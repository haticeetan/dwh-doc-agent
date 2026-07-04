import sqlite3
import threading
import os
from datetime import datetime, timedelta, timezone

_lock = threading.Lock()

MAX_TURNS = 6          # intent_parser'a gönderilen son 6 mesaj (3 alışveriş çifti)
RETENTION_DAYS = 7


def _now_iso() -> str:
    """UTC zamanını timezone suffix'i olmadan döner: '2026-07-04T22:00:00.123456'
    Frontend 'Z' ekleyerek parse eder; +00:00 suffix'i geçersiz tarih üretir."""
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')


def _cutoff_iso() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)).strftime('%Y-%m-%dT%H:%M:%S.%f')


_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "conversations.db")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db() -> None:
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT    NOT NULL,
                role       TEXT    NOT NULL,
                content    TEXT    NOT NULL,
                intent     TEXT    NOT NULL DEFAULT '',
                created_at TEXT    NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_session ON messages (session_id, created_at)")

        # Mevcut DB'de intent kolonu yoksa ekle
        cols = {row[1] for row in conn.execute("PRAGMA table_info(messages)")}
        if "intent" not in cols:
            conn.execute("ALTER TABLE messages ADD COLUMN intent TEXT NOT NULL DEFAULT ''")


def _purge_old() -> None:
    with _get_conn() as conn:
        conn.execute("DELETE FROM messages WHERE created_at < ?", (_cutoff_iso(),))


_init_db()
_purge_old()


def add_message(session_id: str, role: str, content: str, intent: str = "") -> None:
    with _lock:
        now = _now_iso()
        with _get_conn() as conn:
            conn.execute(
                "INSERT INTO messages (session_id, role, content, intent, created_at) VALUES (?, ?, ?, ?, ?)",
                (session_id, role, content, intent, now),
            )


def get_history(session_id: str) -> list[dict]:
    """Intent parser için son MAX_TURNS mesajı döner."""
    cutoff = _cutoff_iso()
    with _lock:
        with _get_conn() as conn:
            rows = conn.execute(
                """
                SELECT role, content FROM (
                    SELECT role, content, created_at
                    FROM messages
                    WHERE session_id = ? AND created_at >= ?
                    ORDER BY created_at DESC
                    LIMIT ?
                ) ORDER BY created_at ASC
                """,
                (session_id, cutoff, MAX_TURNS),
            ).fetchall()
    return [{"role": row["role"], "content": row["content"]} for row in rows]


def get_sessions() -> list[dict]:
    """Sidebar için: her session'ın ilk kullanıcı mesajını başlık olarak döner."""
    cutoff = _cutoff_iso()
    with _lock:
        with _get_conn() as conn:
            rows = conn.execute(
                """
                SELECT
                    session_id,
                    MIN(CASE WHEN role = 'user' THEN content END) AS title,
                    MAX(created_at) AS last_message_at
                FROM messages
                WHERE created_at >= ?
                GROUP BY session_id
                ORDER BY last_message_at DESC
                LIMIT 50
                """,
                (cutoff,),
            ).fetchall()
    return [
        {
            "session_id": row["session_id"],
            "title": (row["title"] or "Sohbet")[:60],
            "last_message_at": row["last_message_at"],
        }
        for row in rows
    ]


def get_session_messages(session_id: str) -> list[dict]:
    """Bir session'ın tüm mesajlarını sırayla döner."""
    cutoff = _cutoff_iso()
    with _lock:
        with _get_conn() as conn:
            rows = conn.execute(
                """
                SELECT role, content, intent, created_at
                FROM messages
                WHERE session_id = ? AND created_at >= ?
                ORDER BY created_at ASC
                """,
                (session_id, cutoff),
            ).fetchall()
    return [
        {
            "role": row["role"],
            "content": row["content"],
            "intent": row["intent"] or None,
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def clear_history(session_id: str) -> None:
    with _lock:
        with _get_conn() as conn:
            conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
