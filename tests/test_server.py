from __future__ import annotations

import unittest
from pathlib import Path
from typing import Any, AsyncIterator

from aiohttp.test_utils import TestClient, TestServer

from copilot_lan_bridge.config import Settings
from copilot_lan_bridge.server import create_app


class FakeContent:
    async def iter_any(self) -> AsyncIterator[bytes]:
        yield b"event: response.output_text.delta\n"
        yield b'data: {"delta":"hello"}\n\n'


class FakeResponse:
    status = 200
    reason = "OK"
    headers = {"Content-Type": "text/event-stream", "Cache-Control": "no-cache"}
    content = FakeContent()

    def release(self) -> None:
        pass


class FakeGateway:
    async def start(self) -> None:
        pass

    async def close(self) -> None:
        pass

    async def models(self) -> list[dict[str, Any]]:
        return [
            {
                "id": "gpt-test",
                "name": "GPT Test",
                "supported_endpoints": ["/responses"],
            }
        ]

    async def open_response(self, body: dict[str, Any], accept: str) -> FakeResponse:
        return FakeResponse()


class ServerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.api_key = "test-key-containing-at-least-32-characters"
        settings = Settings(
            host="127.0.0.1",
            port=18787,
            api_key=self.api_key,
            auth_file=Path("unused-in-fake-gateway.json"),
        )
        self.app = create_app(settings, gateway=FakeGateway())
        self.client = TestClient(TestServer(self.app))
        await self.client.start_server()

    async def asyncTearDown(self) -> None:
        await self.client.close()

    def authorization(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    async def test_health_is_available_without_credentials(self) -> None:
        response = await self.client.get("/health")
        self.assertEqual(response.status, 200)
        self.assertEqual(await response.json(), {"status": "ok"})

    async def test_models_require_bridge_api_key(self) -> None:
        unauthorized = await self.client.get("/v1/models")
        self.assertEqual(unauthorized.status, 401)

        authorized = await self.client.get("/v1/models", headers=self.authorization())
        self.assertEqual(authorized.status, 200)
        document = await authorized.json()
        self.assertEqual([model["id"] for model in document["data"]], ["gpt-test"])

    async def test_responses_stream_is_passed_through(self) -> None:
        response = await self.client.post(
            "/v1/responses",
            headers={**self.authorization(), "Accept": "text/event-stream"},
            json={"model": "gpt-test", "input": "hello"},
        )

        self.assertEqual(response.status, 200)
        self.assertEqual(response.headers["Content-Type"], "text/event-stream")
        self.assertEqual(
            await response.read(),
            b'event: response.output_text.delta\ndata: {"delta":"hello"}\n\n',
        )


if __name__ == "__main__":
    unittest.main()