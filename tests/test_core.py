from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from copilot_lan_bridge.config import ConfigError, Settings, is_loopback_host
from copilot_lan_bridge.credentials import CredentialError, load_copilot_credential
from copilot_lan_bridge.models import supports_responses, visible_models
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
    def test_filters_models_without_native_responses(self) -> None:
        models = [
            {"id": "gpt", "name": "GPT", "supported_endpoints": ["/responses"]},
            {"id": "claude", "supported_endpoints": ["/v1/messages"]},
            {"id": "disabled", "supported_endpoints": ["/responses"], "policy": {"state": "disabled"}},
        ]
        self.assertTrue(supports_responses(models[0]))
        self.assertEqual([model["id"] for model in visible_models(models)], ["gpt"])


if __name__ == "__main__":
    unittest.main()