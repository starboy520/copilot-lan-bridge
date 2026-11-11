from __future__ import annotations

import copy
import io
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from copilot_lan_bridge.codex_catalog import CatalogError, build_catalog, main


def bundled_catalog() -> dict:
    return {"models": [
        {
            "slug": "gpt-6-test",
            "display_name": "Native Test Model",
            "tool_mode": "code_mode_only",
            "use_responses_lite": True,
            "visibility": "list",
            "custom_native_metadata": {"preserve": True},
            "model_messages": {"instructions_template": "Native instructions"},
        },
        {
            "slug": "gpt-5.5",
            "display_name": "Ordinary Template",
            "description": "Template",
            "tool_mode": None,
            "use_responses_lite": False,
            "prefer_websockets": True,
            "visibility": "list",
            "supported_in_api": True,
            "default_reasoning_level": "medium",
            "supported_reasoning_levels": [{"effort": "xhigh", "description": "Extra high"}],
            "shell_type": "shell_command",
            "apply_patch_tool_type": "freeform",
            "truncation_policy": {"mode": "tokens", "limit": 10000},
            "context_window": 272000,
            "supports_image_detail_original": True,
            "supports_search_tool": True,
            "experimental_supported_tools": ["clock"],
            "multi_agent_version": "v2",
            "multi_agent_reasoning_effort": "xhigh",
            "service_tiers": [{"id": "priority"}],
            "additional_speed_tiers": ["fast"],
            "default_service_tier": "priority",
            "upgrade": {"model": "gpt-6-test"},
            "model_messages": {"instructions_template": "Use ordinary tools safely."},
        },
    ]}


class CatalogTests(unittest.TestCase):
    def test_only_bridge_available_models_are_exported_and_native_metadata_is_preserved(self) -> None:
        bundled = bundled_catalog()
        upstream = [
            {"id": "gpt-6-test", "name": "Upstream name", "supported_endpoints": ["/responses"]},
            {"id": "gemini-test", "supported_endpoints": ["/chat/completions"]},
            {"id": "disabled", "supported_endpoints": ["/chat/completions"], "policy": {"state": "disabled"}},
            {"id": "messages-only", "supported_endpoints": ["/v1/messages"]},
            {"id": "unknown", "supported_endpoints": []},
            {"id": " ", "supported_endpoints": ["/responses"]},
            {"id": "gemini-test", "supported_endpoints": ["/chat/completions"]},
            None,
        ]
        bundled_original, upstream_original = copy.deepcopy(bundled), copy.deepcopy(upstream)
        result = build_catalog(upstream, bundled)
        self.assertEqual([model["slug"] for model in result["models"]], ["gpt-6-test", "gemini-test"])
        self.assertEqual(result["models"][0], bundled["models"][0])
        self.assertEqual(bundled, bundled_original)
        self.assertEqual(upstream, upstream_original)
        result["models"][0]["custom_native_metadata"]["preserve"] = False
        self.assertTrue(bundled["models"][0]["custom_native_metadata"]["preserve"])

    def test_gemini_uses_ordinary_tools_and_upstream_prompt_and_image_capabilities(self) -> None:
        result = build_catalog([{
            "id": "gemini-test",
            "name": "Gemini Test",
            "supported_endpoints": ["/chat/completions"],
            "capabilities": {
                "type": "chat",
                "limits": {"max_context_window_tokens": 1048576, "max_prompt_tokens": 128000, "max_output_tokens": 64000},
                "supports": {"vision": True},
            },
        }], bundled_catalog())["models"][0]
        self.assertEqual(result["display_name"], "Gemini Test")
        self.assertEqual(result["context_window"], 128000)
        self.assertEqual(result["max_context_window"], 128000)
        self.assertEqual(result["auto_compact_token_limit"], 102400)
        self.assertEqual(result["input_modalities"], ["text", "image"])
        self.assertEqual(result["model_messages"], {"instructions_template": "Use ordinary tools safely."})
        self.assertIsNone(result["tool_mode"])
        self.assertEqual(result["visibility"], "list")
        self.assertTrue(result["supported_in_api"])
        for capability in ("use_responses_lite", "prefer_websockets", "supports_search_tool", "supports_image_detail_original", "supports_reasoning_effort_updates", "supports_reasoning_summaries"):
            with self.subTest(capability=capability):
                self.assertFalse(result[capability])
        for capability in ("experimental_supported_tools", "service_tiers", "additional_speed_tiers"):
            with self.subTest(capability=capability):
                self.assertEqual(result[capability], [])
        self.assertIsNone(result["multi_agent_version"])
        self.assertIsNone(result["default_service_tier"])
        self.assertIsNone(result["upgrade"])
        self.assertEqual(result["default_reasoning_level"], "low")
        self.assertEqual([level["effort"] for level in result["supported_reasoning_levels"]], ["low", "medium", "high"])

    def test_chat_model_with_matching_bundled_id_still_disables_native_only_features(self) -> None:
        model = build_catalog([{"id": "gpt-6-test", "supported_endpoints": ["/chat/completions"]}], bundled_catalog())["models"][0]
        self.assertIsNone(model["tool_mode"])
        self.assertFalse(model["use_responses_lite"])
        self.assertEqual(model["model_messages"], {"instructions_template": "Use ordinary tools safely."})

    def test_context_and_modalities_fallbacks_do_not_inherit_gpt_limits(self) -> None:
        cases = [
            ({}, 32768, ["text"]),
            ({"capabilities": {"limits": {"max_context_window_tokens": 200000}, "input_modalities": ["text", "image", "audio"]}}, 200000, ["text", "image"]),
            ({"capabilities": {"limits": {"max_prompt_tokens": -1, "max_context_window_tokens": True}}}, 32768, ["text"]),
            ({"capabilities": {"supports": {"vision": False}, "input_modalities": ["text", "image"]}}, 32768, ["text"]),
        ]
        for metadata, window, modalities in cases:
            with self.subTest(metadata=metadata):
                model = build_catalog([{"id": "gemini", "supported_endpoints": ["/chat/completions"], **metadata}], bundled_catalog())["models"][0]
                self.assertEqual(model["context_window"], window)
                self.assertEqual(model["input_modalities"], modalities)

    def test_code_mode_only_catalog_is_not_used_as_a_gemini_template(self) -> None:
        with self.assertRaisesRegex(CatalogError, "ordinary-tool template"):
            build_catalog([{"id": "gemini", "supported_endpoints": ["/chat/completions"]}], {"models": [bundled_catalog()["models"][0]]})
        with self.assertRaisesRegex(CatalogError, "available"):
            build_catalog([], bundled_catalog())


