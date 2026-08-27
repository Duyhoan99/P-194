import sqlite3
import uuid
from datetime import datetime
from pydantic import BaseModel

class ChatSession(BaseModel):
    id: str
    patient_id: str
    title: str
    created_at: str
    updated_at: str

class SessionManager:
    def __init__(self, db_path: str = ".data/checkpoints.sqlite"):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def _init_db(self):
        import os
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with self._get_conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_sessions_patient_id ON chat_sessions(patient_id)")
            conn.commit()

    def get_sessions(self, patient_id: str) -> list[ChatSession]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, patient_id, title, created_at, updated_at FROM chat_sessions WHERE patient_id = ? ORDER BY updated_at DESC",
                (patient_id,)
            )
            rows = cursor.fetchall()
            return [
                ChatSession(id=row[0], patient_id=row[1], title=row[2], created_at=row[3], updated_at=row[4])
                for row in rows
            ]

    def get_session(self, session_id: str) -> ChatSession | None:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, patient_id, title, created_at, updated_at FROM chat_sessions WHERE id = ?",
                (session_id,)
            )
            row = cursor.fetchone()
            if row:
                return ChatSession(id=row[0], patient_id=row[1], title=row[2], created_at=row[3], updated_at=row[4])
            return None

    def upsert_session(self, session_id: str, patient_id: str, title: str) -> ChatSession:
        now = datetime.now().isoformat()
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT created_at FROM chat_sessions WHERE id = ?", (session_id,))
            row = cursor.fetchone()
            if row:
                created_at = row[0]
                cursor.execute(
                    "UPDATE chat_sessions SET updated_at = ? WHERE id = ?",
                    (now, session_id)
                )
            else:
                created_at = now
                safe_title = title[:50] + "..." if len(title) > 50 else title
                if not safe_title.strip():
                    safe_title = "Cuộc trò chuyện mới"
                cursor.execute(
                    "INSERT INTO chat_sessions (id, patient_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (session_id, patient_id, safe_title, created_at, now)
                )
            conn.commit()
            return ChatSession(id=session_id, patient_id=patient_id, title=title, created_at=created_at, updated_at=now)

    def rename_session(self, session_id: str, title: str) -> bool:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            safe_title = title[:50] + "..." if len(title) > 50 else title
            cursor.execute(
                "UPDATE chat_sessions SET title = ?, updated_at = ? WHERE id = ?",
                (safe_title, datetime.now().isoformat(), session_id)
            )
            conn.commit()
            return cursor.rowcount > 0

    def delete_session(self, session_id: str) -> bool:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
            conn.commit()
            return cursor.rowcount > 0

session_manager = SessionManager()
