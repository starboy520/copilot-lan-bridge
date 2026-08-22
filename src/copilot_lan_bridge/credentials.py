from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


class CredentialError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class CopilotCredential:
    token: str
    enterprise_url: str | None = None


def load_copilot_credential(path: Path) -> CopilotCredential:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise CredentialError(
            f"OpenCode credential file was not found at {path}. "
            "Set OPENCODE_AUTH_FILE to its actual location."
        ) from error
    except (OSError, json.JSONDecodeError) as error:
        raise CredentialError(f"Cannot read OpenCode credential file at {path}: {error}") from error

    entry = document.get("github-copilot") if isinstance(document, dict) else None
    token = entry.get("refresh") if isinstance(entry, dict) else None
    if entry is None or entry.get("type") != "oauth" or not isinstance(token, str) or not token:
        raise CredentialError(f"GitHub Copilot OAuth credential was not found in {path}.")

    enterprise_url = entry.get("enterpriseUrl")
    return CopilotCredential(
        token=token,
        enterprise_url=enterprise_url if isinstance(enterprise_url, str) and enterprise_url else None,
    )