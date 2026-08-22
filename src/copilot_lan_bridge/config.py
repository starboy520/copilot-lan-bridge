from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass
from pathlib import Path


class ConfigError(ValueError):
    pass


def is_loopback_host(host: str) -> bool:
    normalized = host.strip().lower().strip("[]")
    if normalized == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def default_auth_paths() -> tuple[Path, ...]:
    home = Path.home()
    paths = [home / ".local" / "share" / "opencode" / "auth.json"]
    for variable in ("APPDATA", "LOCALAPPDATA"):
        root = os.environ.get(variable)
        if root:
            paths.append(Path(root) / "opencode" / "auth.json")
    return tuple(dict.fromkeys(paths))


def resolve_auth_file(value: str | None) -> Path:
    if value:
        return Path(value).expanduser()
    for candidate in default_auth_paths():
        if candidate.is_file():
            return candidate
    return default_auth_paths()[0]


@dataclass(frozen=True, slots=True)
class Settings:
    host: str
    port: int
    api_key: str | None
    auth_file: Path

    @classmethod
    def from_env(cls) -> "Settings":
        raw_port = os.environ.get("COPILOT_BRIDGE_PORT", "18787")
        try:
            port = int(raw_port)
        except ValueError as error:
            raise ConfigError("COPILOT_BRIDGE_PORT must be an integer.") from error

        settings = cls(
            host=os.environ.get("COPILOT_BRIDGE_HOST", "127.0.0.1"),
            port=port,
            api_key=os.environ.get("COPILOT_BRIDGE_API_KEY") or None,
            auth_file=resolve_auth_file(os.environ.get("OPENCODE_AUTH_FILE")),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if not 1 <= self.port <= 65535:
            raise ConfigError("COPILOT_BRIDGE_PORT must be between 1 and 65535.")
        if not is_loopback_host(self.host) and (not self.api_key or len(self.api_key) < 32):
            raise ConfigError(
                "COPILOT_BRIDGE_API_KEY must contain at least 32 characters "
                "when listening outside the local machine."
            )