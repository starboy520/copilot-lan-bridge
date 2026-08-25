from __future__ import annotations

import hashlib
import hmac
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator


DEFAULT_SETTINGS = {
    "grade_level": "junior",
    "response_style": "concise",
    "learning_mode": "guide",
    "reasoning_effort": "medium",
}

DEFAULT_PROFILE_ID = "default"
DEFAULT_PROFILE_NAME = "孩子"
MAX_PROFILES = 8


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class StudyStore:
    def __init__(self, data_dir: Path, default_model: str = "gpt-5.6-sol"):
        self.data_dir = Path(data_dir)
        self.default_model = default_model
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.attachments_dir = self.data_dir / "attachments"
        self.attachments_dir.mkdir(exist_ok=True)
        self.db_path = self.data_dir / "study-agent.db"
        self._initialize()
        self.cleanup_old_attachments()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self.connect() as db:
            db.execute("PRAGMA journal_mode = WAL")
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS profiles (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    profile_id TEXT REFERENCES profiles(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS attachments (
                    id TEXT PRIMARY KEY,
                    storage_path TEXT NOT NULL,
                    mime_type TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attachment_id TEXT REFERENCES attachments(id) ON DELETE SET NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS profile_settings (
                    profile_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    PRIMARY KEY(profile_id, key)
                );
                CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id);
                """
            )
            session_columns = {row["name"] for row in db.execute("PRAGMA table_info(sessions)")}
            if "profile_id" not in session_columns:
                db.execute("ALTER TABLE sessions ADD COLUMN profile_id TEXT REFERENCES profiles(id) ON DELETE CASCADE")

            now = utc_now()
            if db.execute("SELECT COUNT(*) FROM profiles").fetchone()[0] == 0:
                db.execute(
                    "INSERT INTO profiles(id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    (DEFAULT_PROFILE_ID, DEFAULT_PROFILE_NAME, now, now),
                )
            default_profile = db.execute("SELECT id FROM profiles ORDER BY created_at, id LIMIT 1").fetchone()[0]
            db.execute("UPDATE sessions SET profile_id=? WHERE profile_id IS NULL", (default_profile,))
            db.execute("CREATE INDEX IF NOT EXISTS idx_sessions_profile ON sessions(profile_id, updated_at DESC)")

            for key, value in {**DEFAULT_SETTINGS, "model": self.default_model}.items():
                db.execute("INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)", (key, value))

            legacy = {row["key"]: row["value"] for row in db.execute("SELECT key, value FROM settings")}
            for profile in db.execute("SELECT id FROM profiles").fetchall():
                for key, fallback in {**DEFAULT_SETTINGS, "model": self.default_model}.items():
                    db.execute(
                        "INSERT OR IGNORE INTO profile_settings(profile_id, key, value) VALUES (?, ?, ?)",
                        (profile["id"], key, legacy.get(key, fallback)),
                    )

    def list_profiles(self) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(
                """SELECT p.id, p.name, p.created_at, p.updated_at, COUNT(s.id) AS session_count
                   FROM profiles p LEFT JOIN sessions s ON s.profile_id=p.id
                   GROUP BY p.id ORDER BY p.created_at, p.id"""
            ).fetchall()
        return [
            {
                "id": row["id"],
                "name": row["name"],
                "sessionCount": row["session_count"],
                "createdAt": row["created_at"],
                "updatedAt": row["updated_at"],
            }
            for row in rows
        ]

    def profile_exists(self, profile_id: str) -> bool:
        with self.connect() as db:
            return db.execute("SELECT 1 FROM profiles WHERE id=?", (profile_id,)).fetchone() is not None

    def create_profile(self, name: str) -> dict[str, Any]:
        profile_id = str(uuid.uuid4())
        now = utc_now()
        with self.connect() as db:
            if db.execute("SELECT COUNT(*) FROM profiles").fetchone()[0] >= MAX_PROFILES:
                raise ValueError(f"最多可以创建 {MAX_PROFILES} 个孩子档案。")
            try:
                db.execute(
                    "INSERT INTO profiles(id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    (profile_id, name, now, now),
                )
            except sqlite3.IntegrityError as error:
                raise ValueError("档案名称已经存在。") from error
            for key, value in {**DEFAULT_SETTINGS, "model": self.default_model}.items():
                db.execute(
                    "INSERT INTO profile_settings(profile_id, key, value) VALUES (?, ?, ?)",
                    (profile_id, key, value),
                )
        return {"id": profile_id, "name": name, "sessionCount": 0, "createdAt": now, "updatedAt": now}

    def rename_profile(self, profile_id: str, name: str) -> dict[str, Any] | None:
        now = utc_now()
        with self.connect() as db:
            try:
                changed = db.execute(
                    "UPDATE profiles SET name=?, updated_at=? WHERE id=?", (name, now, profile_id)
                ).rowcount
            except sqlite3.IntegrityError as error:
                raise ValueError("档案名称已经存在。") from error
        if not changed:
            return None
        return next(profile for profile in self.list_profiles() if profile["id"] == profile_id)

    def delete_profile(self, profile_id: str) -> bool:
        with self.connect() as db:
            if db.execute("SELECT COUNT(*) FROM profiles").fetchone()[0] <= 1:
                raise ValueError("至少需要保留一个孩子档案。")
            paths = [
                Path(row[0])
                for row in db.execute(
                    """SELECT a.storage_path FROM attachments a JOIN messages m ON m.attachment_id=a.id
                       JOIN sessions s ON s.id=m.session_id WHERE s.profile_id=?""",
                    (profile_id,),
                ).fetchall()
            ]
            deleted = db.execute("DELETE FROM profiles WHERE id=?", (profile_id,)).rowcount > 0
            db.execute(
                "DELETE FROM attachments WHERE id NOT IN (SELECT attachment_id FROM messages WHERE attachment_id IS NOT NULL)"
            )
        if deleted:
            for path in paths:
                path.unlink(missing_ok=True)
        return deleted

    def create_session(self, profile_id: str) -> dict[str, Any]:
        if not self.profile_exists(profile_id):
            raise ValueError("孩子档案不存在。")
        session_id = str(uuid.uuid4())
        now = utc_now()
        with self.connect() as db:
            db.execute(
                "INSERT INTO sessions(id, title, created_at, updated_at, profile_id) VALUES (?, ?, ?, ?, ?)",
                (session_id, "新对话", now, now, profile_id),
            )
        return {"id": session_id, "title": "新对话", "createdAt": now, "updatedAt": now, "profileId": profile_id}

    def list_sessions(self, profile_id: str) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(
                """SELECT s.id, s.title, s.created_at, s.updated_at,
                          (SELECT content FROM messages m WHERE m.session_id=s.id ORDER BY m.id DESC LIMIT 1) AS preview
                   FROM sessions s WHERE s.profile_id=? ORDER BY s.updated_at DESC LIMIT 100""",
                (profile_id,),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "title": row["title"],
                "preview": row["preview"] or "还没有消息",
                "createdAt": row["created_at"],
                "updatedAt": row["updated_at"],
            }
            for row in rows
        ]

    def session_exists(self, session_id: str) -> bool:
        with self.connect() as db:
            return db.execute("SELECT 1 FROM sessions WHERE id=?", (session_id,)).fetchone() is not None

    def session_profile_id(self, session_id: str) -> str | None:
        with self.connect() as db:
            row = db.execute("SELECT profile_id FROM sessions WHERE id=?", (session_id,)).fetchone()
        return row["profile_id"] if row else None

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with self.connect() as db:
            session = db.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
            if session is None:
                return None
            messages = db.execute(
                """SELECT m.id, m.role, m.content, m.status, m.created_at,
                          a.id AS attachment_id, a.mime_type
                   FROM messages m LEFT JOIN attachments a ON a.id=m.attachment_id
                   WHERE m.session_id=? ORDER BY m.id""",
                (session_id,),
            ).fetchall()
        return {
            "id": session["id"],
            "profileId": session["profile_id"],
            "title": session["title"],
            "createdAt": session["created_at"],
            "updatedAt": session["updated_at"],
            "messages": [
                {
                    "id": row["id"],
                    "role": row["role"],
                    "content": row["content"],
                    "status": row["status"],
                    "createdAt": row["created_at"],
                    "attachment": (
                        {"id": row["attachment_id"], "mimeType": row["mime_type"]}
                        if row["attachment_id"]
                        else None
                    ),
                }
                for row in messages
            ],
        }

    def add_attachment(self, raw: bytes, mime_type: str, suffix: str) -> str:
        attachment_id = str(uuid.uuid4())
        filename = f"{attachment_id}{suffix}"
        path = self.attachments_dir / filename
        path.write_bytes(raw)
        with self.connect() as db:
            db.execute(
                "INSERT INTO attachments(id, storage_path, mime_type, size_bytes, created_at) VALUES (?, ?, ?, ?, ?)",
                (attachment_id, str(path), mime_type, len(raw), utc_now()),
            )
        return attachment_id

    def get_attachment(self, attachment_id: str) -> tuple[Path, str] | None:
        with self.connect() as db:
            row = db.execute(
                "SELECT storage_path, mime_type FROM attachments WHERE id=?", (attachment_id,)
            ).fetchone()
        if row is None:
            return None
        path = Path(row["storage_path"])
        return (path, row["mime_type"]) if path.is_file() else None

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        status: str = "completed",
        attachment_id: str | None = None,
    ) -> int:
        now = utc_now()
        with self.connect() as db:
            cursor = db.execute(
                "INSERT INTO messages(session_id, role, content, status, attachment_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, role, content, status, attachment_id, now),
            )
            if role == "user":
                session = db.execute("SELECT title FROM sessions WHERE id=?", (session_id,)).fetchone()
                if session and session["title"] == "新对话":
                    compact = " ".join(content.replace("\n", " ").split())
                    title = (compact[:26] + "…") if len(compact) > 26 else compact
                    db.execute("UPDATE sessions SET title=? WHERE id=?", (title or "图片题目", session_id))
            db.execute("UPDATE sessions SET updated_at=? WHERE id=?", (now, session_id))
            return int(cursor.lastrowid)

    def recent_messages(self, session_id: str, limit: int = 20) -> list[dict[str, str]]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT role, content FROM messages WHERE session_id=? AND status='completed' ORDER BY id DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]

    def delete_session(self, session_id: str) -> bool:
        with self.connect() as db:
            attachment_rows = db.execute(
                """SELECT a.storage_path FROM attachments a JOIN messages m ON m.attachment_id=a.id
                   WHERE m.session_id=?""",
                (session_id,),
            ).fetchall()
            deleted = db.execute("DELETE FROM sessions WHERE id=?", (session_id,)).rowcount > 0
            db.execute(
                "DELETE FROM attachments WHERE id NOT IN (SELECT attachment_id FROM messages WHERE attachment_id IS NOT NULL)"
            )
        for row in attachment_rows:
            Path(row["storage_path"]).unlink(missing_ok=True)
        return deleted

    def clear_profile(self, profile_id: str) -> None:
        with self.connect() as db:
            paths = [
                Path(row[0])
                for row in db.execute(
                    """SELECT a.storage_path FROM attachments a JOIN messages m ON m.attachment_id=a.id
                       JOIN sessions s ON s.id=m.session_id WHERE s.profile_id=?""",
                    (profile_id,),
                ).fetchall()
            ]
            db.execute("DELETE FROM sessions WHERE profile_id=?", (profile_id,))
            db.execute(
                "DELETE FROM attachments WHERE id NOT IN (SELECT attachment_id FROM messages WHERE attachment_id IS NOT NULL)"
            )
        for path in paths:
            path.unlink(missing_ok=True)

    def cleanup_old_attachments(self, days: int = 7) -> int:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
        with self.connect() as db:
            rows = db.execute(
                "SELECT id, storage_path FROM attachments WHERE created_at < ?", (cutoff,)
            ).fetchall()
            if rows:
                placeholders = ",".join("?" for _ in rows)
                db.execute(f"DELETE FROM attachments WHERE id IN ({placeholders})", [row["id"] for row in rows])
        for row in rows:
            Path(row["storage_path"]).unlink(missing_ok=True)
        return len(rows)

    def get_settings(self, profile_id: str) -> dict[str, Any]:
        with self.connect() as db:
            pairs = {
                row["key"]: row["value"]
                for row in db.execute("SELECT key, value FROM profile_settings WHERE profile_id=?", (profile_id,))
            }
            pin_set = db.execute("SELECT 1 FROM settings WHERE key='pin_hash'").fetchone() is not None
        return {
            "gradeLevel": pairs.get("grade_level", "junior"),
            "responseStyle": pairs.get("response_style", "concise"),
            "learningMode": pairs.get("learning_mode", "guide"),
            "reasoningEffort": pairs.get("reasoning_effort", "medium"),
            "model": pairs.get("model", self.default_model),
            "pinSet": pin_set,
        }

    def update_settings(
        self,
        profile_id: str,
        grade_level: str,
        response_style: str,
        learning_mode: str,
        reasoning_effort: str,
        model: str,
    ) -> None:
        values = {
            "grade_level": grade_level,
            "response_style": response_style,
            "learning_mode": learning_mode,
            "reasoning_effort": reasoning_effort,
            "model": model,
        }
        with self.connect() as db:
            for key, value in values.items():
                db.execute(
                    """INSERT INTO profile_settings(profile_id, key, value) VALUES (?, ?, ?)
                       ON CONFLICT(profile_id, key) DO UPDATE SET value=excluded.value""",
                    (profile_id, key, value),
                )

    def set_pin(self, pin: str) -> None:
        salt = os.urandom(16)
        digest = hashlib.scrypt(pin.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
        encoded = f"{salt.hex()}${digest.hex()}"
        with self.connect() as db:
            db.execute(
                "INSERT INTO settings(key, value) VALUES ('pin_hash', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (encoded,),
            )

    def verify_pin(self, pin: str) -> bool:
        with self.connect() as db:
            row = db.execute("SELECT value FROM settings WHERE key='pin_hash'").fetchone()
        if row is None:
            return True
        try:
            salt_hex, digest_hex = row["value"].split("$", 1)
            actual = hashlib.scrypt(pin.encode("utf-8"), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1)
            return hmac.compare_digest(actual.hex(), digest_hex)
        except (ValueError, TypeError):
            return False

    def pin_is_set(self) -> bool:
        with self.connect() as db:
            return db.execute("SELECT 1 FROM settings WHERE key='pin_hash'").fetchone() is not None
