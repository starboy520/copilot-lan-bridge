from __future__ import annotations

import argparse
import base64
import binascii
import getpass
import hashlib
import json
import mimetypes
import os
import re
import sys
import threading
import time
import urllib.parse
from http.cookies import SimpleCookie
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .bridge import BridgeError, CopilotBridgeClient
from .prompts import build_instructions
from .storage import StudyStore


APP_ROOT = Path(__file__).resolve().parent.parent
mimetypes.add_type("text/markdown", ".md")
MAX_JSON_BYTES = 5 * 1024 * 1024
MAX_IMAGE_BYTES = 3 * 1024 * 1024
MAX_MESSAGE_CHARS = 10_000
MAX_PROFILE_NAME_CHARS = 20
ACCESS_COOKIE_NAME = "study_agent_session"
ACCESS_COOKIE_MAX_AGE = 30 * 24 * 60 * 60
LOGIN_WINDOW_SECONDS = 10 * 60
LOGIN_BLOCK_SECONDS = 15 * 60
MAX_LOGIN_FAILURES = 5
IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


class ApiError(ValueError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def parse_image_data_url(value: Any) -> tuple[bytes, str, str] | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise ApiError("图片格式不正确。")
    match = re.fullmatch(r"data:([^;,]+);base64,([A-Za-z0-9+/=\r\n]+)", value)
    if not match:
        raise ApiError("图片数据格式不正确。")
    mime_type = match.group(1).lower()
    if mime_type not in IMAGE_TYPES:
        raise ApiError("只支持 JPG、PNG 或 WebP 图片。")
    try:
        raw = base64.b64decode(match.group(2), validate=True)
    except (binascii.Error, ValueError) as error:
        raise ApiError("图片数据损坏，请重新选择。") from error
    if not raw:
        raise ApiError("图片内容为空。")
    if len(raw) > MAX_IMAGE_BYTES:
        raise ApiError("图片不能超过 3 MB，请压缩或重新拍摄。", 413)
    signatures = {
        "image/jpeg": (b"\xff\xd8\xff",),
        "image/png": (b"\x89PNG\r\n\x1a\n",),
        "image/webp": (b"RIFF",),
    }
    if not any(raw.startswith(prefix) for prefix in signatures[mime_type]):
        raise ApiError("图片的真实格式与文件类型不一致。")
    if mime_type == "image/webp" and (len(raw) < 12 or raw[8:12] != b"WEBP"):
        raise ApiError("WebP 图片格式无效。")
    return raw, mime_type, IMAGE_TYPES[mime_type]


class StudyAgentServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], handler: type[BaseHTTPRequestHandler], data_dir: Path, web_dir: Path):
        super().__init__(address, handler)
        self.web_dir = web_dir.resolve()
        default_model = os.environ.get("STUDY_AGENT_MODEL", "gpt-5.6-sol")
        self.bridge = CopilotBridgeClient(
            os.environ.get("COPILOT_BRIDGE_URL", "http://127.0.0.1:18787"),
            os.environ.get("COPILOT_BRIDGE_API_KEY", ""),
            default_model,
        )
        self.store = StudyStore(data_dir, default_model=default_model)
        self.auth_lock = threading.Lock()
        self.auth_failures: dict[str, list[float]] = {}


