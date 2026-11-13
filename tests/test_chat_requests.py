from __future__ import annotations

import copy
import json
import unittest

from copilot_lan_bridge.chat_requests import (
    ConversionError,
    custom_tool_names,
    responses_to_chat,
    tool_name_map,
)


class ChatRequestTests(unittest.TestCase):
    def test_instruction_roles_multimodal_and_generation_options(self) -> None:
        body = {
            "model": "gemini-test",
            "instructions": "Follow the policy.",
            "input": [
                {"role": "developer", "content": "Use tools carefully."},
                {"type": "message", "role": "system", "content": "Be brief."},
                {"role": "user", "content": [
                    {"type": "input_text", "text": "Describe this."},
                    {"type": "input_image", "image_url": "data:image/png;base64,AAAA", "detail": "low"},
                ]},
                {"type": "message", "id": "msg_1", "status": "completed", "role": "assistant", "phase": "commentary", "content": [
                    {"type": "output_text", "text": "Let me inspect it.", "annotations": []},
                ]},
                {"type": "reasoning", "id": "rs_1", "encrypted_content": "opaque", "summary": []},
            ],
            "stream": True,
            "max_output_tokens": 500,
            "temperature": 0.3,
            "top_p": 0.8,
            "parallel_tool_calls": False,
            "reasoning": {"effort": "high", "summary": "auto"},
            "store": False,
            "include": ["reasoning.encrypted_content"],
            "prompt_cache_key": "test-cache",
        }
        original = copy.deepcopy(body)
        converted = responses_to_chat(body)
        self.assertEqual(body, original)
        self.assertEqual(converted["messages"], [
            {"role": "system", "content": "Follow the policy."},
            {"role": "system", "content": "Use tools carefully."},
            {"role": "system", "content": "Be brief."},
            {"role": "user", "content": [
                {"type": "text", "text": "Describe this."},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA", "detail": "low"}},
            ]},
            {"role": "assistant", "content": [{"type": "text", "text": "Let me inspect it."}]},
        ])
        self.assertEqual(converted["max_tokens"], 500)
        self.assertEqual(converted["stream_options"], {"include_usage": True})
        self.assertEqual(converted["reasoning_effort"], "high")
        self.assertEqual(converted["temperature"], 0.3)
        self.assertEqual(converted["top_p"], 0.8)
        self.assertFalse(converted["parallel_tool_calls"])

    def test_string_input_and_nonstreaming(self) -> None:
        converted = responses_to_chat({"model": "gemini-test", "input": "Hello", "stream": False})
        self.assertEqual(converted, {"model": "gemini-test", "messages": [{"role": "user", "content": "Hello"}], "stream": False})

    def test_codex_client_metadata_and_output_metadata_do_not_reach_upstream(self) -> None:
        for metadata in ({"session_id": "test-session", "turn_id": "test-turn", "originator": "codex_cli_rs"}, None):
            with self.subTest(metadata=metadata):
                body = {
                    "model": "gemini-test",
                    "instructions": "You are a coding assistant.",
                    "input": [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Say hello."}]}],
                    "stream": True,
                    "store": False,
                    "include": ["reasoning.encrypted_content"],
                    "client_metadata": metadata,
                }
                original = copy.deepcopy(body)
                converted = responses_to_chat(body)
                self.assertEqual(body, original)
                self.assertEqual(converted["messages"], [
                    {"role": "system", "content": "You are a coding assistant."},
                    {"role": "user", "content": [{"type": "text", "text": "Say hello."}]},
                ])
                self.assertEqual(converted["stream_options"], {"include_usage": True})
                self.assertTrue(converted["stream"])
                for field in ("client_metadata", "include", "store"):
                    self.assertNotIn(field, converted)

    def test_codex_default_hosted_search_is_filtered_and_declared_unavailable(self) -> None:
        notice = "Hosted web search is unavailable through this bridge; do not claim to have searched the web."
        for kind in ("web_search", "web_search_preview"):
            with self.subTest(kind=kind):
                body = {
                    "model": "gemini-test",
                    "instructions": "You are a coding assistant.",
                    "input": "Explain this code.",
                    "stream": True,
                    "store": False,
                    "include": ["reasoning.encrypted_content"],
                    "client_metadata": {"originator": "codex_cli_rs"},
                    "tools": [
                        {"type": kind, "external_web_access": False, "search_content_types": ["text"]},
                        {"type": "function", "name": "shell", "parameters": {"type": "object"}},
                    ],
                }
                original = copy.deepcopy(body)
                converted = responses_to_chat(body)
                self.assertEqual(body, original)
                self.assertEqual(converted["messages"], [
                    {"role": "system", "content": "You are a coding assistant."},
                    {"role": "system", "content": notice},
                    {"role": "user", "content": "Explain this code."},
                ])
                self.assertEqual([tool["function"]["name"] for tool in converted["tools"]], ["shell"])
                self.assertEqual(tool_name_map(body), {"shell": {"type": "function", "name": "shell"}})
                with self.assertRaisesRegex(ConversionError, "tool_choice"):
                    responses_to_chat({**body, "tool_choice": {"type": kind}})
                with self.assertRaisesRegex(ConversionError, "tool type"):
                    responses_to_chat({**body, "tools": [{"type": "namespace", "name": "functions", "tools": [{"type": kind}]}]})
        without_search = responses_to_chat({"model": "m", "input": "Hi", "tools": [{"type": "image_generation"}]})
        self.assertEqual(without_search["messages"], [{"role": "user", "content": "Hi"}])
        self.assertNotIn("tools", without_search)

    def test_toolless_auto_or_none_tool_choice_is_omitted_for_chat(self) -> None:
        for tools_field in ({}, {"tools": []}, {"tools": [{"type": "web_search"}]}):
            for choice in ("auto", "none"):
                with self.subTest(tools_field=tools_field, choice=choice):
                    converted = responses_to_chat({
                        "model": "gemini-test",
                        "input": "Summarize this thread.",
                        "tool_choice": choice,
                        **tools_field,
                    })
                    self.assertNotIn("tools", converted)
                    self.assertNotIn("tool_choice", converted)
        with_tools = responses_to_chat({
            "model": "gemini-test",
            "input": "Hi",
            "tools": [{"type": "function", "name": "shell", "parameters": {"type": "object"}}],
            "tool_choice": "none",
        })
        self.assertEqual(with_tools["tool_choice"], "none")

    def test_text_verbosity_adds_preference_without_overwriting_instructions(self) -> None:
        preferences = {
            "low": "Keep responses concise.",
            "medium": "Use a moderate level of detail in responses.",
            "high": "Give detailed responses.",
        }
        for verbosity, preference in preferences.items():
            with self.subTest(verbosity=verbosity):
                body = {
                    "model": "gemini-test",
                    "instructions": "Follow the policy.",
                    "input": "Hello",
                    "text": {"verbosity": verbosity, "format": {"type": "json_object"}},
                }
                original = copy.deepcopy(body)
                converted = responses_to_chat(body)
                self.assertEqual(body, original)
                self.assertEqual(converted["messages"], [
                    {"role": "system", "content": "Follow the policy."},
                    {"role": "system", "content": preference},
                    {"role": "user", "content": "Hello"},
                ])
                self.assertNotIn("verbosity", converted)
                self.assertEqual(converted["response_format"], {"type": "json_object"})
        self.assertEqual(
            responses_to_chat({"model": "m", "input": "Hi", "text": {"verbosity": "low"}})["messages"],
            [{"role": "system", "content": preferences["low"]}, {"role": "user", "content": "Hi"}],
        )

    def test_function_and_custom_tool_history_retains_calls_and_outputs(self) -> None:
        body = {
            "model": "gemini-test",
            "tools": [
                {"type": "function", "name": "read", "description": "Read a file", "parameters": {"type": "object"}, "strict": False},
                {"type": "custom", "name": "apply_patch", "description": "Apply a patch", "format": {"type": "grammar", "syntax": "lark", "definition": "start: /.+/"}},
                {"type": "image_generation"},
            ],
            "tool_choice": {"type": "custom", "name": "apply_patch"},
            "input": [
                {"role": "user", "content": "Fix it"},
                {"type": "function_call", "id": "fc_1", "call_id": "call_1", "name": "read", "arguments": '{"path":"x"}'},
                {"type": "custom_tool_call", "call_id": "call_2", "name": "apply_patch", "input": "*** Begin Patch\n*** End Patch"},
                {"type": "function_call_output", "call_id": "call_1", "output": "contents"},
                {"type": "custom_tool_call_output", "call_id": "call_2", "output": [{"type": "input_text", "text": "Success"}]},
            ],
        }
        converted = responses_to_chat(body)
        assistant = converted["messages"][1]
        self.assertEqual(assistant["role"], "assistant")
        self.assertEqual(len(assistant["tool_calls"]), 2)
        self.assertEqual(assistant["tool_calls"][0]["id"], "call_1")
        self.assertEqual(json.loads(assistant["tool_calls"][1]["function"]["arguments"]), {"input": "*** Begin Patch\n*** End Patch"})
        self.assertEqual(converted["messages"][2], {"role": "tool", "tool_call_id": "call_1", "content": "contents"})
        self.assertEqual(converted["messages"][3]["content"], [{"type": "text", "text": "Success"}])
        self.assertEqual(len(converted["tools"]), 2)
        patch = converted["tools"][1]["function"]
        self.assertEqual(patch["parameters"]["properties"], {"input": {"type": "string"}})
        self.assertIn("start: /.+/", patch["description"])
        self.assertEqual(custom_tool_names(body), {"apply_patch"})
        self.assertEqual(converted["tool_choice"], {"type": "function", "function": {"name": "apply_patch"}})

    def test_namespaced_tools_history_and_choices_have_reversible_names(self) -> None:
        body = {
            "model": "gemini-test",
            "tools": [{"type": "namespace", "name": "functions", "description": "Local tools", "tools": [
                {"type": "function", "name": "shell", "parameters": {"type": "object"}},
                {"type": "custom", "name": "apply_patch", "format": {"type": "text"}},
            ]}],
            "input": [
                {"type": "function_call", "name": "shell", "namespace": "functions", "call_id": "c1", "arguments": "{}"},
                {"type": "custom_tool_call", "name": "apply_patch", "namespace": "functions", "call_id": "c2", "input": "patch"},
            ],
            "tool_choice": {"type": "function", "namespace": "functions", "name": "shell"},
        }
        converted = responses_to_chat(body)
        self.assertEqual(tool_name_map(body), {
            "functions__shell": {"type": "function", "name": "shell", "namespace": "functions"},
            "functions__apply_patch": {"type": "custom", "name": "apply_patch", "namespace": "functions"},
        })
        self.assertEqual(custom_tool_names(body), {"functions__apply_patch"})
        self.assertEqual(converted["tools"][0]["function"]["name"], "functions__shell")
        self.assertIn("Local tools", converted["tools"][0]["function"]["description"])
        self.assertEqual([call["function"]["name"] for call in converted["messages"][0]["tool_calls"]], ["functions__shell", "functions__apply_patch"])
        self.assertEqual(converted["tool_choice"]["function"]["name"], "functions__shell")

    def test_namespace_and_top_level_name_collision_is_rejected(self) -> None:
        with self.assertRaisesRegex(ConversionError, "collision"):
            responses_to_chat({"model": "gemini-test", "input": "Hi", "tools": [
                {"type": "function", "name": "functions__shell"},
                {"type": "namespace", "name": "functions", "tools": [{"type": "function", "name": "shell"}]},
            ]})

    def test_structured_output_is_nested_for_chat(self) -> None:
        format_spec = {"type": "json_schema", "name": "answer", "description": "An answer", "schema": {"type": "object", "properties": {"ok": {"type": "boolean"}}}, "strict": True}
        converted = responses_to_chat({"model": "gemini-test", "input": "Hi", "text": {"format": format_spec}})
        self.assertEqual(converted["response_format"], {"type": "json_schema", "json_schema": {key: value for key, value in format_spec.items() if key != "type"}})
        for kind in ("text", "json_object"):
            with self.subTest(kind=kind):
                self.assertEqual(responses_to_chat({"model": "m", "text": {"format": {"type": kind}}})["response_format"], {"type": kind})

    def test_unsupported_content_and_tools_fail_without_silently_discarding_input(self) -> None:
        invalid = [
            ({"previous_response_id": "resp_1"}, "previous_response_id"),
            ({"input": [{"type": "item_reference", "id": "msg_1"}]}, "item_reference"),
            ({"input": [{"role": "user", "content": [{"type": "input_file", "file_id": "file_1"}]}]}, "input_file"),
            ({"input": [{"role": "user", "content": [{"type": "input_image", "file_id": "file_1"}]}]}, "file_id"),
            ({"input": [{"type": "function_call_output", "call_id": "c", "output": [{"type": "input_image", "image_url": "https://example.com/image.png"}]}]}, "user messages"),
            ({"tools": [{"type": "file_search"}]}, "file_search"),
            ({"tools": [{"type": "function", "name": "f", "future_field": True}]}, "future_field"),
            ({"input": [{"role": "user", "content": "Hi", "unknown": "content"}]}, "unknown"),
            ({"unknown_request_field": "content"}, "unknown_request_field"),
            ({"tool_choice": {"type": "function", "name": "missing"}}, "undeclared"),
            ({"tools": [], "tool_choice": "required"}, "required"),
            ({"text": {"verbosity": "invalid"}}, "verbosity"),
            ({"text": {"verbosity": []}}, "verbosity"),
            ({"background": True}, "background"),
            ({"truncation": "auto"}, "truncation"),
            ({"input": None}, "input"),
            ({"max_output_tokens": True}, "positive integer"),
            ({"stream": "yes"}, "boolean"),
            ({"client_metadata": []}, "client_metadata"),
            ({"client_metadata": "metadata"}, "client_metadata"),
            ({"tools": [{"type": []}]}, "tool type"),
            ({"input": [{"type": []}]}, "item type"),
            ({"input": [{"role": []}]}, "role"),
            ({"input": [{"role": "user", "content": [{"type": []}]}]}, "content type"),
            ({"truncation": {}}, "truncation"),
            ({"text": {"format": {"type": []}}}, "text.format"),
        ]
        for overrides, message in invalid:
            with self.subTest(overrides=overrides):
                with self.assertRaisesRegex(ConversionError, message):
                    responses_to_chat({"model": "gemini-test", "input": "Hi", **overrides})


if __name__ == "__main__":
    unittest.main()
