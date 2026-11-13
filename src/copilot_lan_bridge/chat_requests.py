"""Translate stateless Responses requests to Chat Completions requests.

Responses item identifiers, reasoning history, and output/cache metadata have no
Chat equivalent. They do not change the supplied conversation and are ignored.
Inputs and tool types that would lose conversation content are rejected instead.
"""

from __future__ import annotations

import copy
import json
import re
from typing import Any


class ConversionError(ValueError):
    """The request cannot be represented safely by Chat Completions."""


_NAME = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
_ITEM_METADATA = {"id", "status"}
_HOSTED_SEARCH_TYPES = ("web_search", "web_search_preview")
_HOSTED_SEARCH_NOTICE = "Hosted web search is unavailable through this bridge; do not claim to have searched the web."
_VERBOSITY_INSTRUCTIONS = {
    "low": "Keep responses concise.",
    "medium": "Use a moderate level of detail in responses.",
    "high": "Give detailed responses.",
}
_REQUEST_FIELDS = {
    "model", "input", "instructions", "tools", "tool_choice", "parallel_tool_calls",
    "max_output_tokens", "temperature", "top_p", "reasoning", "text", "stream",
    "previous_response_id", "metadata", "store", "include", "prompt_cache_key",
    "prompt_cache_retention", "safety_identifier", "user", "service_tier", "background",
    "truncation", "stream_options", "conversation", "prompt", "max_tool_calls",
    "context_management", "client_metadata",
}


def _check_fields(value: dict[str, Any], allowed: set[str], context: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ConversionError(f"Unsupported {context} field(s): {', '.join(sorted(unknown))}.")


def _string(value: Any, context: str, *, empty: bool = True) -> str:
    if not isinstance(value, str) or (not empty and not value):
        raise ConversionError(f"{context} must be a {'non-empty ' if not empty else ''}string.")
    return value


def _tool_name(name: Any, namespace: Any = None) -> str:
    if not isinstance(name, str) or not _NAME.fullmatch(name):
        raise ConversionError("Tool names must contain 1–64 letters, digits, underscores, or hyphens.")
    if namespace is None:
        return name
    if not isinstance(namespace, str) or not _NAME.fullmatch(namespace):
        raise ConversionError("Tool namespaces must contain 1–64 letters, digits, underscores, or hyphens.")
    encoded = f"{namespace}__{name}"
    if len(encoded) > 64:
        raise ConversionError(f"Namespaced tool name '{encoded}' exceeds the Chat Completions 64-character limit.")
    return encoded


def _tool_definitions(body: dict[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any], str | None]]:
    tools = body.get("tools")
    if tools is None:
        return []
    if not isinstance(tools, list):
        raise ConversionError("tools must be a list.")
    definitions: list[tuple[dict[str, Any], dict[str, Any], str | None]] = []
    seen: set[str] = set()

    def add(tool: Any, namespace: str | None = None, description: str | None = None) -> None:
        if not isinstance(tool, dict):
            raise ConversionError("Each tool must be an object.")
        kind = tool.get("type")
        if namespace is None and kind in ("image_generation", *_HOSTED_SEARCH_TYPES):
            return  # Hosted tools cannot be invoked through Chat Completions.
        if kind == "namespace" and namespace is None:
            _check_fields(tool, {"type", "name", "description", "tools"}, "namespace tool")
            namespace_name = _tool_name(tool.get("name"))
            nested = tool.get("tools")
            if not isinstance(nested, list) or not nested:
                raise ConversionError("A namespace tool must contain a non-empty tools list.")
            namespace_description = tool.get("description")
            if namespace_description is not None:
                _string(namespace_description, "Namespace description")
            for child in nested:
                add(child, namespace_name, namespace_description)
            return
        if kind not in ("function", "custom"):
            raise ConversionError(f"Unsupported tool type '{kind}' for Chat Completions.")
        name = _tool_name(tool.get("name"), namespace)
        if name in seen:
            raise ConversionError(f"Tool name collision after namespace conversion: '{name}'.")
        seen.add(name)
        entry: dict[str, Any] = {"type": kind, "name": tool["name"]}
        if namespace is not None:
            entry["namespace"] = namespace
        definitions.append((tool, entry, description))

    for tool in tools:
        add(tool)
    return definitions


