from __future__ import annotations

import sys

from aiohttp import web

from .config import ConfigError, Settings, is_loopback_host
from .server import create_app


def main() -> None:
    try:
        settings = Settings.from_env()
    except ConfigError as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        raise SystemExit(2) from error

    scope = "local only" if is_loopback_host(settings.host) else "LAN"
    print(f"Copilot LAN bridge listening on http://{settings.host}:{settings.port}/v1 ({scope})", file=sys.stderr)
    print(f"Using OpenCode credentials from {settings.auth_file}", file=sys.stderr)
    web.run_app(create_app(settings), host=settings.host, port=settings.port, print=None)