class CatalogCLITests(unittest.TestCase):
    def test_cli_writes_atomic_catalog_and_keeps_api_key_out_of_output(self) -> None:
        token = "test-token-must-not-appear-in-output"
        with tempfile.TemporaryDirectory() as directory:
            key_file = Path(directory) / "api-key"
            key_file.write_text(token + "\n", encoding="utf-8")
            output = Path(directory) / "catalog.json"
            output.write_text('{"old":true}', encoding="utf-8")
            model_document = {"data": [{"id": "gemini-test", "supported_endpoints": ["/chat/completions"]}]}
            captured = io.StringIO()
            with patch("copilot_lan_bridge.codex_catalog.subprocess.run", return_value=subprocess.CompletedProcess([], 0, json.dumps(bundled_catalog()), "")) as run:
                with patch("copilot_lan_bridge.codex_catalog.urlopen", return_value=io.BytesIO(json.dumps(model_document).encode())) as open_url:
                    with redirect_stdout(captured), redirect_stderr(captured):
                        code = main(["--base-url", "http://127.0.0.1:18787/v1/", "--api-key-file", str(key_file), "--output", str(output)])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(output.read_text())["models"][0]["slug"], "gemini-test")
            self.assertEqual(open_url.call_args.args[0].full_url, "http://127.0.0.1:18787/v1/models")
            self.assertEqual(open_url.call_args.args[0].get_header("Authorization"), f"Bearer {token}")
            self.assertEqual(run.call_args.args[0], ["codex", "debug", "models", "--bundled"])
            self.assertNotIn(token, captured.getvalue())
            self.assertNotIn(token, output.read_text())
            self.assertEqual(sorted(path.name for path in Path(directory).iterdir()), ["api-key", "catalog.json"])
            if os.name != "nt":
                self.assertEqual(output.stat().st_mode & 0o777, 0o600)

    def test_old_codex_failure_does_not_replace_catalog_or_echo_subprocess_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "catalog.json"
            output.write_text("original", encoding="utf-8")
            captured = io.StringIO()
            with patch("copilot_lan_bridge.codex_catalog.subprocess.run", return_value=subprocess.CompletedProcess([], 2, "private-output", "private-error")):
                with redirect_stderr(captured):
                    code = main(["--base-url", "http://127.0.0.1:18787/v1", "--api-key-file", "unused", "--output", str(output)])
            self.assertEqual(code, 2)
            self.assertEqual(output.read_text(), "original")
            self.assertIn("supports this command", captured.getvalue())
            self.assertNotIn("private", captured.getvalue())

    def test_http_failure_does_not_echo_response_or_replace_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            key_file = Path(directory) / "api-key"
            key_file.write_text("token-not-for-output", encoding="utf-8")
            output = Path(directory) / "catalog.json"
            output.write_text("original", encoding="utf-8")
            captured = io.StringIO()
            failure = HTTPError("http://127.0.0.1:18787/v1/models", 401, "token-not-for-output", {}, io.BytesIO(b"token-not-for-output"))
            with patch("copilot_lan_bridge.codex_catalog.subprocess.run", return_value=subprocess.CompletedProcess([], 0, json.dumps(bundled_catalog()), "")):
                with patch("copilot_lan_bridge.codex_catalog.urlopen", side_effect=failure):
                    with redirect_stderr(captured):
                        code = main(["--base-url", "http://127.0.0.1:18787/v1", "--api-key-file", str(key_file), "--output", str(output)])
            self.assertEqual(code, 2)
            self.assertIn("HTTP 401", captured.getvalue())
            self.assertNotIn("token-not-for-output", captured.getvalue())
            self.assertEqual(output.read_text(), "original")


if __name__ == "__main__":
    unittest.main()