def tool_name_map(body: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Map Chat names to original Responses tool type, name, and namespace."""
    return {
        _tool_name(entry["name"], entry.get("namespace")): dict(entry)
        for _, entry, _ in _tool_definitions(body)
    }


def custom_tool_names(body: dict[str, Any]) -> set[str]:
    """Return encoded Chat names for tools whose Responses type is custom."""
    return {name for name, entry in tool_name_map(body).items() if entry["type"] == "custom"}


def _chat_tools(body: dict[str, Any]) -> list[dict[str, Any]]:
    converted: list[dict[str, Any]] = []
    for tool, entry, namespace_description in _tool_definitions(body):
        kind = entry["type"]
        allowed = {"type", "name", "description", "parameters", "strict"} if kind == "function" else {
            "type", "name", "description", "format",
        }
        _check_fields(tool, allowed, f"{kind} tool")
        function: dict[str, Any] = {"name": _tool_name(entry["name"], entry.get("namespace"))}
        description = tool.get("description", "")
        _string(description, "Tool description")
        if namespace_description:
            description = f"{namespace_description}\n\n{description}".strip()
        if kind == "function":
            if description:
                function["description"] = description
            if tool.get("parameters") is not None:
                if not isinstance(tool["parameters"], dict):
                    raise ConversionError("Function parameters must be a JSON Schema object.")
                function["parameters"] = copy.deepcopy(tool["parameters"])
            if tool.get("strict") is not None:
                if not isinstance(tool["strict"], bool):
                    raise ConversionError("Function strict must be a boolean.")
                function["strict"] = tool["strict"]
        else:
            instructions = "Pass the complete free-form tool input as the JSON string argument `input`."
            format_spec = tool.get("format")
            if format_spec is not None:
                if not isinstance(format_spec, dict) or format_spec.get("type") not in ("text", "grammar"):
                    raise ConversionError("A custom tool format must have type 'text' or 'grammar'.")
                if format_spec["type"] == "text":
                    _check_fields(format_spec, {"type"}, "custom text format")
                else:
                    _check_fields(format_spec, {"type", "syntax", "definition"}, "custom grammar format")
                    if format_spec.get("syntax") not in ("lark", "regex"):
                        raise ConversionError("A custom grammar syntax must be 'lark' or 'regex'.")
                    _string(format_spec.get("definition"), "Custom grammar definition", empty=False)
                    instructions += " The input must satisfy this format: " + json.dumps(format_spec, ensure_ascii=False)
            function["description"] = f"{description}\n\n{instructions}".strip()
            function["parameters"] = {
                "type": "object",
                "properties": {"input": {"type": "string"}},
                "required": ["input"],
                "additionalProperties": False,
            }
        converted.append({"type": "function", "function": function})
    return converted


def _content(value: Any, role: str) -> str | list[dict[str, Any]]:
    if isinstance(value, str):
        return value
    if not isinstance(value, list):
        raise ConversionError("Message content must be a string or content list.")
    parts: list[dict[str, Any]] = []
    for part in value:
        if not isinstance(part, dict):
            raise ConversionError("Each message content part must be an object.")
        kind = part.get("type")
        if kind in ("input_text", "output_text", "text"):
            _check_fields(part, {"type", "text", "annotations", "logprobs"}, "text content")
            parts.append({"type": "text", "text": _string(part.get("text"), "Content text")})
        elif kind == "input_image":
            _check_fields(part, {"type", "image_url", "detail", "file_id"}, "image content")
            if role != "user":
                raise ConversionError("Chat Completions only supports input images in user messages.")
            if part.get("file_id") is not None:
                raise ConversionError("Image file_id cannot be translated; provide an image_url or data URL.")
            image: dict[str, Any] = {"url": _string(part.get("image_url"), "Image URL", empty=False)}
            if part.get("detail") is not None:
                if part["detail"] not in ("auto", "low", "high"):
                    raise ConversionError("Image detail must be 'auto', 'low', or 'high'.")
                image["detail"] = part["detail"]
            parts.append({"type": "image_url", "image_url": image})
        else:
            raise ConversionError(f"Unsupported input content type '{kind}' for Chat Completions.")
    return parts


def _call(messages: list[dict[str, Any]], item: dict[str, Any], *, custom: bool) -> None:
    kind = "custom_tool_call" if custom else "function_call"
    _check_fields(item, _ITEM_METADATA | {"type", "call_id", "name", "namespace", "arguments" if not custom else "input"}, kind)
    name = _tool_name(item.get("name"), item.get("namespace"))
    if custom:
        arguments = json.dumps({"input": _string(item.get("input"), "Custom tool input")}, ensure_ascii=False)
    else:
        arguments = _string(item.get("arguments"), "Function arguments")
    tool_call = {
        "id": _string(item.get("call_id"), "Tool call_id", empty=False),
        "type": "function",
        "function": {"name": name, "arguments": arguments},
    }
    if not messages or messages[-1]["role"] != "assistant":
        messages.append({"role": "assistant", "content": None, "tool_calls": []})
    messages[-1].setdefault("tool_calls", []).append(tool_call)


def _messages(body: dict[str, Any]) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    instructions = body.get("instructions")
    if instructions is not None:
        messages.append({"role": "system", "content": _string(instructions, "instructions")})
    tools = body.get("tools")
    if isinstance(tools, list) and any(isinstance(tool, dict) and tool.get("type") in _HOSTED_SEARCH_TYPES for tool in tools):
        messages.append({"role": "system", "content": _HOSTED_SEARCH_NOTICE})
    text = body.get("text")
    if isinstance(text, dict) and text.get("verbosity") is not None:
        verbosity = text["verbosity"]
        if not isinstance(verbosity, str) or verbosity not in _VERBOSITY_INSTRUCTIONS:
            raise ConversionError("text.verbosity must be 'low', 'medium', or 'high'.")
        messages.append({"role": "system", "content": _VERBOSITY_INSTRUCTIONS[verbosity]})
    input_value = body.get("input", [])
    if isinstance(input_value, str):
        messages.append({"role": "user", "content": input_value})
        return messages
    if not isinstance(input_value, list):
        raise ConversionError("input must be a string or a list of Responses items.")
    for item in input_value:
        if not isinstance(item, dict):
            raise ConversionError("Each input item must be an object.")
        kind = item.get("type", "message" if "role" in item else None)
        if kind == "reasoning":
            continue  # Opaque reasoning state cannot be consumed by Chat Completions.
        if kind == "message":
            _check_fields(item, _ITEM_METADATA | {"type", "role", "content", "phase"}, "message")
            role = item.get("role")
            if role not in ("system", "developer", "user", "assistant"):
                raise ConversionError(f"Unsupported message role '{role}'.")
            messages.append({"role": "system" if role == "developer" else role, "content": _content(item.get("content"), role)})
        elif kind in ("function_call", "custom_tool_call"):
            _call(messages, item, custom=kind == "custom_tool_call")
        elif kind in ("function_call_output", "custom_tool_call_output"):
            _check_fields(item, _ITEM_METADATA | {"type", "call_id", "output"}, kind)
            messages.append({
                "role": "tool",
                "tool_call_id": _string(item.get("call_id"), "Tool output call_id", empty=False),
                "content": _content(item.get("output"), "tool"),
            })
        else:
            raise ConversionError(f"Unsupported input item type '{kind}' for Chat Completions.")
    return messages


def _tool_choice(value: Any, names: dict[str, dict[str, Any]]) -> Any:
    if isinstance(value, str) and value in {"auto", "none", "required"}:
        if not names:
            if value == "required":
                raise ConversionError("tool_choice 'required' requires at least one supported tool.")
            return None
        return value
    if not isinstance(value, dict):
        raise ConversionError("tool_choice must be 'auto', 'none', 'required', or a named function/custom tool.")
    _check_fields(value, {"type", "name", "namespace"}, "tool_choice")
    if value.get("type") not in ("function", "custom"):
        raise ConversionError(f"Unsupported tool_choice type '{value.get('type')}'.")
    name = _tool_name(value.get("name"), value.get("namespace"))
    if name not in names:
        raise ConversionError(f"tool_choice refers to undeclared tool '{name}'.")
    if names[name]["type"] != value["type"]:
        raise ConversionError(f"tool_choice type does not match declared tool '{name}'.")
    return {"type": "function", "function": {"name": name}}


def _response_format(text: Any) -> dict[str, Any] | None:
    if text is None:
        return None
    if not isinstance(text, dict):
        raise ConversionError("text must be an object.")
    _check_fields(text, {"format", "verbosity"}, "text configuration")
    format_spec = text.get("format")
    if format_spec is None:
        return None
    if not isinstance(format_spec, dict):
        raise ConversionError("text.format must be an object.")
    kind = format_spec.get("type")
    if kind in ("text", "json_object"):
        _check_fields(format_spec, {"type"}, "text format")
        return {"type": kind}
    if kind == "json_schema":
        _check_fields(format_spec, {"type", "name", "description", "schema", "strict"}, "JSON schema format")
        _string(format_spec.get("name"), "JSON schema name", empty=False)
        if not isinstance(format_spec.get("schema"), dict):
            raise ConversionError("text.format.schema must be a JSON Schema object.")
        schema = {key: copy.deepcopy(value) for key, value in format_spec.items() if key != "type" and value is not None}
        if "description" in schema:
            _string(schema["description"], "JSON schema description")
        if "strict" in schema and not isinstance(schema["strict"], bool):
            raise ConversionError("JSON schema strict must be a boolean.")
        return {"type": "json_schema", "json_schema": schema}
    raise ConversionError(f"Unsupported text.format type '{kind}'.")


def responses_to_chat(body: dict[str, Any]) -> dict[str, Any]:
    """Translate a complete, stateless Responses request, or raise ConversionError."""
    if not isinstance(body, dict):
        raise ConversionError("The Responses request must be an object.")
    _check_fields(body, _REQUEST_FIELDS, "Responses request")
    if body.get("client_metadata") is not None and not isinstance(body["client_metadata"], dict):
        raise ConversionError("client_metadata must be an object or null.")
    if body.get("previous_response_id"):
        raise ConversionError("previous_response_id is not supported for Chat Completions models; send the full conversation in input.")
    if body.get("conversation"):
        raise ConversionError("conversation is not supported; send the full conversation in input.")
    if body.get("prompt"):
        raise ConversionError("Stored prompt references are not supported; provide instructions and input directly.")
    if body.get("background"):
        raise ConversionError("background responses are not supported by the Chat Completions adapter.")
    if body.get("truncation") not in (None, "disabled"):
        raise ConversionError("Automatic truncation is not supported; truncate the supplied conversation before sending it.")
    if body.get("max_tool_calls") is not None or body.get("context_management"):
        raise ConversionError("max_tool_calls and context_management are not supported by the Chat Completions adapter.")
    include = body.get("include")
    if include is not None and (not isinstance(include, list) or any(entry != "reasoning.encrypted_content" for entry in include)):
        raise ConversionError("Only the optional reasoning.encrypted_content include metadata is accepted by the Chat Completions adapter.")
    converted: dict[str, Any] = {
        "model": _string(body.get("model"), "model", empty=False),
        "messages": _messages(body),
    }
    tools = _chat_tools(body)
    if tools:
        converted["tools"] = tools
    if body.get("tool_choice") is not None:
        choice = _tool_choice(body["tool_choice"], tool_name_map(body))
        if choice is not None:
            converted["tool_choice"] = choice
    for key in ("stream", "parallel_tool_calls"):
        if key in body:
            if not isinstance(body[key], bool):
                raise ConversionError(f"{key} must be a boolean.")
            converted[key] = body[key]
    if converted.get("stream"):
        converted["stream_options"] = {"include_usage": True}
    if body.get("max_output_tokens") is not None:
        limit = body["max_output_tokens"]
        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            raise ConversionError("max_output_tokens must be a positive integer.")
        converted["max_tokens"] = limit
    for key in ("temperature", "top_p"):
        if body.get(key) is not None:
            if isinstance(body[key], bool) or not isinstance(body[key], (int, float)):
                raise ConversionError(f"{key} must be a number.")
            converted[key] = body[key]
    reasoning = body.get("reasoning")
    if reasoning is not None:
        if not isinstance(reasoning, dict):
            raise ConversionError("reasoning must be an object.")
        _check_fields(reasoning, {"effort", "summary", "generate_summary"}, "reasoning configuration")
        if reasoning.get("effort") is not None:
            converted["reasoning_effort"] = _string(reasoning["effort"], "reasoning.effort", empty=False)
    response_format = _response_format(body.get("text"))
    if response_format is not None:
        converted["response_format"] = response_format
    if body.get("user") is not None:
        converted["user"] = _string(body["user"], "user")
    return converted
