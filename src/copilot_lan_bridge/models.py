from __future__ import annotations

from typing import Any


def _normalized_endpoints(model: dict[str, Any]) -> set[str]:
    endpoints = model.get("supported_endpoints")
    if not isinstance(endpoints, list):
        return set()
    normalized = {endpoint.strip().lower() for endpoint in endpoints if isinstance(endpoint, str) and endpoint.strip()}
    return {endpoint if endpoint.startswith("/") else f"/{endpoint}" for endpoint in normalized}


def supports_responses(model: dict[str, Any]) -> bool:
    return bool(_normalized_endpoints(model) & {"/responses", "/v1/responses"})


def supports_chat_completions(model: dict[str, Any]) -> bool:
    return bool(_normalized_endpoints(model) & {"/chat/completions", "/v1/chat/completions"})


def is_available(model: dict[str, Any]) -> bool:
    model_id = model.get("id")
    policy = model.get("policy")
    return (
        isinstance(model_id, str)
        and bool(model_id.strip())
        and not (isinstance(policy, dict) and policy.get("state") == "disabled")
        and (supports_responses(model) or supports_chat_completions(model))
    )


def visible_models(models: list[dict[str, Any]]) -> list[dict[str, Any]]:
    visible: list[dict[str, Any]] = []
    for source in models:
        if not is_available(source):
            continue

        model_id = source["id"]
        model = dict(source)
        model.update(
            {
                "id": model_id,
                "slug": model_id,
                "object": "model",
                "display_name": source.get("name") or model_id,
                "owned_by": "github-copilot",
            }
        )
        visible.append(model)
    return visible
