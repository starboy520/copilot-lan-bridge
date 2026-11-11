from __future__ import annotations

import json
import time
import uuid
from collections.abc import AsyncIterator
from copy import deepcopy
from typing import Any

from aiohttp import ClientError

from .chat_requests import ConversionError, tool_name_map


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _usage(source: dict[str, Any]) -> dict[str, Any]:
    input_tokens = source.get("prompt_tokens", 0)
    output_tokens = source.get("completion_tokens", 0)
    return {
        "input_tokens": input_tokens,
        "input_tokens_details": {"cached_tokens": (source.get("prompt_tokens_details") or {}).get("cached_tokens", 0)},
        "output_tokens": output_tokens,
        "output_tokens_details": {"reasoning_tokens": (source.get("completion_tokens_details") or {}).get("reasoning_tokens", 0)},
        "total_tokens": source.get("total_tokens", input_tokens + output_tokens),
    }


class ChatResponse:
    """Accumulate Chat deltas and emit the corresponding Responses lifecycle."""

    def __init__(self, body: dict[str, Any]) -> None:
        self.tool_names = tool_name_map(body)
        self.response: dict[str, Any] = {
            "id": _id("resp"),
            "object": "response",
            "created_at": int(time.time()),
            "status": "in_progress",
            "error": None,
            "incomplete_details": None,
            "instructions": body.get("instructions"),
            "max_output_tokens": body.get("max_output_tokens"),
            "model": body["model"],
            "output": [],
            "parallel_tool_calls": body.get("parallel_tool_calls", True),
            "previous_response_id": None,
            "reasoning": body.get("reasoning"),
            "store": False,
            "temperature": body.get("temperature", 1),
            "text": body.get("text", {"format": {"type": "text"}}),
            "tool_choice": body.get("tool_choice", "auto"),
            "tools": body.get("tools", []),
            "top_p": body.get("top_p", 1),
            "truncation": "disabled",
            "usage": None,
            "metadata": body.get("metadata", {}),
        }
        self.sequence = 0
        self.message_index: int | None = None
        self.tools: dict[int, dict[str, Any]] = {}
        self.finish_reason: str | None = None

    def event(self, event_type: str, **fields: Any) -> dict[str, Any]:
        event = {"type": event_type, "sequence_number": self.sequence, **fields}
        self.sequence += 1
        # Events are snapshots; later deltas must not modify earlier events.
        return deepcopy(event)

    def start(self) -> list[dict[str, Any]]:
        return [self.event("response.created", response=self.response), self.event("response.in_progress", response=self.response)]

    def _text(self, text: str, *, refusal: bool = False) -> list[dict[str, Any]]:
        events = []
        if self.message_index is None:
            self.message_index = len(self.response["output"])
            item = {"id": _id("msg"), "type": "message", "role": "assistant", "status": "in_progress", "content": []}
            self.response["output"].append(item)
            events.append(self.event("response.output_item.added", output_index=self.message_index, item=item))
        item = self.response["output"][self.message_index]
        part_type = "refusal" if refusal else "output_text"
        content_index = next((i for i, part in enumerate(item["content"]) if part["type"] == part_type), None)
        if content_index is None:
            content_index = len(item["content"])
            part = {"type": "refusal", "refusal": ""} if refusal else {"type": "output_text", "text": "", "annotations": [], "logprobs": []}
            item["content"].append(part)
            events.append(self.event("response.content_part.added", item_id=item["id"], output_index=self.message_index, content_index=content_index, part=part))
        part = item["content"][content_index]
        part["refusal" if refusal else "text"] += text
        fields = {"item_id": item["id"], "output_index": self.message_index, "content_index": content_index, "delta": text}
        if not refusal:
            fields["logprobs"] = []
        events.append(self.event("response.refusal.delta" if refusal else "response.output_text.delta", **fields))
        return events

    def _open_tool(self, state: dict[str, Any]) -> list[dict[str, Any]]:
        if "output_index" in state:
            return []
        if not state["name"]:
            raise ConversionError("Upstream tool call is missing a function name.")
        spec = self.tool_names.get(state["name"], {"name": state["name"], "type": "function"})
        custom = spec["type"] == "custom"
        item = {
            "id": _id("ctc" if custom else "fc"),
            "type": "custom_tool_call" if custom else "function_call",
            "status": "in_progress",
            "call_id": state["call_id"] or _id("call"),
            "name": spec["name"],
            "input" if custom else "arguments": "",
        }
        if spec.get("namespace"):
            item["namespace"] = spec["namespace"]
        state["output_index"] = len(self.response["output"])
        self.response["output"].append(item)
        return [self.event("response.output_item.added", output_index=state["output_index"], item=item)]

    def feed(self, chunk: dict[str, Any]) -> list[dict[str, Any]]:
        if chunk.get("error") or chunk.get("type") == "error":
            error = chunk.get("error", chunk)
            raise ConversionError(error.get("message", "Upstream Chat Completions error.") if isinstance(error, dict) else str(error))
        if chunk.get("model"):
            self.response["model"] = chunk["model"]
        if isinstance(chunk.get("usage"), dict):
            self.response["usage"] = _usage(chunk["usage"])
        choices = chunk.get("choices", [])
        if not isinstance(choices, list):
            raise ConversionError("Upstream Chat Completions choices must be a list.")
        events = []
        for choice in choices:
            if not isinstance(choice, dict):
                raise ConversionError("Upstream Chat Completions choice must be an object.")
            if choice.get("index", 0) != 0:
                continue
            delta = choice.get("delta", {})
            if not isinstance(delta, dict):
                raise ConversionError("Upstream Chat Completions delta must be an object.")
            for key in ("content", "refusal"):
                if delta.get(key) is not None and not isinstance(delta[key], str):
                    raise ConversionError(f"Upstream Chat Completions {key} must be a string.")
            calls = delta.get("tool_calls")
            if calls is not None and not isinstance(calls, list):
                raise ConversionError("Upstream Chat Completions tool_calls must be a list.")
            if self.finish_reason is not None and (delta.get("content") or delta.get("tool_calls") or delta.get("refusal")):
                raise ConversionError("Upstream sent output after its finish reason.")
            if isinstance(delta.get("content"), str) and delta["content"]:
                events.extend(self._text(delta["content"]))
            if isinstance(delta.get("refusal"), str) and delta["refusal"]:
                events.extend(self._text(delta["refusal"], refusal=True))
            for position, call in enumerate(calls or []):
                if not isinstance(call, dict):
                    raise ConversionError("Upstream tool call must be an object.")
                index = call.get("index", position)
                if isinstance(index, bool) or not isinstance(index, int) or index < 0:
                    raise ConversionError("Upstream tool call index must be a non-negative integer.")
                state = self.tools.setdefault(index, {"name": "", "call_id": "", "arguments": ""})
                if call.get("id") is not None and not isinstance(call["id"], str):
                    raise ConversionError("Upstream tool call id must be a string.")
                if call.get("id"):
                    state["call_id"] += call["id"]
                function = call.get("function") or {}
                if not isinstance(function, dict):
                    raise ConversionError("Upstream tool call function must be an object.")
                for key in ("name", "arguments"):
                    if function.get(key) is not None and not isinstance(function[key], str):
                        raise ConversionError(f"Upstream tool call {key} must be a string.")
                if function.get("name"):
                    state["name"] += function["name"]
                state["arguments"] += function.get("arguments") or ""
                # Buffer tool identities as well as arguments: providers may split
                # names and call IDs across chunks. Emit one consistent identity.
            if choice.get("finish_reason") is not None:
                self.finish_reason = choice["finish_reason"]
        return events

    def finish(self) -> list[dict[str, Any]]:
        if self.finish_reason is None:
            raise ConversionError("Upstream Chat Completions stream ended before a finish reason.")
        if self.finish_reason not in {"stop", "tool_calls", "function_call", "length", "content_filter"}:
            raise ConversionError(f"Upstream Chat Completions ended with {self.finish_reason!r}.")
        events = []
        incomplete = self.finish_reason in {"length", "content_filter"}
        for state in self.tools.values():
            events.extend(self._open_tool(state))
            item = self.response["output"][state["output_index"]]
            if item["type"] == "custom_tool_call":
                try:
                    arguments = json.loads(state["arguments"])
                    if not isinstance(arguments, dict) or not isinstance(arguments.get("input"), str):
                        raise ValueError("missing string input")
                except (ValueError, TypeError) as error:
                    raise ConversionError("Upstream custom tool arguments must contain a string 'input'.") from error
                item["input"] = arguments["input"]
                events.append(self.event("response.custom_tool_call_input.delta", item_id=item["id"], output_index=state["output_index"], delta=item["input"]))
                events.append(self.event("response.custom_tool_call_input.done", item_id=item["id"], output_index=state["output_index"], input=item["input"]))
            else:
                item["arguments"] = state["arguments"]
                if item["arguments"]:
                    events.append(self.event("response.function_call_arguments.delta", item_id=item["id"], output_index=state["output_index"], delta=item["arguments"]))
                events.append(self.event("response.function_call_arguments.done", item_id=item["id"], output_index=state["output_index"], arguments=item["arguments"], name=item["name"]))
        for output_index, item in enumerate(self.response["output"]):
            item["status"] = "incomplete" if incomplete else "completed"
            if item["type"] == "message":
                for content_index, part in enumerate(item["content"]):
                    common = {"item_id": item["id"], "output_index": output_index, "content_index": content_index}
                    if part["type"] == "output_text":
                        events.append(self.event("response.output_text.done", **common, text=part["text"], logprobs=[]))
                    else:
                        events.append(self.event("response.refusal.done", **common, refusal=part["refusal"]))
                    events.append(self.event("response.content_part.done", **common, part=part))
            events.append(self.event("response.output_item.done", output_index=output_index, item=item))
        self.response["status"] = "incomplete" if incomplete else "completed"
        if incomplete:
            self.response["incomplete_details"] = {"reason": "max_output_tokens" if self.finish_reason == "length" else "content_filter"}
        events.append(self.event("response.incomplete" if incomplete else "response.completed", response=self.response))
        return events

    def fail(self, message: str) -> dict[str, Any]:
        self.response["status"] = "failed"
        self.response["error"] = {"code": "upstream_error", "message": message}
        return self.event("response.failed", response=self.response)


