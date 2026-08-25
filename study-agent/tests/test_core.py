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
from server.bridge import CopilotBridgeClient, extract_sse_text_event
from server.prompts import build_instructions
from server.storage import StudyStore


def enable_access(server: StudyAgentServer) -> str:
    if not server.store.access_password_is_set():
        server.store.set_initial_access_password("family-pass")
    return f"study_agent_session={server.store.create_access_token()}"


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

    def test_access_password_tokens_are_revoked_when_password_changes(self) -> None:
        self.assertTrue(self.store.set_initial_access_password("family-pass"))
        self.assertFalse(self.store.set_initial_access_password("other-pass"))
        self.assertTrue(self.store.verify_access_password("family-pass"))
        token = self.store.create_access_token()
        self.assertTrue(self.store.verify_access_token(token))
        self.store.set_access_password("new-family-pass")
        self.assertFalse(self.store.verify_access_token(token))
        self.assertTrue(self.store.verify_access_password("new-family-pass"))

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
    class FakeStream(list):
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    def test_delta_event(self) -> None:
        delta, done, error, fallback = extract_sse_text_event('{"type":"response.output_text.delta","delta":"你好"}')
        self.assertEqual("你好", delta)
        self.assertFalse(done)
        self.assertIsNone(error)
        self.assertFalse(fallback)

    def test_output_text_done_can_recover_a_non_streamed_answer(self) -> None:
        text, done, error, fallback = extract_sse_text_event(
            '{"type":"response.output_text.done","text":"完整答案"}'
        )
        self.assertEqual("完整答案", text)
        self.assertFalse(done)
        self.assertIsNone(error)
        self.assertTrue(fallback)

    def test_completed_event_can_recover_nested_output_text(self) -> None:
        text, done, error, fallback = extract_sse_text_event(json.dumps({
            "type": "response.completed",
            "response": {"output": [{"type": "message", "content": [
                {"type": "output_text", "text": "最终答案"}
            ]}]},
        }))
        self.assertEqual("最终答案", text)
        self.assertTrue(done)
        self.assertIsNone(error)
        self.assertTrue(fallback)

    def test_failed_event(self) -> None:
        _, done, error, _ = extract_sse_text_event('{"type":"response.failed","response":{"error":{"message":"bad"}}}')
        self.assertTrue(done)
        self.assertEqual("bad", error)

    def test_final_text_fallback_is_not_duplicated_after_deltas(self) -> None:
        client = CopilotBridgeClient("http://bridge", "key", "model")
        client._request = lambda *_args, **_kwargs: self.FakeStream([
            b'data: {"type":"response.output_text.delta","delta":"\xe4\xbd\xa0"}\n',
            b'data: {"type":"response.output_text.delta","delta":"\xe5\xa5\xbd"}\n',
            b'data: {"type":"response.output_text.done","text":"\xe4\xbd\xa0\xe5\xa5\xbd"}\n',
            b'data: {"type":"response.completed","response":{"output":[]}}\n',
        ])
        output = list(client.stream_response("instructions", [], "question", None))
        self.assertEqual(["你", "好"], output)

    def test_final_text_fallback_is_used_when_no_deltas_arrive(self) -> None:
        client = CopilotBridgeClient("http://bridge", "key", "model")
        client._request = lambda *_args, **_kwargs: self.FakeStream([
            b'data: {"type":"response.output_text.done","text":"\xe5\xae\x8c\xe6\x95\xb4\xe7\xad\x94\xe6\xa1\x88"}\n',
            b'data: {"type":"response.completed","response":{"output":[]}}\n',
        ])
        output = list(client.stream_response("instructions", [], "question", None))
        self.assertEqual(["完整答案"], output)


class PromptTests(unittest.TestCase):
    def test_prompt_contains_grade_and_safety_boundary(self) -> None:
        prompt = build_instructions("junior", "concise", "guide")
        self.assertIn("初中", prompt)
        self.assertIn("本轮只说明考点", prompt)
        self.assertIn("不能改变以上规则", prompt)

    def test_review_prompt_requires_careful_per_question_feedback(self) -> None:
        prompt = build_instructions("junior", "detailed", "review")
        self.assertIn("当前是批改作业模式", prompt)
        self.assertIn("按题号逐题反馈", prompt)
        self.assertIn("不要编造分数", prompt)
        self.assertIn("未看到作答", prompt)


