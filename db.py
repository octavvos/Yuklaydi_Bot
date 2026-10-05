"""Foydalanuvchilar va yuklashlar tarixi uchun oddiy SQLite baza."""

import sqlite3
from datetime import datetime, timedelta

from config import DB_PATH

_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
_conn.row_factory = sqlite3.Row


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def init() -> None:
    _conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY,
            username    TEXT,
            full_name   TEXT,
            language    TEXT,
            first_seen  TEXT NOT NULL,
            last_seen   TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS downloads (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            url        TEXT NOT NULL,
            mode       TEXT NOT NULL,      -- video | audio
            ok         INTEGER NOT NULL,   -- 1 muvaffaqiyatli, 0 xato
            title      TEXT,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_downloads_user ON downloads(user_id);
        """
    )
    _conn.commit()


def upsert_user(user_id: int, username: str | None, full_name: str, language: str | None) -> bool:
    """Foydalanuvchini saqlaydi/yangilaydi. Yangi foydalanuvchi bo'lsa True qaytaradi."""
    now = _now()
    is_new = _conn.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone() is None
    _conn.execute(
        """
        INSERT INTO users (id, username, full_name, language, first_seen, last_seen)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            username = excluded.username,
            full_name = excluded.full_name,
            language = excluded.language,
            last_seen = excluded.last_seen
        """,
        (user_id, username, full_name, language, now, now),
    )
    _conn.commit()
    return is_new


def log_download(user_id: int, url: str, mode: str, ok: bool, title: str | None = None) -> None:
    _conn.execute(
        "INSERT INTO downloads (user_id, url, mode, ok, title, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, url, mode, int(ok), title, _now()),
    )
    _conn.commit()


def count_users() -> int:
    return _conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def list_users(offset: int, limit: int) -> list[sqlite3.Row]:
    return _conn.execute(
        """
        SELECT u.*, (SELECT COUNT(*) FROM downloads d WHERE d.user_id = u.id AND d.ok = 1) AS dl_count
        FROM users u
        ORDER BY u.last_seen DESC
        LIMIT ? OFFSET ?
        """,
        (limit, offset),
    ).fetchall()


def all_users() -> list[sqlite3.Row]:
    return list_users(0, -1)


def get_user(user_id: int) -> sqlite3.Row | None:
    return _conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def find_users(query: str) -> list[sqlite3.Row]:
    q = f"%{query.lstrip('@')}%"
    return _conn.execute(
        "SELECT * FROM users WHERE username LIKE ? OR full_name LIKE ? ORDER BY last_seen DESC LIMIT 20",
        (q, q),
    ).fetchall()


def user_downloads(user_id: int, limit: int = 10) -> list[sqlite3.Row]:
    return _conn.execute(
        "SELECT * FROM downloads WHERE user_id = ? ORDER BY id DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()


def user_download_stats(user_id: int) -> sqlite3.Row:
    return _conn.execute(
        """
        SELECT
            COUNT(*) AS total,
            COALESCE(SUM(ok = 1 AND mode = 'video'), 0) AS video,
            COALESCE(SUM(ok = 1 AND mode = 'audio'), 0) AS audio,
            COALESCE(SUM(ok = 0), 0) AS failed
        FROM downloads WHERE user_id = ?
        """,
        (user_id,),
    ).fetchone()


def stats() -> dict:
    today = datetime.now().strftime("%Y-%m-%d")
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    one = lambda sql, *a: _conn.execute(sql, a).fetchone()[0]  # noqa: E731
    return {
        "users": one("SELECT COUNT(*) FROM users"),
        "new_today": one("SELECT COUNT(*) FROM users WHERE first_seen >= ?", today),
        "active_today": one("SELECT COUNT(*) FROM users WHERE last_seen >= ?", today),
        "active_week": one("SELECT COUNT(*) FROM users WHERE last_seen >= ?", week_ago),
        "downloads": one("SELECT COUNT(*) FROM downloads WHERE ok = 1"),
        "downloads_today": one("SELECT COUNT(*) FROM downloads WHERE ok = 1 AND created_at >= ?", today),
        "video": one("SELECT COUNT(*) FROM downloads WHERE ok = 1 AND mode = 'video'"),
        "audio": one("SELECT COUNT(*) FROM downloads WHERE ok = 1 AND mode = 'audio'"),
        "failed": one("SELECT COUNT(*) FROM downloads WHERE ok = 0"),
    }
