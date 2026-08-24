from __future__ import annotations

import base64
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from server.app import ApiError, RequestHandler, StudyAgentServer, parse_image_data_url
from server.bridge import extract_sse_text_event
from server.prompts import build_instructions
from server.storage import StudyStore


class StorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.store = StudyStore(Path(self.temp.name))

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_session_messages_and_delete(self) -> None:
        session = self.store.create_session()
        self.store.add_message(session["id"], "user", "什么是质数？")
        self.store.add_message(session["id"], "assistant", "质数只有两个正因数。")
        loaded = self.store.get_session(session["id"])
        self.assertIsNotNone(loaded)
        self.assertEqual("什么是质数？", loaded["title"])
        self.assertEqual(2, len(loaded["messages"]))
        self.assertTrue(self.store.delete_session(session["id"]))
        self.assertIsNone(self.store.get_session(session["id"]))

    def test_parent_pin(self) -> None:
        self.assertTrue(self.store.verify_pin("anything"))
        self.store.set_pin("1234")
        self.assertTrue(self.store.verify_pin("1234"))
        self.assertFalse(self.store.verify_pin("0000"))

    def test_reasoning_effort_setting(self) -> None:
        self.assertEqual("medium", self.store.get_settings()["reasoningEffort"])
        self.store.update_settings("junior", "concise", "guide", "high", "gpt-5.6-sol")
        self.assertEqual("high", self.store.get_settings()["reasoningEffort"])
        self.assertEqual("gpt-5.6-sol", self.store.get_settings()["model"])

    def test_custom_default_model_for_new_deployment(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = StudyStore(Path(temp), default_model="deployment-model")
            self.assertEqual("deployment-model", store.get_settings()["model"])

    def test_old_attachment_cleanup(self) -> None:
        raw = b"\x89PNG\r\n\x1a\ncontent"
        attachment_id = self.store.add_attachment(raw, "image/png", ".png")
        attachment = self.store.get_attachment(attachment_id)
        with self.store.connect() as db:
            db.execute("UPDATE attachments SET created_at='2000-01-01T00:00:00+00:00' WHERE id=?", (attachment_id,))
        self.assertEqual(1, self.store.cleanup_old_attachments())
        self.assertFalse(attachment[0].exists())


class InputValidationTests(unittest.TestCase):
    def test_valid_png(self) -> None:
        raw = b"\x89PNG\r\n\x1a\n" + b"content"
        value = "data:image/png;base64," + base64.b64encode(raw).decode()
        parsed = parse_image_data_url(value)
        self.assertEqual(raw, parsed[0])
        self.assertEqual("image/png", parsed[1])

    def test_rejects_mismatched_image(self) -> None:
        value = "data:image/png;base64," + base64.b64encode(b"not png").decode()
        with self.assertRaises(ApiError):
            parse_image_data_url(value)


class BridgeParserTests(unittest.TestCase):
    def test_delta_event(self) -> None:
        delta, done, error = extract_sse_text_event('{"type":"response.output_text.delta","delta":"你好"}')
        self.assertEqual("你好", delta)
        self.assertFalse(done)
        self.assertIsNone(error)

    def test_failed_event(self) -> None:
        _, done, error = extract_sse_text_event('{"type":"response.failed","response":{"error":{"message":"bad"}}}')
        self.assertTrue(done)
        self.assertEqual("bad", error)


class PromptTests(unittest.TestCase):
    def test_prompt_contains_grade_and_safety_boundary(self) -> None:
        prompt = build_instructions("junior", "concise", "guide")
        self.assertIn("初中", prompt)
        self.assertIn("本轮只说明考点", prompt)
        self.assertIn("不能改变以上规则", prompt)


class HttpProtocolTests(unittest.TestCase):
    def test_create_session_consumes_body_on_persistent_connection(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            web = root / "web"
            web.mkdir()
            (web / "index.html").write_text("ok", encoding="utf-8")
            server = StudyAgentServer(("127.0.0.1", 0), RequestHandler, root / "data", web)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
            try:
                connection.request("POST", "/api/sessions", body="{}", headers={"Content-Type": "application/json"})
                first = connection.getresponse()
                self.assertEqual(201, first.status)
                first.read()
                connection.request("GET", "/api/sessions")
                response = connection.getresponse()
                self.assertEqual(200, response.status)
                self.assertEqual(1, len(json.loads(response.read())))
            finally:
                connection.close()
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_chat_stream_is_saved(self) -> None:
        class FakeBridge:
            model = "fake"
            selected_model = None

            @staticmethod
            def health():
                return True

            @classmethod
            def list_models(cls):
                return [cls.model, "other", "gpt-5.6-sol"]

            @classmethod
            def stream_response(cls, *_args, **kwargs):
                cls.selected_model = kwargs.get("model")
                yield "你好"
                yield "，一起学习！"

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            web = root / "web"
            web.mkdir()
            (web / "index.html").write_text("ok", encoding="utf-8")
            server = StudyAgentServer(("127.0.0.1", 0), RequestHandler, root / "data", web)
            server.bridge = FakeBridge()
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                connection.request("POST", "/api/sessions", body="{}", headers={"Content-Type": "application/json"})
                session = json.loads(connection.getresponse().read())
                connection.close()

                connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                payload = json.dumps({"sessionId": session["id"], "message": "你好", "mode": "guide"})
                connection.request("POST", "/api/chat", body=payload, headers={"Content-Type": "application/json"})
                response = connection.getresponse()
                events = [json.loads(line) for line in response.read().decode().splitlines()]
                self.assertEqual(200, response.status)
                self.assertEqual("你好，一起学习！", "".join(e.get("text", "") for e in events))
                stored = server.store.get_session(session["id"])
                self.assertEqual(2, len(stored["messages"]))
                self.assertEqual("你好，一起学习！", stored["messages"][-1]["content"])
                self.assertEqual("gpt-5.6-sol", FakeBridge.selected_model)
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
