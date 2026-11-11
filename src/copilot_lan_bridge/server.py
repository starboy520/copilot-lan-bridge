from __future__ import annotations

import json
import time
from typing import Any
from urllib.parse import urlparse

from aiohttp import ClientError, ClientResponse, ClientSession, ClientTimeout, web

from .chat_requests import ConversionError, responses_to_chat
from .chat_responses import response_from_chat, stream_from_chat
from .config import Settings
from .credentials import CopilotCredential, CredentialError, load_copilot_credential
from .models import is_available, supports_responses, visible_models
from .security import is_authorized

COPILOT_API_VERSION = "2026-06-01"
MODELS_CACHE_SECONDS = 30


def _copilot_base_url(credential: CopilotCredential) -> str:
    if not credential.enterprise_url:
        return "https://api.githubcopilot.com"
    parsed = urlparse(credential.enterprise_url if "://" in credential.enterprise_url else f"https://{credential.enterprise_url}")
    if not parsed.hostname:
        raise CredentialError("The Copilot enterprise URL in the credential file is invalid.")
    return f"https://copilot-api.{parsed.hostname}"


def _upstream_headers(credential: CopilotCredential, *, accept: str = "application/json") -> dict[str, str]:
    return {
        "Authorization": f"Bearer {credential.token}",
        "Accept": accept,
        "Content-Type": "application/json",
        "OpenAI-Intent": "conversation-edits",
        "User-Agent": "copilot-lan-bridge/0.1",
        "X-GitHub-Api-Version": COPILOT_API_VERSION,
    }


def _sanitize_response_body(body: dict[str, Any]) -> dict[str, Any]:
    sanitized = dict(body)
    tools = sanitized.get("tools")
    if isinstance(tools, list):
        sanitized["tools"] = [tool for tool in tools if not isinstance(tool, dict) or tool.get("type") != "image_generation"]
    return sanitized


