from __future__ import annotations

import base64
import http.client
import json
import sqlite3
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
        profile_id = self.store.list_profiles()[0]["id"]
        session = self.store.create_session(profile_id)
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
        profile_id = self.store.list_profiles()[0]["id"]
        self.assertEqual("medium", self.store.get_settings(profile_id)["reasoningEffort"])
        self.store.update_settings(profile_id, "junior", "concise", "guide", "high", "gpt-5.6-sol")
        self.assertEqual("high", self.store.get_settings(profile_id)["reasoningEffort"])
        self.assertEqual("gpt-5.6-sol", self.store.get_settings(profile_id)["model"])

    def test_custom_default_model_for_new_deployment(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = StudyStore(Path(temp), default_model="deployment-model")
            profile_id = store.list_profiles()[0]["id"]
            self.assertEqual("deployment-model", store.get_settings(profile_id)["model"])

    def test_profiles_isolate_sessions_and_settings(self) -> None:
        first_id = self.store.list_profiles()[0]["id"]
        second = self.store.create_profile("小明")
        first_session = self.store.create_session(first_id)
        second_session = self.store.create_session(second["id"])
        self.store.update_settings(second["id"], "primary", "detailed", "direct", "low", "gpt-5.6-sol")
        self.assertEqual(1, len(self.store.list_sessions(first_id)))
        self.assertEqual(1, len(self.store.list_sessions(second["id"])))
        self.assertEqual("junior", self.store.get_settings(first_id)["gradeLevel"])
        self.assertEqual("primary", self.store.get_settings(second["id"])["gradeLevel"])
        self.assertTrue(self.store.delete_profile(second["id"]))
        self.assertIsNotNone(self.store.get_session(first_session["id"]))
        self.assertIsNone(self.store.get_session(second_session["id"]))

    def test_existing_database_is_migrated_to_default_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            db_path = root / "study-agent.db"
            db = sqlite3.connect(db_path)
            try:
                db.executescript(
                    """
                    CREATE TABLE sessions (id TEXT PRIMARY KEY, title TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
                    CREATE TABLE attachments (id TEXT PRIMARY KEY, storage_path TEXT NOT NULL, mime_type TEXT NOT NULL, size_bytes INTEGER NOT NULL, created_at TEXT NOT NULL);
                    CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE, role TEXT NOT NULL, content TEXT NOT NULL, status TEXT NOT NULL, attachment_id TEXT REFERENCES attachments(id), created_at TEXT NOT NULL);
                    CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                    INSERT INTO sessions VALUES ('old-session', '旧对话', '2026-01-01', '2026-01-01');
                    INSERT INTO settings VALUES ('grade_level', 'senior');
                    """
                )
                db.commit()
            finally:
                db.close()
            migrated = StudyStore(root)
            profile_id = migrated.list_profiles()[0]["id"]
            self.assertEqual("old-session", migrated.list_sessions(profile_id)[0]["id"])
            self.assertEqual("senior", migrated.get_settings(profile_id)["gradeLevel"])

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
    def test_profile_crud_requires_parent_pin(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            web = root / "web"
            web.mkdir()
            (web / "index.html").write_text("ok", encoding="utf-8")
            server = StudyAgentServer(("127.0.0.1", 0), RequestHandler, root / "data", web)
            server.store.set_pin("1234")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()

            def request(method: str, path: str, payload: dict | None = None) -> tuple[int, dict | list]:
                connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                try:
                    body = json.dumps(payload) if payload is not None else None
                    headers = {"Content-Type": "application/json"} if body is not None else {}
                    connection.request(method, path, body=body, headers=headers)
                    response = connection.getresponse()
                    return response.status, json.loads(response.read())
                finally:
                    connection.close()

            try:
                status, _ = request("POST", "/api/profiles", {"name": "小明", "pin": "0000"})
                self.assertEqual(403, status)

                status, profile = request("POST", "/api/profiles", {"name": "小明", "pin": "1234"})
                self.assertEqual(201, status)
                profile_id = profile["id"]

                status, renamed = request(
                    "PUT", f"/api/profiles/{profile_id}", {"name": "小明同学", "pin": "1234"}
                )
                self.assertEqual(200, status)
                self.assertEqual("小明同学", renamed["name"])

                status, _ = request("DELETE", f"/api/profiles/{profile_id}", {"pin": "1234"})
                self.assertEqual(200, status)
                self.assertEqual(1, len(server.store.list_profiles()))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

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
                profile_id = server.store.list_profiles()[0]["id"]
                body = json.dumps({"profileId": profile_id})
                connection.request("POST", "/api/sessions", body=body, headers={"Content-Type": "application/json"})
                first = connection.getresponse()
                self.assertEqual(201, first.status)
                first.read()
                connection.request("GET", f"/api/sessions?profileId={profile_id}")
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
                profile_id = server.store.list_profiles()[0]["id"]
                connection.request(
                    "POST",
                    "/api/sessions",
                    body=json.dumps({"profileId": profile_id}),
                    headers={"Content-Type": "application/json"},
                )
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