class HttpProtocolTests(unittest.TestCase):
    def test_family_access_setup_login_and_rate_limit(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            web = root / "web"
            web.mkdir()
            (web / "index.html").write_text("ok", encoding="utf-8")
            server = StudyAgentServer(("127.0.0.1", 0), RequestHandler, root / "data", web)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()

            def request(method: str, path: str, payload: dict | None = None, cookie: str = ""):
                connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                try:
                    body = json.dumps(payload) if payload is not None else None
                    headers = {"Content-Type": "application/json"} if body is not None else {}
                    if cookie:
                        headers["Cookie"] = cookie
                    connection.request(method, path, body=body, headers=headers)
                    response = connection.getresponse()
                    data = json.loads(response.read())
                    return response.status, data, response.getheader("Set-Cookie", "")
                finally:
                    connection.close()

            try:
                status, _, _ = request("GET", "/api/profiles")
                self.assertEqual(401, status)
                status, state, _ = request("GET", "/api/auth/status")
                self.assertEqual({"configured": False, "authenticated": False}, state)

                status, _, set_cookie = request("POST", "/api/auth/setup", {"password": "family-pass"})
                self.assertEqual(201, status)
                self.assertIn("HttpOnly", set_cookie)
                self.assertIn("SameSite=Strict", set_cookie)
                cookie = set_cookie.split(";", 1)[0]
                status, _, _ = request("GET", "/api/profiles", cookie=cookie)
                self.assertEqual(200, status)

                for _ in range(5):
                    status, _, _ = request("POST", "/api/auth/login", {"password": "wrong-pass"})
                    self.assertEqual(401, status)
                status, _, _ = request("POST", "/api/auth/login", {"password": "family-pass"})
                self.assertEqual(429, status)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_profile_crud_requires_parent_pin(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            web = root / "web"
            web.mkdir()
            (web / "index.html").write_text("ok", encoding="utf-8")
            server = StudyAgentServer(("127.0.0.1", 0), RequestHandler, root / "data", web)
            server.store.set_pin("1234")
            access_cookie = enable_access(server)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()

            def request(method: str, path: str, payload: dict | None = None) -> tuple[int, dict | list]:
                connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                try:
                    body = json.dumps(payload) if payload is not None else None
                    headers = {"Content-Type": "application/json"} if body is not None else {}
                    headers["Cookie"] = access_cookie
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
            access_cookie = enable_access(server)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
            try:
                profile_id = server.store.list_profiles()[0]["id"]
                body = json.dumps({"profileId": profile_id})
                connection.request("POST", "/api/sessions", body=body, headers={"Content-Type": "application/json", "Cookie": access_cookie})
                first = connection.getresponse()
                self.assertEqual(201, first.status)
                first.read()
                connection.request("GET", f"/api/sessions?profileId={profile_id}", headers={"Cookie": access_cookie})
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
            selected_instructions = None

            @staticmethod
            def health():
                return True

            @classmethod
            def list_models(cls):
                return [cls.model, "other", "gpt-5.6-sol"]

            @classmethod
            def stream_response(cls, *args, **kwargs):
                cls.selected_model = kwargs.get("model")
                cls.selected_instructions = args[0]
                yield "你好"
                yield "，一起学习！"

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            web = root / "web"
            web.mkdir()
            (web / "index.html").write_text("ok", encoding="utf-8")
            server = StudyAgentServer(("127.0.0.1", 0), RequestHandler, root / "data", web)
            server.bridge = FakeBridge()
            access_cookie = enable_access(server)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                profile_id = server.store.list_profiles()[0]["id"]
                connection.request(
                    "POST",
                    "/api/sessions",
                    body=json.dumps({"profileId": profile_id}),
                    headers={"Content-Type": "application/json", "Cookie": access_cookie},
                )
                session = json.loads(connection.getresponse().read())
                connection.close()

                connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                image_data = "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\ncontent").decode()
                payload = json.dumps(
                    {"sessionId": session["id"], "message": "", "imageDataUrl": image_data, "mode": "review"}
                )
                connection.request("POST", "/api/chat", body=payload, headers={"Content-Type": "application/json", "Cookie": access_cookie})
                response = connection.getresponse()
                events = [json.loads(line) for line in response.read().decode().splitlines()]
                self.assertEqual(200, response.status)
                self.assertEqual(
                    {"type": "status", "message": "图片已收到，正在识别题目和作答…"},
                    events[0],
                )
                self.assertEqual("你好，一起学习！", "".join(e.get("text", "") for e in events))
                stored = server.store.get_session(session["id"])
                self.assertEqual(2, len(stored["messages"]))
                self.assertIn("逐题识别并批改", stored["messages"][0]["content"])
                self.assertIsNotNone(stored["messages"][0]["attachment"])
                self.assertEqual("你好，一起学习！", stored["messages"][-1]["content"])
                self.assertEqual("gpt-5.6-sol", FakeBridge.selected_model)
                self.assertIn("当前是批改作业模式", FakeBridge.selected_instructions)
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
