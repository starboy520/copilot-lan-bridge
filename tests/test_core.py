from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from copilot_lan_bridge.config import ConfigError, Settings, is_loopback_host
from copilot_lan_bridge.credentials import CredentialError, load_copilot_credential
from copilot_lan_bridge.models import is_available, supports_chat_completions, supports_responses, visible_models
from copilot_lan_bridge.security import is_authorized


class ConfigTests(unittest.TestCase):
    def test_loopback_detection(self) -> None:
        self.assertTrue(is_loopback_host("127.0.0.1"))
        self.assertTrue(is_loopback_host("::1"))
        self.assertTrue(is_loopback_host("localhost"))
        self.assertFalse(is_loopback_host("0.0.0.0"))
        self.assertFalse(is_loopback_host("192.168.1.20"))

    def test_lan_listener_requires_long_api_key(self) -> None:
        with patch.dict(os.environ, {"COPILOT_BRIDGE_HOST": "0.0.0.0"}):
            os.environ.pop("COPILOT_BRIDGE_API_KEY", None)
            with self.assertRaises(ConfigError):
                Settings.from_env()
        with patch.dict(
            os.environ,
            {"COPILOT_BRIDGE_HOST": "0.0.0.0", "COPILOT_BRIDGE_API_KEY": "x" * 32},
        ):
            self.assertEqual(Settings.from_env().host, "0.0.0.0")


class SecurityTests(unittest.TestCase):
    def test_bearer_authentication(self) -> None:
        key = "a-secure-key-containing-32-characters"
        self.assertTrue(is_authorized(f"Bearer {key}", key))
        self.assertTrue(is_authorized(None, None))
        self.assertFalse(is_authorized(None, key))
        self.assertFalse(is_authorized("Bearer wrong", key))
        self.assertFalse(is_authorized(f"Basic {key}", key))


class CredentialTests(unittest.TestCase):
    def test_loads_opencode_copilot_credential(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "auth.json"
            path.write_text(
                json.dumps({"github-copilot": {"type": "oauth", "refresh": "secret-token"}}),
                encoding="utf-8",
            )
            self.assertEqual(load_copilot_credential(path).token, "secret-token")

    def test_rejects_missing_copilot_entry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "auth.json"
            path.write_text("{}", encoding="utf-8")
            with self.assertRaises(CredentialError):
                load_copilot_credential(path)


class ModelTests(unittest.TestCase):
    def test_lists_native_and_chat_models_but_excludes_unavailable_models(self) -> None:
        models = [
            {"id": "gpt", "name": "GPT", "supported_endpoints": ["/responses"]},
            {"id": "gemini", "name": "Gemini", "supported_endpoints": ["/chat/completions"], "policy": {"state": "enabled"}},
            {"id": "claude", "supported_endpoints": ["/v1/messages"]},
            {"id": "disabled", "supported_endpoints": ["/responses"], "policy": {"state": "disabled"}},
            {"id": "disabled-chat", "supported_endpoints": ["/chat/completions"], "policy": {"state": "disabled"}},
            {"id": "unknown", "supported_endpoints": ["/unknown"]},
            {"id": "", "supported_endpoints": ["/responses"]},
            {"id": " ", "supported_endpoints": ["/chat/completions"]},
            {"supported_endpoints": ["/chat/completions"]},
        ]
        self.assertTrue(supports_responses(models[0]))
        self.assertTrue(supports_chat_completions(models[1]))
        visible = visible_models(models)
        self.assertEqual([model["id"] for model in visible], ["gpt", "gemini"])
        self.assertEqual(visible[1]["supported_endpoints"], ["/chat/completions"])
        self.assertEqual(visible[1]["display_name"], "Gemini")
        self.assertNotIn("slug", models[1])
        self.assertTrue(all(is_available(model) for model in models[:2]))
        self.assertTrue(all(not is_available(model) for model in models[2:]))

    def test_normalizes_endpoint_prefix_case_and_whitespace(self) -> None:
        for endpoint in ("/responses", " /V1/Responses ", "responses"):
            with self.subTest(endpoint=endpoint):
                self.assertTrue(supports_responses({"supported_endpoints": [endpoint]}))
        for endpoint in ("/chat/completions", " /V1/Chat/Completions ", "chat/completions"):
            with self.subTest(endpoint=endpoint):
                self.assertTrue(supports_chat_completions({"supported_endpoints": [endpoint]}))

    def test_ignores_invalid_endpoint_metadata(self) -> None:
        for endpoints in (None, "/responses", [None, 42, " ", "/messages"]):
            with self.subTest(endpoints=endpoints):
                model = {"id": "invalid", "supported_endpoints": endpoints}
                self.assertFalse(supports_responses(model))
                self.assertFalse(supports_chat_completions(model))
                self.assertFalse(is_available(model))


if __name__ == "__main__":
    unittest.main()
