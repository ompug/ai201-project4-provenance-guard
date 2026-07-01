import json
import sqlite3
from pathlib import Path
from typing import Any


DB_PATH = Path("provenance_guard.db")


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS content (
                content_id TEXT PRIMARY KEY,
                creator_id TEXT NOT NULL,
                content_type TEXT NOT NULL,
                raw_content TEXT NOT NULL,
                attribution TEXT NOT NULL,
                confidence REAL NOT NULL,
                label TEXT NOT NULL,
                status TEXT NOT NULL,
                signal_scores TEXT NOT NULL,
                created_at TEXT NOT NULL,
                verified INTEGER NOT NULL DEFAULT 0,
                creator_reasoning TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_id TEXT NOT NULL,
                creator_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                content_type TEXT NOT NULL,
                attribution TEXT NOT NULL,
                confidence REAL NOT NULL,
                label TEXT NOT NULL,
                status TEXT NOT NULL,
                signal_scores TEXT NOT NULL,
                rationale TEXT,
                appeal_reasoning TEXT,
                timestamp TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS verified_creators (
                creator_id TEXT PRIMARY KEY,
                verification_content_id TEXT NOT NULL,
                verification_confidence REAL NOT NULL,
                verified_at TEXT NOT NULL
            )
            """
        )


def create_content(record: dict[str, Any]) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO content (
                content_id,
                creator_id,
                content_type,
                raw_content,
                attribution,
                confidence,
                label,
                status,
                signal_scores,
                created_at,
                verified,
                creator_reasoning
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["content_id"],
                record["creator_id"],
                record["content_type"],
                record["raw_content"],
                record["attribution"],
                record["confidence"],
                record["label"],
                record["status"],
                json.dumps(record["signal_scores"]),
                record["created_at"],
                int(record.get("verified", False)),
                record.get("creator_reasoning"),
            ),
        )


def update_content_status(content_id: str, status: str, creator_reasoning: str | None = None) -> bool:
    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE content
            SET status = ?, creator_reasoning = COALESCE(?, creator_reasoning)
            WHERE content_id = ?
            """,
            (status, creator_reasoning, content_id),
        )
        return cursor.rowcount > 0


def get_content(content_id: str) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM content WHERE content_id = ?",
            (content_id,),
        ).fetchone()

    if row is None:
        return None

    result = dict(row)
    result["signal_scores"] = json.loads(result["signal_scores"])
    result["verified"] = bool(result["verified"])
    return result


def is_creator_verified(creator_id: str) -> bool:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT creator_id FROM verified_creators WHERE creator_id = ?",
            (creator_id,),
        ).fetchone()
    return row is not None


def verify_creator(
    creator_id: str,
    verification_content_id: str,
    verification_confidence: float,
    verified_at: str,
) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO verified_creators (
                creator_id,
                verification_content_id,
                verification_confidence,
                verified_at
            ) VALUES (?, ?, ?, ?)
            ON CONFLICT(creator_id) DO UPDATE SET
                verification_content_id = excluded.verification_content_id,
                verification_confidence = excluded.verification_confidence,
                verified_at = excluded.verified_at
            """,
            (
                creator_id,
                verification_content_id,
                verification_confidence,
                verified_at,
            ),
        )


def write_audit_entry(entry: dict[str, Any]) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO audit_log (
                content_id,
                creator_id,
                event_type,
                content_type,
                attribution,
                confidence,
                label,
                status,
                signal_scores,
                rationale,
                appeal_reasoning,
                timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry["content_id"],
                entry["creator_id"],
                entry["event_type"],
                entry["content_type"],
                entry["attribution"],
                entry["confidence"],
                entry["label"],
                entry["status"],
                json.dumps(entry["signal_scores"]),
                entry.get("rationale"),
                entry.get("appeal_reasoning"),
                entry["timestamp"],
            ),
        )


def get_recent_log_entries(limit: int = 50) -> list[dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM audit_log
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    entries: list[dict[str, Any]] = []
    for row in rows:
        entry = dict(row)
        entry["signal_scores"] = json.loads(entry["signal_scores"])
        entries.append(entry)
    return entries


def get_dashboard_metrics() -> dict[str, Any]:
    with get_connection() as connection:
        verdict_rows = connection.execute(
            """
            SELECT attribution, COUNT(*) AS count
            FROM content
            GROUP BY attribution
            """
        ).fetchall()
        total_submissions = connection.execute(
            "SELECT COUNT(*) AS count FROM content"
        ).fetchone()["count"]
        appeal_count = connection.execute(
            "SELECT COUNT(*) AS count FROM content WHERE status = 'under_review'"
        ).fetchone()["count"]
        average_confidence = connection.execute(
            "SELECT COALESCE(AVG(confidence), 0) AS average_confidence FROM content"
        ).fetchone()["average_confidence"]
        verified_creators = connection.execute(
            "SELECT COUNT(*) AS count FROM verified_creators"
        ).fetchone()["count"]

    verdict_counts = {"likely_ai": 0, "likely_human": 0, "uncertain": 0}
    for row in verdict_rows:
        verdict_counts[row["attribution"]] = row["count"]

    appeal_rate = (appeal_count / total_submissions) if total_submissions else 0.0

    return {
        "verdict_counts": verdict_counts,
        "total_submissions": total_submissions,
        "appeal_count": appeal_count,
        "appeal_rate": round(appeal_rate, 3),
        "average_confidence": round(float(average_confidence or 0.0), 3),
        "verified_creators": verified_creators,
    }
