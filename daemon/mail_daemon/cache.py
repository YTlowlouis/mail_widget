"""Cache SQLite indexé par Message-ID. Un mail déjà vu n'est jamais renvoyé à l'API."""
from __future__ import annotations

import datetime
import sqlite3
from pathlib import Path
from typing import Iterable, NamedTuple, Optional

_SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    message_id TEXT PRIMARY KEY,
    thread_key TEXT NOT NULL,
    seen_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_thread_key ON messages(thread_key);

CREATE TABLE IF NOT EXISTS threads (
    thread_key TEXT PRIMARY KEY,
    resume TEXT NOT NULL,
    urgence TEXT NOT NULL,
    raison TEXT NOT NULL,
    otp_code TEXT,
    processed_at TEXT NOT NULL
);
"""


class ThreadRecord(NamedTuple):
    thread_key: str
    resume: str
    urgence: str
    raison: str
    otp_code: Optional[str]
    processed_at: str


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class Cache:
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "Cache":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def known_message_ids(self, message_ids: Iterable[str]) -> set[str]:
        ids = list(message_ids)
        if not ids:
            return set()
        placeholders = ",".join("?" for _ in ids)
        rows = self._conn.execute(
            f"SELECT message_id FROM messages WHERE message_id IN ({placeholders})", ids
        ).fetchall()
        return {row["message_id"] for row in rows}

    def thread_key_of(self, message_id: str) -> Optional[str]:
        row = self._conn.execute(
            "SELECT thread_key FROM messages WHERE message_id = ?", (message_id,)
        ).fetchone()
        return row["thread_key"] if row else None

    def mark_messages_seen(self, message_ids: Iterable[str], thread_key: str) -> None:
        now = _now()
        self._conn.executemany(
            "INSERT OR REPLACE INTO messages (message_id, thread_key, seen_at) VALUES (?, ?, ?)",
            [(mid, thread_key, now) for mid in message_ids],
        )
        self._conn.commit()

    def upsert_thread(
        self, thread_key: str, resume: str, urgence: str, raison: str, otp_code: Optional[str] = None
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO threads (thread_key, resume, urgence, raison, otp_code, processed_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(thread_key) DO UPDATE SET
                resume = excluded.resume,
                urgence = excluded.urgence,
                raison = excluded.raison,
                otp_code = excluded.otp_code,
                processed_at = excluded.processed_at
            """,
            (thread_key, resume, urgence, raison, otp_code, _now()),
        )
        self._conn.commit()

    def get_thread(self, thread_key: str) -> Optional[ThreadRecord]:
        row = self._conn.execute(
            "SELECT thread_key, resume, urgence, raison, otp_code, processed_at FROM threads WHERE thread_key = ?",
            (thread_key,),
        ).fetchone()
        return ThreadRecord(**dict(row)) if row else None