def response_from_chat(document: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
    choices = document.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ConversionError("Upstream Chat Completions response has no choices.")
    choice = choices[0]
    message = choice.get("message")
    if not isinstance(message, dict):
        raise ConversionError("Upstream Chat Completions response has no message.")
    response = ChatResponse(body)
    response.feed({**document, "choices": [{"index": 0, "delta": message, "finish_reason": choice.get("finish_reason")}]})
    response.finish()
    return response.response


async def _sse_data(content: Any) -> AsyncIterator[str]:
    """Read SSE records independently of TCP chunks, UTF-8 boundaries and CRLF."""
    pending = b""
    data: list[str] = []
    async for chunk in content.iter_any():
        pending += chunk
        while b"\n" in pending:
            line, pending = pending.split(b"\n", 1)
            line = line.rstrip(b"\r")
            if not line:
                if data:
                    yield "\n".join(data)
                    data = []
            elif line.startswith(b"data:"):
                value = line[5:]
                if value.startswith(b" "):
                    value = value[1:]
                data.append(value.decode("utf-8"))
    if pending.rstrip(b"\r").startswith(b"data:"):
        data.append(pending.rstrip(b"\r")[5:].lstrip(b" ").decode("utf-8"))
    if data:
        yield "\n".join(data)


def _encode_event(event: dict[str, Any]) -> bytes:
    return f"event: {event['type']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n".encode("utf-8")


async def stream_from_chat(content: Any, body: dict[str, Any]) -> AsyncIterator[bytes]:
    response = ChatResponse(body)
    for event in response.start():
        yield _encode_event(event)
    try:
        async for data in _sse_data(content):
            if data.strip() == "[DONE]":
                break
            chunk = json.loads(data)
            if not isinstance(chunk, dict):
                raise ConversionError("Upstream Chat Completions chunk must be an object.")
            for event in response.feed(chunk):
                yield _encode_event(event)
        for event in response.finish():
            yield _encode_event(event)
    except (ConversionError, ClientError, UnicodeError, ValueError, TypeError, KeyError) as error:
        yield _encode_event(response.fail(str(error)))