class RequestHandler(BaseHTTPRequestHandler):
    server: StudyAgentServer
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stdout.write(f"[{self.log_date_time_string()}] {fmt % args}\n")

    def _send_bytes(self, status: int, data: bytes, content_type: str, extra_headers: dict[str, str] | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        default_cache = "no-store" if content_type.startswith("application/json") else "public, max-age=3600"
        if not extra_headers or "Cache-Control" not in extra_headers:
            self.send_header("Cache-Control", default_cache)
        if extra_headers:
            for name, value in extra_headers.items():
                self.send_header(name, value)
        self.end_headers()
        self.wfile.write(data)

    def _send_not_modified(self, extra_headers: dict[str, str]) -> None:
        self.send_response(HTTPStatus.NOT_MODIFIED)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        for name, value in extra_headers.items():
            self.send_header(name, value)
        self.end_headers()

    def _json(self, status: int, payload: Any, extra_headers: dict[str, str] | None = None) -> None:
        self._send_bytes(
            status,
            json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            "application/json; charset=utf-8",
            extra_headers,
        )

    def _read_json(self) -> dict[str, Any]:
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            raise ApiError("请求必须使用 JSON 格式。", 415)
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ApiError("请求长度无效。") from error
        if length <= 0:
            raise ApiError("请求内容不能为空。")
        if length > MAX_JSON_BYTES:
            raise ApiError("请求内容过大。", 413)
        try:
            value = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ApiError("JSON 内容无效。") from error
        if not isinstance(value, dict):
            raise ApiError("请求内容必须是对象。")
        return value

    def _route_parts(self) -> list[str]:
        return [urllib.parse.unquote(part) for part in urllib.parse.urlsplit(self.path).path.split("/") if part]

    def _query_value(self, name: str) -> str:
        values = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get(name, [])
        return values[0].strip() if values else ""

    def _require_profile(self, profile_id: str) -> str:
        if not profile_id or not self.server.store.profile_exists(profile_id):
            raise ApiError("孩子档案不存在。", 404)
        return profile_id

    def _access_token(self) -> str:
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
        except Exception:
            return ""
        morsel = cookie.get(ACCESS_COOKIE_NAME)
        return morsel.value if morsel else ""

    def _is_authenticated(self) -> bool:
        return self.server.store.verify_access_token(self._access_token())

    def _require_auth(self) -> None:
        if not self.server.store.access_password_is_set():
            raise ApiError("请先设置家庭密码。", 401)
        if not self._is_authenticated():
            raise ApiError("登录已失效，请重新输入家庭密码。", 401)

    def _session_cookie(self, token: str, max_age: int = ACCESS_COOKIE_MAX_AGE) -> str:
        parts = [
            f"{ACCESS_COOKIE_NAME}={token}",
            "Path=/",
            f"Max-Age={max_age}",
            "HttpOnly",
            "SameSite=Strict",
        ]
        if self.headers.get("X-Forwarded-Proto", "").lower() == "https":
            parts.append("Secure")
        return "; ".join(parts)

    @staticmethod
    def _access_password(value: Any) -> str:
        password = str(value or "")
        if password != password.strip():
            raise ApiError("家庭密码首尾不能有空格。")
        if not 8 <= len(password) <= 64:
            raise ApiError("家庭密码需要 8—64 个字符。")
        return password

    def _login_retry_after(self) -> int:
        address = self.client_address[0]
        now = time.monotonic()
        with self.server.auth_lock:
            failures = [value for value in self.server.auth_failures.get(address, []) if now - value < LOGIN_BLOCK_SECONDS]
            self.server.auth_failures[address] = failures
            if len(failures) < MAX_LOGIN_FAILURES:
                return 0
            return max(1, int(LOGIN_BLOCK_SECONDS - (now - failures[-1])))

    def _record_login_failure(self) -> None:
        address = self.client_address[0]
        now = time.monotonic()
        with self.server.auth_lock:
            failures = [value for value in self.server.auth_failures.get(address, []) if now - value < LOGIN_WINDOW_SECONDS]
            failures.append(now)
            self.server.auth_failures[address] = failures

    def _clear_login_failures(self) -> None:
        with self.server.auth_lock:
            self.server.auth_failures.pop(self.client_address[0], None)

    @staticmethod
    def _profile_name(value: Any) -> str:
        name = " ".join(str(value or "").split())
        if not name:
            raise ApiError("请输入孩子的名字或昵称。")
        if len(name) > MAX_PROFILE_NAME_CHARS:
            raise ApiError(f"档案名称不能超过 {MAX_PROFILE_NAME_CHARS} 个字符。")
        return name

    def do_GET(self) -> None:
        try:
            parts = self._route_parts()
            if parts[:1] == ["api"]:
                if parts not in (["api", "health"], ["api", "auth", "status"]):
                    self._require_auth()
                self._handle_api_get(parts[1:])
            else:
                self._serve_static()
        except ApiError as error:
            self._json(error.status, {"error": str(error)})
        except Exception as error:  # pragma: no cover - last-resort boundary
            self.log_error("Unhandled GET error: %r", error)
            self._json(500, {"error": "服务器发生错误。"})

    def do_POST(self) -> None:
        try:
            parts = self._route_parts()
            if parts == ["api", "auth", "setup"]:
                self._auth_setup()
            elif parts == ["api", "auth", "login"]:
                self._auth_login()
            elif parts == ["api", "auth", "logout"]:
                self._json(200, {"ok": True}, {"Set-Cookie": self._session_cookie("", 0)})
            elif parts == ["api", "chat"]:
                self._require_auth()
                self._chat()
            elif parts == ["api", "sessions"]:
                self._require_auth()
                body = self._read_json()
                profile_id = self._require_profile(str(body.get("profileId", "")))
                self._json(201, self.server.store.create_session(profile_id))
            elif parts == ["api", "profiles"]:
                self._require_auth()
                body = self._read_json()
                try:
                    profile = self.server.store.create_profile(self._profile_name(body.get("name")))
                except ValueError as error:
                    raise ApiError(str(error)) from error
                self._json(201, profile)
            else:
                raise ApiError("接口不存在。", 404)
        except ApiError as error:
            self._json(error.status, {"error": str(error)})
        except Exception as error:  # pragma: no cover
            self.log_error("Unhandled POST error: %r", error)
            self._json(500, {"error": "服务器发生错误。"})

    def do_PUT(self) -> None:
        try:
            self._require_auth()
            parts = self._route_parts()
            body = self._read_json()
            if parts == ["api", "auth", "password"]:
                new_password = self._access_password(body.get("newPassword"))
                self.server.store.set_access_password(new_password)
                token = self.server.store.create_access_token()
                self._json(200, {"ok": True}, {"Set-Cookie": self._session_cookie(token)})
                return
            if len(parts) == 3 and parts[:2] == ["api", "profiles"]:
                try:
                    profile = self.server.store.rename_profile(parts[2], self._profile_name(body.get("name")))
                except ValueError as error:
                    raise ApiError(str(error)) from error
                if profile is None:
                    raise ApiError("孩子档案不存在。", 404)
                self._json(200, profile)
                return
            if parts != ["api", "settings"]:
                raise ApiError("接口不存在。", 404)
            profile_id = self._require_profile(str(body.get("profileId", "")))
            grade = body.get("gradeLevel")
            style = body.get("responseStyle")
            mode = body.get("learningMode")
            reasoning_effort = body.get("reasoningEffort")
            model = str(body.get("model", "")).strip()
            if grade not in {"primary", "junior", "senior"}:
                raise ApiError("学段设置无效。")
            if style not in {"concise", "detailed"}:
                raise ApiError("回答风格设置无效。")
            if mode not in {"guide", "direct", "review"}:
                raise ApiError("学习模式设置无效。")
            if reasoning_effort not in {"low", "medium", "high"}:
                raise ApiError("思考深度设置无效。")
            try:
                available_models = self.server.bridge.list_models()
            except BridgeError as error:
                raise ApiError(str(error), 503) from error
            if model not in available_models:
                raise ApiError("所选模型当前不可用，请重新选择。")
            self.server.store.update_settings(profile_id, grade, style, mode, reasoning_effort, model)
            self._json(200, self.server.store.get_settings(profile_id))
        except ApiError as error:
            self._json(error.status, {"error": str(error)})
        except Exception as error:  # pragma: no cover
            self.log_error("Unhandled PUT error: %r", error)
            self._json(500, {"error": "服务器发生错误。"})

    def do_DELETE(self) -> None:
        try:
            self._require_auth()
            parts = self._route_parts()
            body = self._read_json()
            if len(parts) == 3 and parts[:2] == ["api", "sessions"]:
                if not self.server.store.delete_session(parts[2]):
                    raise ApiError("会话不存在。", 404)
                self._json(200, {"ok": True})
            elif len(parts) == 3 and parts[:2] == ["api", "profiles"]:
                try:
                    deleted = self.server.store.delete_profile(parts[2])
                except ValueError as error:
                    raise ApiError(str(error)) from error
                if not deleted:
                    raise ApiError("孩子档案不存在。", 404)
                self._json(200, {"ok": True})
            elif parts == ["api", "data"]:
                profile_id = self._require_profile(str(body.get("profileId", "")))
                self.server.store.clear_profile(profile_id)
                self._json(200, {"ok": True})
            else:
                raise ApiError("接口不存在。", 404)
        except ApiError as error:
            self._json(error.status, {"error": str(error)})
        except Exception as error:  # pragma: no cover
            self.log_error("Unhandled DELETE error: %r", error)
            self._json(500, {"error": "服务器发生错误。"})

    def _handle_api_get(self, parts: list[str]) -> None:
        if parts == ["auth", "status"]:
            configured = self.server.store.access_password_is_set()
            self._json(200, {"configured": configured, "authenticated": configured and self._is_authenticated()})
        elif parts == ["health"]:
            self._json(
                200,
                {
                    "status": "ok",
                    "bridge": self.server.bridge.health(),
                },
            )
        elif parts == ["models"]:
            try:
                models = self.server.bridge.list_models()
            except BridgeError:
                models = [self.server.bridge.model]
            self._json(200, {"default": self.server.bridge.model, "models": models})
        elif parts == ["profiles"]:
            self._json(200, self.server.store.list_profiles())
        elif parts == ["sessions"]:
            profile_id = self._require_profile(self._query_value("profileId"))
            self._json(200, self.server.store.list_sessions(profile_id))
        elif len(parts) == 2 and parts[0] == "sessions":
            session = self.server.store.get_session(parts[1])
            if session is None:
                raise ApiError("会话不存在。", 404)
            self._json(200, session)
        elif parts == ["settings"]:
            profile_id = self._require_profile(self._query_value("profileId"))
            self._json(200, self.server.store.get_settings(profile_id))
        elif len(parts) == 2 and parts[0] == "attachments":
            attachment = self.server.store.get_attachment(parts[1])
            if attachment is None:
                raise ApiError("图片不存在。", 404)
            path, mime_type = attachment
            self._send_bytes(200, path.read_bytes(), mime_type, {"Cache-Control": "private, no-store"})
        else:
            raise ApiError("接口不存在。", 404)

    def _auth_setup(self) -> None:
        body = self._read_json()
        password = self._access_password(body.get("password"))
        if not self.server.store.set_initial_access_password(password):
            raise ApiError("家庭密码已经设置，请直接登录。", 409)
        token = self.server.store.create_access_token()
        self._clear_login_failures()
        self._json(201, {"ok": True}, {"Set-Cookie": self._session_cookie(token)})

    def _auth_login(self) -> None:
        body = self._read_json()
        retry_after = self._login_retry_after()
        if retry_after:
            self._json(
                429,
                {"error": f"尝试次数过多，请在约 {max(1, retry_after // 60)} 分钟后重试。"},
                {"Retry-After": str(retry_after)},
            )
            return
        password = str(body.get("password", ""))
        if not self.server.store.access_password_is_set():
            raise ApiError("请先设置家庭密码。", 409)
        if not self.server.store.verify_access_password(password):
            self._record_login_failure()
            raise ApiError("家庭密码不正确。", 401)
        self._clear_login_failures()
        token = self.server.store.create_access_token()
        self._json(200, {"ok": True}, {"Set-Cookie": self._session_cookie(token)})

    def _chat(self) -> None:
        body = self._read_json()
        session_id = str(body.get("sessionId", ""))
        message = str(body.get("message", "")).strip()
        if not session_id or not self.server.store.session_exists(session_id):
            raise ApiError("会话不存在。", 404)
        if len(message) > MAX_MESSAGE_CHARS:
            raise ApiError("问题太长，请缩短后重试。", 413)
        parsed_image = parse_image_data_url(body.get("imageDataUrl"))
        if not message and parsed_image is None:
            raise ApiError("请输入问题或选择一张题目图片。")

        profile_id = self.server.store.session_profile_id(session_id)
        if profile_id is None:
            raise ApiError("会话不存在。", 404)
        settings = self.server.store.get_settings(profile_id)
        try:
            available_models = self.server.bridge.list_models()
        except BridgeError as error:
            raise ApiError(str(error), 503) from error
        if settings["model"] not in available_models:
            raise ApiError("当前配置的模型不可用，请在家长设置中重新选择。")

        history = self.server.store.recent_messages(session_id, limit=20)
        attachment_id = None
        if parsed_image:
            raw, mime_type, suffix = parsed_image
            attachment_id = self.server.store.add_attachment(raw, mime_type, suffix)
        mode = body.get("mode") if body.get("mode") in {"guide", "direct", "review"} else settings["learningMode"]
        stored_message = message or (
            "请逐题识别并批改这张作业图片，判断学生作答是否正确，指出错误并给出订正建议。"
            if mode == "review"
            else "请帮我识别并讲解这张题目图片。"
        )
        self.server.store.add_message(session_id, "user", stored_message, attachment_id=attachment_id)

        instructions = build_instructions(settings["gradeLevel"], settings["responseStyle"], mode)

        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Connection", "close")
        self.end_headers()

        full_text: list[str] = []
        try:
            image_data_url = body.get("imageDataUrl") if parsed_image else None
            if image_data_url and mode == "review":
                self._write_stream({"type": "status", "message": "图片已收到，正在识别题目和作答…"})
            for delta in self.server.bridge.stream_response(
                instructions,
                history,
                stored_message,
                image_data_url,
                reasoning_effort=settings["reasoningEffort"],
                model=settings["model"],
            ):
                full_text.append(delta)
                self._write_stream({"type": "delta", "text": delta})
            final_text = "".join(full_text).strip()
            if not final_text:
                raise BridgeError("模型没有返回可显示的内容。")
            message_id = self.server.store.add_message(session_id, "assistant", final_text)
            self._write_stream({"type": "done", "messageId": message_id})
        except (BridgeError, BrokenPipeError, ConnectionResetError, ConnectionAbortedError) as error:
            if full_text:
                self.server.store.add_message(session_id, "assistant", "".join(full_text), status="interrupted")
            if not isinstance(error, (BrokenPipeError, ConnectionResetError, ConnectionAbortedError)):
                try:
                    self._write_stream({"type": "error", "error": str(error)})
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    pass
        except Exception as error:  # defensive stream boundary
            self.log_error("Unexpected model stream error: %r", error)
            if full_text:
                self.server.store.add_message(session_id, "assistant", "".join(full_text), status="interrupted")
            try:
                self._write_stream({"type": "error", "error": "回答意外中断，请稍后重试。"})
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass
        finally:
            self.close_connection = True

    def _write_stream(self, payload: dict[str, Any]) -> None:
        self.wfile.write(json.dumps(payload, ensure_ascii=False).encode("utf-8") + b"\n")
        self.wfile.flush()

    def _serve_static(self) -> None:
        raw_path = urllib.parse.unquote(urllib.parse.urlsplit(self.path).path)
        relative = raw_path.lstrip("/") or "index.html"
        candidate = (self.server.web_dir / relative).resolve()
        try:
            candidate.relative_to(self.server.web_dir)
        except ValueError as error:
            raise ApiError("文件不存在。", 404) from error
        if not candidate.is_file():
            candidate = self.server.web_dir / "index.html"
        if not candidate.is_file():
            raise ApiError("前端尚未构建，请先运行构建命令。", 503)
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type in {"application/javascript", "application/json"}:
            content_type += "; charset=utf-8"
        relative_candidate = candidate.relative_to(self.server.web_dir)
        is_curriculum = bool(relative_candidate.parts) and relative_candidate.parts[0] == "curriculum"
        data = candidate.read_bytes()
        if is_curriculum:
            etag = f'"{hashlib.sha256(data).hexdigest()}"'
            cache_headers = {"Cache-Control": "no-cache", "ETag": etag}
            requested_etags = {
                value.strip() for value in self.headers.get("If-None-Match", "").split(",") if value.strip()
            }
            if "*" in requested_etags or etag in requested_etags or f"W/{etag}" in requested_etags:
                self._send_not_modified(cache_headers)
                return
            self._send_bytes(200, data, content_type, cache_headers)
            return

        cache = "no-cache" if candidate.name == "index.html" else "public, max-age=31536000, immutable"
        self._send_bytes(200, data, content_type, {"Cache-Control": cache})


def main() -> None:
    parser = argparse.ArgumentParser(description="小问号学习助手")
    parser.add_argument("--host", default=os.environ.get("STUDY_AGENT_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("STUDY_AGENT_PORT", "8765")))
    parser.add_argument("--data-dir", type=Path, default=Path(os.environ.get("STUDY_AGENT_DATA_DIR", APP_ROOT / "data")))
    parser.add_argument(
        "--reset-family-password",
        "--reset-access-password",
        dest="reset_family_password",
        action="store_true",
        help="交互式重置家庭密码后退出",
    )
    args = parser.parse_args()

    if args.reset_family_password:
        password = getpass.getpass("新的家庭密码（8—64 个字符）：")
        if password != password.strip() or not 8 <= len(password) <= 64:
            raise SystemExit("密码需要 8—64 个字符，且首尾不能有空格。")
        if password != getpass.getpass("请再输入一次："):
            raise SystemExit("两次输入的密码不一致。")
        StudyStore(args.data_dir, default_model=os.environ.get("STUDY_AGENT_MODEL", "gpt-5.6-sol")).set_access_password(password)
        print("家庭密码已重置，所有设备需要重新登录。")
        return

    try:
        server = StudyAgentServer((args.host, args.port), RequestHandler, args.data_dir, APP_ROOT / "web")
    except OSError as error:
        print(f"无法启动：端口 {args.port} 可能已被占用。{error}")
        raise SystemExit(1) from error
    print("\n小问号学习助手已启动")
    print(f"本机访问：http://127.0.0.1:{args.port}")
    if args.host == "0.0.0.0":
        print(f"手机访问：请使用 http://这台电脑的局域网IP:{args.port}")
    print("按 Ctrl+C 停止。\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n正在停止学习助手…")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
