from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from typing import Any, AsyncIterator

from aiohttp.test_utils import TestClient, TestServer

from copilot_lan_bridge.config import Settings
from copilot_lan_bridge.server import create_app


def chat_completion(
    content: str | None = "你好，世界", *, tool_calls: list[dict[str, Any]] | None = None,
    finish_reason: str = "stop",
) -> dict[str, Any]:
    message: dict[str, Any] = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = tool_calls
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 1700000000,
        "model": "gemini-test",
        "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 7, "total_tokens": 12},
    }


def chat_chunk(delta: dict[str, Any], finish_reason: str | None = None) -> dict[str, Any]:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion.chunk",
        "created": 1700000000,
        "model": "gemini-test",
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
    }


def sse_bytes(*chunks: dict[str, Any] | str) -> bytes:
    # CRLF, comments, Unicode, and arbitrary read boundaries occur on real SSE connections.
    frames = [": upstream heartbeat\r\n\r\n"]
    for chunk in chunks:
        payload = chunk if isinstance(chunk, str) else json.dumps(chunk, ensure_ascii=False)
        frames.append(f"data: {payload}\r\n\r\n")
    return "".join(frames).encode("utf-8")


def response_events(raw: bytes) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for frame in raw.decode("utf-8").replace("\r\n", "\n").split("\n\n"):
        data = "\n".join(line[5:].lstrip() for line in frame.splitlines() if line.startswith("data:"))
        if data and data != "[DONE]":
            events.append(json.loads(data))
    return events


class FakeContent:
    def __init__(self, data: bytes, fragment_size: int = 2):
        self.data = data
        self.fragment_size = fragment_size

    async def iter_any(self) -> AsyncIterator[bytes]:
        for offset in range(0, len(self.data), self.fragment_size):
            yield self.data[offset:offset + self.fragment_size]


class FakeResponse:
    def __init__(
        self, document: dict[str, Any] | None = None, *, data: bytes | None = None,
        content_type: str = "application/json", status: int = 200,
    ):
        self.status = status
        self.reason = "OK" if status == 200 else "Upstream error"
        self.headers = {"Content-Type": content_type, "X-Request-Id": "upstream-request"}
        self.data = data if data is not None else json.dumps(document).encode()
        self.content = FakeContent(self.data)
        self.released = False

    async def json(self, **_: Any) -> Any:
        return json.loads(self.data)

    async def read(self) -> bytes:
        return self.data

    def release(self) -> None:
        self.released = True


class FakeGateway:
    def __init__(self):
        self.chat_calls: list[dict[str, Any]] = []
        self.native_calls: list[dict[str, Any]] = []
        self.chat_responses = [FakeResponse(chat_completion())]
        self.native_response = FakeResponse(
            data=b'event: response.output_text.delta\ndata: {"delta":"native"}\n\n',
            content_type="text/event-stream",
        )

    async def start(self) -> None:
        pass

    async def close(self) -> None:
        pass

    async def models(self) -> list[dict[str, Any]]:
        return [
            {"id": "gemini-test", "supported_endpoints": ["/chat/completions"]},
            {"id": "dual-test", "supported_endpoints": ["/responses", "/chat/completions"]},
            {
                "id": "disabled-test", "supported_endpoints": ["/chat/completions"],
                "policy": {"state": "disabled"},
            },
            {"id": "messages-only", "supported_endpoints": ["/v1/messages"]},
        ]

    async def open_chat_completion(self, body: dict[str, Any], accept: str) -> FakeResponse:
        self.chat_calls.append(copy.deepcopy(body))
        return self.chat_responses.pop(0)

    async def open_response(self, body: dict[str, Any], accept: str) -> FakeResponse:
        self.native_calls.append(copy.deepcopy(body))
        return self.native_response


class ChatServerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.gateway = FakeGateway()
        settings = Settings(
            host="127.0.0.1", port=18787, api_key="test-key-containing-at-least-32-characters",
            auth_file=Path("unused-fake-credential.json"),
        )
        self.client = TestClient(TestServer(create_app(settings, gateway=self.gateway)))
        await self.client.start_server()
        self.headers = {"Authorization": f"Bearer {settings.api_key}"}

    async def asyncTearDown(self) -> None:
        await self.client.close()

    async def post(self, **body: Any) -> Any:
        return await self.client.post(
            "/v1/responses", headers=self.headers,
            json={"model": "gemini-test", "input": "hello", **body},
        )

    async def test_chat_models_are_visible_but_disabled_and_unsupported_are_hidden(self) -> None:
        response = await self.client.get("/v1/models", headers=self.headers)
        self.assertEqual(response.status, 200)
        document = await response.json()
        self.assertEqual({model["id"] for model in document["data"]}, {"gemini-test", "dual-test"})

    async def test_plain_response_converts_text_and_usage(self) -> None:
        upstream = self.gateway.chat_responses[0]
        response = await self.post(instructions="Write code", max_output_tokens=100)
        self.assertEqual(response.status, 200)
        document = await response.json()
        self.assertEqual(document["object"], "response")
        self.assertEqual(document["status"], "completed")
        self.assertEqual(document["model"], "gemini-test")
        message = document["output"][0]
        self.assertEqual((message["type"], message["role"]), ("message", "assistant"))
        self.assertEqual(message["content"][0]["type"], "output_text")
        self.assertEqual(message["content"][0]["text"], "你好，世界")
        self.assertEqual(
            {key: document["usage"][key] for key in ("input_tokens", "output_tokens", "total_tokens")},
            {"input_tokens": 5, "output_tokens": 7, "total_tokens": 12},
        )
        self.assertEqual(self.gateway.chat_calls[0]["messages"][-1], {"role": "user", "content": "hello"})
        self.assertTrue(upstream.released)
        self.assertFalse(self.gateway.native_calls)

    async def test_function_call_and_result_round_trip(self) -> None:
        function = {"name": "run_command", "arguments": '{"command":"pwd"}'}
        self.gateway.chat_responses = [
            FakeResponse(chat_completion(None, tool_calls=[{
                "id": "call-shell", "type": "function", "function": function,
            }], finish_reason="tool_calls")),
            FakeResponse(chat_completion("The current directory is /workspace.")),
        ]
        tool = {
            "type": "function", "name": "run_command", "description": "Run a shell command",
            "parameters": {"type": "object", "properties": {"command": {"type": "string"}}},
        }
        response = await self.post(tools=[tool])
        self.assertEqual(response.status, 200)
        document = await response.json()
        call = next(item for item in document["output"] if item["type"] == "function_call")
        self.assertEqual(call["call_id"], "call-shell")
        self.assertEqual(call["name"], "run_command")
        self.assertEqual(json.loads(call["arguments"]), {"command": "pwd"})
        followup = await self.post(
            tools=[tool], input=[
                {"role": "user", "content": "Where am I?"}, call,
                {"type": "function_call_output", "call_id": call["call_id"], "output": "/workspace"},
            ],
        )
        self.assertEqual(followup.status, 200)
        messages = self.gateway.chat_calls[-1]["messages"]
        self.assertEqual(messages[-2]["role"], "assistant")
        self.assertEqual(messages[-2]["tool_calls"][0]["id"], "call-shell")
        self.assertEqual(messages[-2]["tool_calls"][0]["function"], function)
        self.assertEqual(messages[-1], {"role": "tool", "tool_call_id": "call-shell", "content": "/workspace"})

    async def test_custom_tool_response_preserves_freeform_input(self) -> None:
        patch = "*** Begin Patch\n*** End Patch"
        self.gateway.chat_responses = [FakeResponse(chat_completion(None, tool_calls=[{
            "id": "call-patch", "type": "function",
            "function": {"name": "apply_patch", "arguments": json.dumps({"input": patch})},
        }], finish_reason="tool_calls"))]
        response = await self.post(tools=[{"type": "custom", "name": "apply_patch", "description": "Apply a patch"}])
        self.assertEqual(response.status, 200)
        document = await response.json()
        call = next(item for item in document["output"] if item["type"] == "custom_tool_call")
        self.assertEqual(call["call_id"], "call-patch")
        self.assertEqual(call["name"], "apply_patch")
        self.assertEqual(call["input"], patch)

    async def test_fragmented_stream_preserves_unicode_tool_arguments_and_usage(self) -> None:
        data = sse_bytes(
            chat_chunk({"role": "assistant", "content": "你"}),
            chat_chunk({"content": "好"}),
            chat_chunk({"tool_calls": [{"index": 0, "id": "call-shell", "type": "function", "function": {
                "name": "run_command", "arguments": '{"command":',
            }}]}),
            chat_chunk({"tool_calls": [{"index": 0, "function": {"arguments": '"pwd"}'}}]}),
            chat_chunk({}, "tool_calls"),
            {"choices": [], "usage": {"prompt_tokens": 9, "completion_tokens": 4, "total_tokens": 13}},
            "[DONE]",
        )
        upstream = FakeResponse(data=data, content_type="text/event-stream")
        self.gateway.chat_responses = [upstream]
        response = await self.post(stream=True, tools=[{
            "type": "function", "name": "run_command", "parameters": {"type": "object"},
        }])
        self.assertEqual(response.status, 200)
        self.assertTrue(response.headers["Content-Type"].startswith("text/event-stream"))
        events = response_events(await response.read())
        types = [event["type"] for event in events]
        self.assertEqual(types[0], "response.created")
        self.assertEqual(types[-1], "response.completed")
        self.assertEqual("".join(event["delta"] for event in events if event["type"] == "response.output_text.delta"), "你好")
        self.assertEqual(
            "".join(event["delta"] for event in events if event["type"] == "response.function_call_arguments.delta"),
            '{"command":"pwd"}',
        )
        completed = events[-1]["response"]
        self.assertEqual(completed["usage"]["total_tokens"], 13)
        calls = [item for item in completed["output"] if item["type"] == "function_call"]
        self.assertEqual(calls[0]["call_id"], "call-shell")
        self.assertEqual(json.loads(calls[0]["arguments"]), {"command": "pwd"})
        numbers = [event["sequence_number"] for event in events]
        self.assertEqual(numbers, list(range(numbers[0], numbers[0] + len(numbers))))
        self.assertTrue(upstream.released)

    async def test_custom_tool_stream_decodes_wrapped_input(self) -> None:
        patch = "*** Begin Patch\n*** End Patch"
        arguments = json.dumps({"input": patch})
        data = sse_bytes(
            chat_chunk({"tool_calls": [{"index": 0, "id": "call-patch", "type": "function", "function": {
                "name": "apply_patch", "arguments": arguments[:12],
            }}]}),
            chat_chunk({"tool_calls": [{"index": 0, "function": {"arguments": arguments[12:]}}]}),
            chat_chunk({}, "tool_calls"), "[DONE]",
        )
        self.gateway.chat_responses = [FakeResponse(data=data, content_type="text/event-stream")]
        response = await self.post(stream=True, tools=[{"type": "custom", "name": "apply_patch"}])
        self.assertEqual(response.status, 200)
        events = response_events(await response.read())
        self.assertEqual(events[-1]["type"], "response.completed")
        deltas = [event["delta"] for event in events if event["type"] == "response.custom_tool_call_input.delta"]
        self.assertEqual("".join(deltas), patch)
        call = next(item for item in events[-1]["response"]["output"] if item["type"] == "custom_tool_call")
        self.assertEqual(call["input"], patch)
        self.assertEqual(call["call_id"], "call-patch")

    async def test_interleaved_parallel_tools_keep_ids_and_arguments_separate(self) -> None:
        data = sse_bytes(
            chat_chunk({"tool_calls": [
                {"index": 1, "id": "call-read", "type": "function", "function": {"name": "read_file", "arguments": '{"path":'}},
                {"index": 0, "id": "call-shell", "type": "function", "function": {"name": "run_command", "arguments": '{"command":'}},
            ]}),
            chat_chunk({"tool_calls": [{"index": 0, "function": {"arguments": '"pwd"}'}}]}),
            chat_chunk({"tool_calls": [{"index": 1, "function": {"arguments": '"main.py"}'}}]}),
            chat_chunk({}, "tool_calls"), "[DONE]",
        )
        self.gateway.chat_responses = [FakeResponse(data=data, content_type="text/event-stream")]
        response = await self.post(stream=True, tools=[
            {"type": "function", "name": name, "parameters": {"type": "object"}}
            for name in ("run_command", "read_file")
        ])
        self.assertEqual(response.status, 200)
        events = response_events(await response.read())
        self.assertEqual(events[-1]["type"], "response.completed")
        output = events[-1]["response"]["output"]
        calls = {item["call_id"]: item for item in output}
        self.assertEqual(set(calls), {"call-shell", "call-read"})
        self.assertEqual(calls["call-shell"]["name"], "run_command")
        self.assertEqual(json.loads(calls["call-shell"]["arguments"]), {"command": "pwd"})
        self.assertEqual(calls["call-read"]["name"], "read_file")
        self.assertEqual(json.loads(calls["call-read"]["arguments"]), {"path": "main.py"})
        self.assertNotEqual(calls["call-shell"]["id"], calls["call-read"]["id"])
        for event in events:
            if event["type"] == "response.function_call_arguments.delta":
                self.assertEqual(event["item_id"], output[event["output_index"]]["id"])

    async def test_token_limit_is_reported_as_incomplete_for_json_and_stream(self) -> None:
        for stream in (False, True):
            with self.subTest(stream=stream):
                if stream:
                    upstream = FakeResponse(
                        data=sse_bytes(chat_chunk({"content": "unfinished"}), chat_chunk({}, "length"), "[DONE]"),
                        content_type="text/event-stream",
                    )
                else:
                    upstream = FakeResponse(chat_completion("unfinished", finish_reason="length"))
                self.gateway.chat_responses = [upstream]
                response = await self.post(stream=stream)
                self.assertEqual(response.status, 200)
                if stream:
                    events = response_events(await response.read())
                    self.assertEqual(events[-1]["type"], "response.incomplete")
                    document = events[-1]["response"]
                    self.assertFalse(any(event["type"] == "response.completed" for event in events))
                else:
                    document = await response.json()
                self.assertEqual(document["status"], "incomplete")
                self.assertEqual(document["incomplete_details"]["reason"], "max_output_tokens")

    async def test_unsupported_content_returns_validation_error_before_upstream_call(self) -> None:
        response = await self.post(input=[{
            "role": "user", "content": [{"type": "input_file", "file_id": "file-not-supported"}],
        }])
        self.assertEqual(response.status, 400)
        document = await response.json()
        self.assertTrue(document["error"]["message"])
        self.assertFalse(self.gateway.chat_calls)

    async def test_malformed_upstream_json_response_returns_bad_gateway(self) -> None:
        upstream = FakeResponse({"choices": []})
        self.gateway.chat_responses = [upstream]
        response = await self.post()
        self.assertEqual(response.status, 502)
        document = await response.json()
        self.assertTrue(document["error"]["message"])
        self.assertTrue(upstream.released)

    async def test_namespaced_function_and_custom_tools_round_trip(self) -> None:
        patch = "*** Begin Patch\n*** End Patch"
        cases = [
            ("function", "run_command", '{"command":"pwd"}'),
            ("custom", "apply_patch", json.dumps({"input": patch})),
        ]
        for kind, name, arguments in cases:
            with self.subTest(kind=kind):
                chat_name = f"functions__{name}"
                self.gateway.chat_responses = [
                    FakeResponse(chat_completion(None, tool_calls=[{
                        "id": "call-namespaced", "type": "function",
                        "function": {"name": chat_name, "arguments": arguments},
                    }], finish_reason="tool_calls")),
                    FakeResponse(chat_completion("done")),
                ]
                definition = {"type": kind, "name": name}
                if kind == "function":
                    definition["parameters"] = {"type": "object"}
                tools = [{"type": "namespace", "name": "functions", "tools": [definition]}]
                response = await self.post(tools=tools)
                self.assertEqual(response.status, 200)
                document = await response.json()
                call_type = "function_call" if kind == "function" else "custom_tool_call"
                call = next(item for item in document["output"] if item["type"] == call_type)
                self.assertEqual((call["name"], call["namespace"]), (name, "functions"))
                if kind == "custom":
                    self.assertEqual(call["input"], patch)
                self.assertEqual(self.gateway.chat_calls[-1]["tools"][0]["function"]["name"], chat_name)
                followup = await self.post(tools=tools, input=[
                    {"role": "user", "content": "do the task"}, call,
                    {"type": f"{call_type}_output", "call_id": call["call_id"], "output": "success"},
                ])
                self.assertEqual(followup.status, 200)
                messages = self.gateway.chat_calls[-1]["messages"]
                function = messages[-2]["tool_calls"][0]["function"]
                self.assertEqual(function["name"], chat_name)
                self.assertEqual(json.loads(function["arguments"]), json.loads(arguments))
                self.assertEqual(messages[-1]["tool_call_id"], "call-namespaced")

    async def test_fragmented_tool_identity_is_consistent_across_events_and_followup(self) -> None:
        data = sse_bytes(
            chat_chunk({"tool_calls": [{"index": 0, "id": "call_", "type": "function", "function": {
                "name": "read_", "arguments": "{",
            }}]}),
            chat_chunk({"tool_calls": [{"index": 0, "id": "suffix", "function": {
                "name": "file", "arguments": "}",
            }}]}, "tool_calls"),
            "[DONE]",
        )
        self.gateway.chat_responses = [
            FakeResponse(data=data, content_type="text/event-stream"),
            FakeResponse(chat_completion("The file was read.")),
        ]
        tools = [{"type": "function", "name": "read_file", "parameters": {"type": "object"}}]
        response = await self.post(stream=True, tools=tools)
        self.assertEqual(response.status, 200)
        events = response_events(await response.read())
        self.assertEqual(events[-1]["type"], "response.completed")
        added = next(event["item"] for event in events if event["type"] == "response.output_item.added")
        done = next(event["item"] for event in events if event["type"] == "response.output_item.done")
        call = events[-1]["response"]["output"][0]
        for item in (added, done, call):
            self.assertEqual(item["type"], "function_call")
            self.assertEqual(item["call_id"], "call_suffix")
            self.assertEqual(item["name"], "read_file")
            self.assertEqual(item["id"], call["id"])
        self.assertEqual(call["arguments"], "{}")
        followup = await self.post(tools=tools, input=[
            {"role": "user", "content": "Read the file"}, call,
            {"type": "function_call_output", "call_id": call["call_id"], "output": "file contents"},
        ])
        self.assertEqual(followup.status, 200)
        messages = self.gateway.chat_calls[-1]["messages"]
        self.assertEqual(messages[-2]["tool_calls"][0]["id"], "call_suffix")
        self.assertEqual(messages[-2]["tool_calls"][0]["function"], {"name": "read_file", "arguments": "{}"})
        self.assertEqual(messages[-1]["tool_call_id"], "call_suffix")

    async def test_malformed_stream_tool_calls_or_delta_fail_cleanly(self) -> None:
        bad_deltas = [
            [],
            {"tool_calls": [None]},
            {"tool_calls": {"unexpected": {}}},
            {"tool_calls": [{"index": 0, "function": "invalid"}]},
            {"content": {"unexpected": True}},
        ]
        for delta in bad_deltas:
            with self.subTest(delta=delta):
                malformed = chat_chunk({})
                malformed["choices"][0]["delta"] = delta
                self.gateway.chat_responses = [FakeResponse(
                    data=sse_bytes(malformed, chat_chunk({}, "stop"), "[DONE]"),
                    content_type="text/event-stream",
                )]
                response = await self.post(stream=True)
                self.assertEqual(response.status, 200)
                events = response_events(await response.read())
                self.assertEqual(events[-1]["type"], "response.failed")
                self.assertFalse(any(event["type"] == "response.completed" for event in events))

    async def test_upstream_http_error_status_and_body_are_preserved(self) -> None:
        document = {"error": {"message": "Rate limit reached", "type": "rate_limit_error"}}
        upstream = FakeResponse(document, status=429)
        self.gateway.chat_responses = [upstream]
        response = await self.post(stream=True)
        self.assertEqual(response.status, 429)
        self.assertEqual(await response.json(), document)
        self.assertTrue(upstream.released)

    async def test_upstream_stream_error_is_not_reported_as_completed(self) -> None:
        self.gateway.chat_responses = [FakeResponse(
            data=sse_bytes(chat_chunk({"content": "partial"}), {"error": {"message": "Upstream failed"}}),
            content_type="text/event-stream",
        )]
        response = await self.post(stream=True)
        self.assertEqual(response.status, 200)
        events = response_events(await response.read())
        self.assertFalse(any(event["type"] == "response.completed" for event in events))
        self.assertTrue(any(event["type"] in {"error", "response.failed"} for event in events))
        self.assertIn("Upstream failed", json.dumps(events))

    async def test_truncated_upstream_stream_is_not_reported_as_completed(self) -> None:
        self.gateway.chat_responses = [FakeResponse(
            data=sse_bytes(chat_chunk({"content": "partial"})), content_type="text/event-stream",
        )]
        response = await self.post(stream=True)
        self.assertEqual(response.status, 200)
        events = response_events(await response.read())
        self.assertFalse(any(event["type"] == "response.completed" for event in events))
        self.assertTrue(any(event["type"] in {"error", "response.failed"} for event in events))

    async def test_disabled_model_cannot_be_requested_directly(self) -> None:
        response = await self.post(model="disabled-test")
        self.assertGreaterEqual(response.status, 400)
        self.assertLess(response.status, 500)
        self.assertFalse(self.gateway.chat_calls)
        self.assertFalse(self.gateway.native_calls)

    async def test_native_responses_are_preferred_when_both_protocols_exist(self) -> None:
        response = await self.post(model="dual-test", stream=True)
        self.assertEqual(response.status, 200)
        self.assertEqual(await response.read(), self.gateway.native_response.data)
        self.assertEqual(len(self.gateway.native_calls), 1)
        self.assertFalse(self.gateway.chat_calls)

    async def test_unsupported_stateful_request_returns_validation_error(self) -> None:
        response = await self.post(previous_response_id="resp-not-stored")
        self.assertEqual(response.status, 400)
        self.assertFalse(self.gateway.chat_calls)


if __name__ == "__main__":
    unittest.main()
