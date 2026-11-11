"""Build a Codex model catalog from models exposed by Copilot LAN Bridge."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .models import is_available, supports_responses


class CatalogError(ValueError):
    """A catalog could not be built or loaded."""


def _positive_integer(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None


def _ordinary_template(models: list[dict[str, Any]]) -> dict[str, Any] | None:
    ordinary = [model for model in models if model.get("tool_mode") in (None, "direct") and not model.get("use_responses_lite")]
    return next((model for model in ordinary if model.get("slug") == "gpt-5.5"), ordinary[0] if ordinary else None)


def _capabilities(source: dict[str, Any]) -> tuple[int, list[str]]:
    capabilities = source.get("capabilities")
    capabilities = capabilities if isinstance(capabilities, dict) else {}
    limits = capabilities.get("limits")
    limits = limits if isinstance(limits, dict) else {}
    # Copilot can impose a smaller prompt limit than the model's total window.
    # Advertise that effective limit so Codex compacts before Copilot rejects it.
    windows = [
        value for candidate in (
            limits.get("max_context_window_tokens"),
            limits.get("max_prompt_tokens"),
            capabilities.get("context_window"),
            source.get("context_window"),
        )
        if (value := _positive_integer(candidate)) is not None
    ]
    context_window = min(windows) if windows else 32768
    supports = capabilities.get("supports")
    supports = supports if isinstance(supports, dict) else {}
    modalities = capabilities.get("input_modalities", source.get("input_modalities"))
    vision = supports.get("vision")
    if not isinstance(vision, bool):
        vision = isinstance(modalities, list) and "image" in modalities
    return context_window, ["text", "image"] if vision else ["text"]


def _adapted_model(source: dict[str, Any], template: dict[str, Any], priority: int) -> dict[str, Any]:
    model = deepcopy(template)
    context_window, modalities = _capabilities(source)
    display_name = source.get("name") or source.get("display_name") or source["id"]
    if not isinstance(display_name, str):
        display_name = source["id"]
    model.update({
        "slug": source["id"],
        "display_name": display_name,
        "description": f"{display_name} through Copilot LAN Bridge.",
        "visibility": "list",
        "supported_in_api": True,
        "priority": priority,
        "prefer_websockets": False,
        "use_responses_lite": False,
        "tool_mode": None,
        "experimental_supported_tools": [],
        "supports_search_tool": False,
        "supports_image_detail_original": False,
        "input_modalities": modalities,
        "context_window": context_window,
        "max_context_window": context_window,
        "auto_compact_token_limit": max(1, context_window * 4 // 5),
        "default_reasoning_level": "low",
        "supported_reasoning_levels": [
            {"effort": "low", "description": "Lower reasoning effort"},
            {"effort": "medium", "description": "Moderate reasoning effort"},
            {"effort": "high", "description": "Higher reasoning effort"},
        ],
        "default_reasoning_summary": "none",
        "supports_reasoning_summary_parameter": False,
        "supports_reasoning_summaries": False,
        "supports_reasoning_effort_updates": False,
        "supports_experimental_context": False,
        "supports_parallel_tool_calls": True,
        "support_verbosity": True,
        "default_verbosity": "low",
        "multi_agent_version": None,
        "multi_agent_reasoning_effort": None,
        "guardian": None,
        "node_repl_auto_review_required": False,
        "node_repl_disabled": True,
        "requires_sandboxed_review": False,
        "auto_review_model_override": None,
        "model_specialty": None,
        "default_service_tier": None,
        "service_tiers": [],
        "additional_speed_tiers": [],
        "upgrade": None,
        "availability_nux": None,
    })
    return model


def build_catalog(upstream_models: list[dict[str, Any]], bundled_catalog: dict[str, Any]) -> dict[str, Any]:
    """Keep matching native metadata and add safe ordinary-tool model entries.

    Only models available through this bridge are included. Chat-only models
    always get conservative metadata, even if a bundled model has the same ID.
    Both arguments remain unchanged.
    """
    if not isinstance(upstream_models, list):
        raise CatalogError("The Bridge model list must be a list.")
    bundled = bundled_catalog.get("models") if isinstance(bundled_catalog, dict) else None
    if not isinstance(bundled, list) or not bundled:
        raise CatalogError("The bundled Codex catalog must contain a non-empty models list.")
    if any(not isinstance(model, dict) or not isinstance(model.get("slug"), str) for model in bundled):
        raise CatalogError("Each bundled Codex model must be an object with a string slug.")
    native_metadata = {model["slug"]: model for model in bundled}
    template = _ordinary_template(bundled)
    models: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source in upstream_models:
        if not isinstance(source, dict) or not is_available(source) or source["id"] in seen:
            continue
        seen.add(source["id"])
        if supports_responses(source) and source["id"] in native_metadata:
            models.append(deepcopy(native_metadata[source["id"]]))
            continue
        if template is None:
            raise CatalogError("The bundled Codex catalog has no ordinary-tool template (such as gpt-5.5); code-mode-only templates cannot be used for Bridge models.")
        models.append(_adapted_model(source, template, len(models) + 1))
    if not models:
        raise CatalogError("The Bridge did not return any available Responses or Chat Completions models.")
    return {"models": models}


def _load_bundled_catalog() -> dict[str, Any]:
    try:
        result = subprocess.run(
            ["codex", "debug", "models", "--bundled"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except FileNotFoundError as error:
        raise CatalogError("Codex CLI was not found on PATH.") from error
    except (OSError, subprocess.TimeoutExpired) as error:
        raise CatalogError("Could not run 'codex debug models --bundled'.") from error
    if result.returncode:
        raise CatalogError("'codex debug models --bundled' failed; install a Codex CLI version that supports this command.")
    try:
        catalog = json.loads(result.stdout)
    except ValueError as error:
        raise CatalogError("'codex debug models --bundled' did not return a JSON catalog.") from error
    if not isinstance(catalog, dict):
        raise CatalogError("The bundled Codex catalog must be a JSON object.")
    return catalog


def _load_bridge_models(base_url: str, api_key_file: Path) -> list[dict[str, Any]]:
    parsed = urlsplit(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise CatalogError("--base-url must be an HTTP(S) API base URL without credentials, query, or fragment.")
    try:
        api_key = api_key_file.expanduser().read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError) as error:
        raise CatalogError("Could not read the Bridge API key file.") from error
    if not api_key or any(character in api_key for character in "\r\n"):
        raise CatalogError("The Bridge API key file must contain one non-empty token.")
    request = Request(
        base_url.rstrip("/") + "/models",
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=30) as response:
            document = json.load(response)
    except HTTPError as error:
        raise CatalogError(f"Bridge models request failed with HTTP {error.code}.") from error
    except (OSError, URLError) as error:
        raise CatalogError("Could not connect to the Bridge models endpoint.") from error
    except (ValueError, UnicodeError) as error:
        raise CatalogError("The Bridge models endpoint did not return valid JSON.") from error
    models = document.get("data", document.get("models")) if isinstance(document, dict) else None
    if not isinstance(models, list):
        raise CatalogError("The Bridge models response must contain a data or models list.")
    return models


def _write_catalog(catalog: dict[str, Any], output: Path) -> None:
    output = output.expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        # A same-directory temporary file makes replace atomic. mkstemp also
        # creates it with owner-only permissions; no API key is ever written.
        descriptor, filename = tempfile.mkstemp(prefix=f".{output.name}.", suffix=".tmp", dir=output.parent)
        temporary = Path(filename)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(catalog, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export Bridge models into a startup model catalog for Codex.")
    parser.add_argument("--base-url", required=True, help="Bridge API base URL, including /v1")
    parser.add_argument("--api-key-file", required=True, type=Path, help="File containing the Bridge API key")
    parser.add_argument("--output", required=True, type=Path, help="Destination Codex model catalog JSON file")
    args = parser.parse_args(argv)
    try:
        bundled = _load_bundled_catalog()
        models = _load_bridge_models(args.base_url, args.api_key_file)
        catalog = build_catalog(models, bundled)
        _write_catalog(catalog, args.output)
    except (CatalogError, OSError) as error:
        # Do not print captured subprocess output, upstream response bodies, or
        # request headers: those sources can contain authentication information.
        print(f"Catalog export failed: {error}", file=sys.stderr)
        return 2
    print(f"Wrote {len(catalog['models'])} models to {args.output.expanduser()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
