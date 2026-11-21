import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List

from werkzeug.security import generate_password_hash

from .config import Config


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    Config.DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(Config.DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin')),
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                created_at TEXT NOT NULL,
                source_name TEXT NOT NULL,
                source_type TEXT NOT NULL,
                word_count INTEGER NOT NULL,
                before_score REAL NOT NULL,
                before_label TEXT NOT NULL,
                after_score REAL NOT NULL,
                after_label TEXT NOT NULL,
                total_changes INTEGER NOT NULL,
                change_percentage REAL NOT NULL,
                changed_sentences INTEGER NOT NULL,
                total_sentences INTEGER NOT NULL,
                original_text TEXT NOT NULL,
                humanized_text TEXT NOT NULL,
                changes_json TEXT NOT NULL,
                cliche_hits_json TEXT NOT NULL,
                before_metrics_json TEXT NOT NULL DEFAULT '{}',
                after_metrics_json TEXT NOT NULL DEFAULT '{}',
                engine_mode TEXT NOT NULL DEFAULT 'heuristic'
            )
            """
        )
        columns = {row[1] for row in conn.execute("PRAGMA table_info(analyses)")}
        migrations = {
            "user_id": "INTEGER REFERENCES users(id) ON DELETE CASCADE",
            "before_metrics_json": "TEXT NOT NULL DEFAULT '{}'",
            "after_metrics_json": "TEXT NOT NULL DEFAULT '{}'",
            "engine_mode": "TEXT NOT NULL DEFAULT 'heuristic'",
        }
        for column, definition in migrations.items():
            if column not in columns:
                conn.execute(f"ALTER TABLE analyses ADD COLUMN {column} {definition}")
        conn.execute("CREATE INDEX IF NOT EXISTS analyses_user_id_idx ON analyses(user_id, id DESC)")

        admin_username = os.getenv("VERITONE_ADMIN_USER", "").strip()
        admin_password = os.getenv("VERITONE_ADMIN_PASS", "")
        if admin_username and admin_password:
            conn.execute(
                """INSERT OR IGNORE INTO users (username, password_hash, role, created_at)
                   VALUES (?, ?, 'admin', ?)""",
                (
                    admin_username,
                    generate_password_hash(admin_password),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
        conn.commit()


def create_user(username: str, password_hash: str) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
            (username, password_hash, datetime.now(timezone.utc).isoformat()),
        )
        return int(cursor.lastrowid)


def get_user_by_id(user_id: int) -> Dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def get_user_by_username(username: str) -> Dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ? COLLATE NOCASE", (username,)
        ).fetchone()
        return dict(row) if row else None


def list_users() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT u.id, u.username, u.role, u.is_active, u.created_at,
                      COUNT(a.id) AS run_count, COALESCE(SUM(a.word_count), 0) AS word_count
               FROM users u LEFT JOIN analyses a ON a.user_id = u.id
               GROUP BY u.id ORDER BY u.id"""
        ).fetchall()
        return [dict(row) for row in rows]


def update_user(user_id: int, role: str, is_active: bool) -> bool:
    with get_connection() as conn:
        cursor = conn.execute(
            "UPDATE users SET role = ?, is_active = ? WHERE id = ?",
            (role, int(is_active), user_id),
        )
        return cursor.rowcount > 0


def save_analysis(record: Dict[str, Any], user_id: int) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO analyses (
                user_id, created_at, source_name, source_type, word_count,
                before_score, before_label, after_score, after_label,
                total_changes, change_percentage, changed_sentences, total_sentences,
                original_text, humanized_text, changes_json, cliche_hits_json,
                before_metrics_json, after_metrics_json, engine_mode
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                record["created_at"],
                record["source_name"],
                record["source_type"],
                record["word_count"],
                record["before_score"],
                record["before_label"],
                record["after_score"],
                record["after_label"],
                record["total_changes"],
                record["change_percentage"],
                record["changed_sentences"],
                record["total_sentences"],
                record["original_text"],
                record["humanized_text"],
                json.dumps(record["changes"]),
                json.dumps(record["cliche_hits"]),
                json.dumps(record.get("before_metrics", {})),
                json.dumps(record.get("after_metrics", {})),
                record.get("engine_mode", "heuristic"),
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


def list_analyses(user_id: int | None = None, limit: int = 100) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        if user_id is None:
            return []
        rows = conn.execute(
            """
            SELECT id, created_at, source_name, source_type, word_count,
                   before_score, before_label, after_score, after_label,
                   total_changes, change_percentage, changed_sentences, total_sentences
            FROM analyses WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def get_analysis(analysis_id: int, user_id: int | None = None) -> Dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM analyses WHERE id = ? AND user_id = ?",
            (analysis_id, user_id),
        ).fetchone()
        if not row:
            return None
        item = dict(row)
        item["changes"] = json.loads(item.pop("changes_json"))
        item["cliche_hits"] = json.loads(item.pop("cliche_hits_json"))
        item["before_metrics"] = json.loads(item.pop("before_metrics_json"))
        item["after_metrics"] = json.loads(item.pop("after_metrics_json"))
        return item


def get_any_analysis_owner(analysis_id: int) -> int | None:
    with get_connection() as conn:
        row = conn.execute("SELECT user_id FROM analyses WHERE id = ?", (analysis_id,)).fetchone()
        return int(row["user_id"]) if row and row["user_id"] is not None else None


def delete_analysis(analysis_id: int, user_id: int | None = None) -> bool:
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM analyses WHERE id = ? AND user_id = ?", (analysis_id, user_id)
        )
        conn.commit()
        return cursor.rowcount > 0


def get_admin_overview() -> Dict[str, Any]:
    with get_connection() as conn:
        row = conn.execute(
            """SELECT (SELECT COUNT(*) FROM users) AS total_users,
                      COUNT(*) AS total_runs, COALESCE(SUM(word_count), 0) AS total_words,
                      COALESCE(AVG(before_score - after_score), 0) AS average_score_shift
               FROM analyses"""
        ).fetchone()
        return dict(row)


def list_all_analyses(limit: int = 200) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT a.id, a.created_at, a.source_name, a.source_type, a.word_count,
                      a.before_score, a.after_score, a.total_changes, a.change_percentage,
                      u.username, a.user_id
               FROM analyses a LEFT JOIN users u ON u.id = a.user_id
               ORDER BY a.id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]