class CopilotGateway:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.session: ClientSession | None = None
        self._models: list[dict[str, Any]] | None = None
        self._models_expires_at = 0.0

    async def start(self) -> None:
        self.session = ClientSession(timeout=ClientTimeout(total=None, connect=20, sock_read=None))

    async def close(self) -> None:
        if self.session is not None:
            await self.session.close()

    def _credential(self) -> CopilotCredential:
        return load_copilot_credential(self.settings.auth_file)

    async def models(self) -> list[dict[str, Any]]:
        now = time.monotonic()
        if self._models is not None and now < self._models_expires_at:
            return self._models
        if self.session is None:
            raise RuntimeError("Copilot gateway has not started.")

        credential = self._credential()
        async with self.session.get(
            f"{_copilot_base_url(credential)}/models",
            headers=_upstream_headers(credential),
        ) as response:
            if response.status >= 400:
                raise web.HTTPBadGateway(text=f"Copilot models request failed with status {response.status}.")
            document = await response.json()

        data = document.get("data") if isinstance(document, dict) else None
        self._models = [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []
        self._models_expires_at = now + MODELS_CACHE_SECONDS
        return self._models

    async def open_response(self, body: dict[str, Any], accept: str) -> ClientResponse:
        if self.session is None:
            raise RuntimeError("Copilot gateway has not started.")
        credential = self._credential()
        return await self.session.post(
            f"{_copilot_base_url(credential)}/responses",
            headers=_upstream_headers(credential, accept=accept),
            json=_sanitize_response_body(body),
        )

    async def open_chat_completion(self, body: dict[str, Any], accept: str) -> ClientResponse:
        if self.session is None:
            raise RuntimeError("Copilot gateway has not started.")
        credential = self._credential()
        return await self.session.post(
            f"{_copilot_base_url(credential)}/chat/completions",
            headers=_upstream_headers(credential, accept=accept),
            json=body,
        )


SETTINGS_KEY = web.AppKey("settings", Settings)
GATEWAY_KEY = web.AppKey("gateway", CopilotGateway)


@web.middleware
async def authorization_middleware(request: web.Request, handler: Any) -> web.StreamResponse:
    if request.path != "/health" and not is_authorized(
        request.headers.get("Authorization"), request.app[SETTINGS_KEY].api_key
    ):
        return web.json_response(
            {"error": {"message": "Missing or invalid bridge API key."}},
            status=401,
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await handler(request)


async def health(_: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


async def list_models(request: web.Request) -> web.Response:
    gateway = request.app[GATEWAY_KEY]
    try:
        models = visible_models(await gateway.models())
        return web.json_response({"object": "list", "data": models, "models": models})
    except (CredentialError, ClientError) as error:
        return web.json_response({"error": {"message": str(error)}}, status=502)


async def create_response(request: web.Request) -> web.StreamResponse:
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError):
        return web.json_response({"error": {"message": "Request body must be valid JSON."}}, status=400)
    if not isinstance(body, dict):
        return web.json_response({"error": {"message": "Request body must be a JSON object."}}, status=400)

    model_id = body.get("model")
    if not isinstance(model_id, str) or not model_id:
        return web.json_response({"error": {"message": "Responses request is missing a string model."}}, status=400)

    gateway = request.app[GATEWAY_KEY]
    try:
        models = await gateway.models()
        model = next((item for item in models if item.get("id") == model_id), None)
        if model is None:
            return web.json_response({"error": {"message": f"Copilot model '{model_id}' was not found."}}, status=404)
        if not is_available(model):
            return web.json_response(
                {"error": {"message": f"Copilot model '{model_id}' is disabled or has no supported endpoint."}},
                status=400,
            )

        native = supports_responses(model)
        if native:
            upstream = await gateway.open_response(body, request.headers.get("Accept", "text/event-stream"))
        else:
            chat_body = responses_to_chat(body)
            upstream = await gateway.open_chat_completion(
                chat_body, "text/event-stream" if chat_body.get("stream") else "application/json"
            )
    except ConversionError as error:
        return web.json_response({"error": {"message": str(error), "type": "invalid_request_error"}}, status=400)
    except (CredentialError, ClientError) as error:
        return web.json_response({"error": {"message": str(error)}}, status=502)

    if not native and upstream.status < 400:
        return await _adapt_chat_response(request, upstream, body)

    headers = {}
    for name in ("Content-Type", "Cache-Control", "X-Request-Id"):
        value = upstream.headers.get(name)
        if value:
            headers[name] = value

    downstream = web.StreamResponse(status=upstream.status, reason=upstream.reason, headers=headers)
    await downstream.prepare(request)
    try:
        async for chunk in upstream.content.iter_any():
            await downstream.write(chunk)
    finally:
        upstream.release()
    await downstream.write_eof()
    return downstream


async def _adapt_chat_response(request: web.Request, upstream: ClientResponse, body: dict[str, Any]) -> web.StreamResponse:
    try:
        if not body.get("stream", False):
            try:
                document = await upstream.json()
                if not isinstance(document, dict):
                    raise ConversionError("Upstream Chat Completions response must be an object.")
                response = response_from_chat(document, body)
            except (ConversionError, ClientError, ValueError, TypeError) as error:
                return web.json_response({"error": {"message": str(error), "type": "upstream_error"}}, status=502)
            headers = {"X-Request-Id": upstream.headers["X-Request-Id"]} if upstream.headers.get("X-Request-Id") else {}
            return web.json_response(response, headers=headers)

        if "text/event-stream" not in upstream.headers.get("Content-Type", ""):
            return web.json_response(
                {"error": {"message": "Upstream Chat Completions did not return an event stream."}}, status=502
            )
        headers = {"Content-Type": "text/event-stream", "Cache-Control": "no-cache"}
        if upstream.headers.get("X-Request-Id"):
            headers["X-Request-Id"] = upstream.headers["X-Request-Id"]
        downstream = web.StreamResponse(headers=headers)
        await downstream.prepare(request)
        async for event in stream_from_chat(upstream.content, body):
            await downstream.write(event)
        await downstream.write_eof()
        return downstream
    finally:
        upstream.release()


def create_app(settings: Settings, gateway: CopilotGateway | None = None) -> web.Application:
    app = web.Application(
        middlewares=[authorization_middleware],
        client_max_size=100 * 1024**2,
    )
    selected_gateway = gateway or CopilotGateway(settings)
    app[SETTINGS_KEY] = settings
    app[GATEWAY_KEY] = selected_gateway
    app.router.add_get("/health", health)
    app.router.add_get("/v1/models", list_models)
    app.router.add_post("/v1/responses", create_response)
    app.on_startup.append(lambda _: selected_gateway.start())
    app.on_cleanup.append(lambda _: selected_gateway.close())
    return app
