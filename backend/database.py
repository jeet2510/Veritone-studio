import json
import sqlite3
from typing import Any, Dict, List

from .config import Config


def get_connection() -> sqlite3.Connection:
    Config.DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(Config.DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                cliche_hits_json TEXT NOT NULL
            )
            """
        )
        conn.commit()


def save_analysis(record: Dict[str, Any]) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO analyses (
                created_at, source_name, source_type, word_count,
                before_score, before_label, after_score, after_label,
                total_changes, change_percentage, changed_sentences, total_sentences,
                original_text, humanized_text, changes_json, cliche_hits_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
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
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


def list_analyses(limit: int = 100) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, created_at, source_name, source_type, word_count,
                   before_score, before_label, after_score, after_label,
                   total_changes, change_percentage, changed_sentences, total_sentences
            FROM analyses
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_analysis(analysis_id: int) -> Dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM analyses WHERE id = ?",
            (analysis_id,),
        ).fetchone()
        if not row:
            return None
        item = dict(row)
        item["changes"] = json.loads(item.pop("changes_json"))
        item["cliche_hits"] = json.loads(item.pop("cliche_hits_json"))
        return item


def delete_analysis(analysis_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM analyses WHERE id = ?", (analysis_id,))
        conn.commit()
        return cursor.rowcount > 0