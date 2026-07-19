"""Database models for FillForm."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from typing import Any, Iterable

DATABASE_FILENAME = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "fillform.db")
)


def get_database_path(db_path: str | None = None) -> str:
    return db_path or DATABASE_FILENAME


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    connection = sqlite3.connect(get_database_path(db_path), detect_types=sqlite3.PARSE_DECLTYPES)
    connection.row_factory = sqlite3.Row
    return connection


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _json_loads(value: str | None) -> Any:
    if value is None or value == "":
        return []
    return json.loads(value)


def initialize_database(db_path: str | None = None) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_type TEXT NOT NULL,
                filename TEXT,
                text TEXT NOT NULL,
                summary TEXT,
                sentence_count INTEGER,
                keyword_count INTEGER,
                keywords TEXT,
                deadline_candidates TEXT,
                has_deadline_signal INTEGER NOT NULL DEFAULT 0,
                match_score REAL,
                reminder_plan TEXT,
                form_type TEXT,
                status TEXT NOT NULL DEFAULT 'new',
                verification_required INTEGER NOT NULL DEFAULT 1,
                submitted INTEGER NOT NULL DEFAULT 0,
                submitted_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                email TEXT,
                phone TEXT,
                organization TEXT,
                resume_text TEXT,
                resume_version INTEGER NOT NULL DEFAULT 1,
                tags TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                submission_id INTEGER NOT NULL,
                deadline TEXT,
                suggested_timing TEXT,
                calendar_event_id TEXT,
                notes TEXT,
                created_at TEXT NOT NULL,
                triggered_at TEXT,
                FOREIGN KEY(submission_id) REFERENCES submissions(id)
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS resume_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_description TEXT,
                original_resume TEXT,
                optimized_resume TEXT,
                changes_summary TEXT,
                created_at TEXT NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0
            );
            """
        )


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    if "keywords" in result:
        result["keywords"] = _json_loads(result["keywords"])
    if "deadline_candidates" in result:
        result["deadline_candidates"] = _json_loads(result["deadline_candidates"])
    if "reminder_plan" in result:
        result["reminder_plan"] = json.loads(result["reminder_plan"]) if result["reminder_plan"] else {}
    return result


def save_submission(
    source_type: str,
    text: str,
    filename: str | None = None,
    summary: str | None = None,
    sentence_count: int | None = None,
    keyword_count: int | None = None,
    keywords: Iterable[str] | None = None,
    deadline_candidates: Iterable[str] | None = None,
    has_deadline_signal: bool = False,
    match_score: float | None = None,
    reminder_plan: dict[str, Any] | None = None,
    form_type: str | None = None,
    status: str = "new",
    verification_required: bool = True,
    submitted: bool = False,
    db_path: str | None = None,
) -> int:
    now = _now_iso()
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO submissions (
                source_type,
                filename,
                text,
                summary,
                sentence_count,
                keyword_count,
                keywords,
                deadline_candidates,
                has_deadline_signal,
                match_score,
                reminder_plan,
                form_type,
                status,
                verification_required,
                submitted,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                source_type,
                filename,
                text,
                summary or "",
                sentence_count or 0,
                keyword_count or 0,
                _json_dumps(list(keywords or [])),
                _json_dumps(list(deadline_candidates or [])),
                1 if has_deadline_signal else 0,
                match_score,
                _json_dumps(reminder_plan or {}),
                form_type,
                status,
                1 if verification_required else 0,
                1 if submitted else 0,
                now,
                now,
            ),
        )
        return cursor.lastrowid


def update_submission_status(
    submission_id: int,
    status: str,
    submitted: bool | None = None,
    submitted_at: str | None = None,
    match_score: float | None = None,
    note: str | None = None,
    db_path: str | None = None,
) -> None:
    updates: list[str] = ["status = ?", "updated_at = ?"]
    params: list[Any] = [status, _now_iso()]
    if submitted is not None:
        updates.append("submitted = ?")
        params.append(1 if submitted else 0)
    if submitted_at is not None:
        updates.append("submitted_at = ?")
        params.append(submitted_at)
    if match_score is not None:
        updates.append("match_score = ?")
        params.append(match_score)
    if note is not None:
        updates.append("reminder_plan = ?")
        params.append(_json_dumps({"note": note}))
    params.append(submission_id)

    with get_connection(db_path) as conn:
        conn.execute(
            f"UPDATE submissions SET {', '.join(updates)} WHERE id = ?;",
            params,
        )


def record_reminder(
    submission_id: int,
    deadline: str,
    suggested_timing: Iterable[str] | None = None,
    calendar_event_id: str | None = None,
    notes: str | None = None,
    db_path: str | None = None,
) -> int:
    now = _now_iso()
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO reminders (
                submission_id,
                deadline,
                suggested_timing,
                calendar_event_id,
                notes,
                created_at,
                triggered_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (
                submission_id,
                deadline,
                _json_dumps(list(suggested_timing or [])),
                calendar_event_id,
                notes,
                now,
                None,
            ),
        )
        return cursor.lastrowid


def save_profile(
    name: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    organization: str | None = None,
    resume_text: str | None = None,
    tags: Iterable[str] | None = None,
    db_path: str | None = None,
) -> int:
    now = _now_iso()
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO profiles (
                name,
                email,
                phone,
                organization,
                resume_text,
                resume_version,
                tags,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                name,
                email,
                phone,
                organization,
                resume_text,
                1,
                _json_dumps(list(tags or [])),
                now,
                now,
            ),
        )
        return cursor.lastrowid


def save_resume_request(
    job_description: str | None = None,
    original_resume: str | None = None,
    optimized_resume: str | None = None,
    changes_summary: str | None = None,
    completed: bool = False,
    db_path: str | None = None,
) -> int:
    now = _now_iso()
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO resume_requests (
                job_description,
                original_resume,
                optimized_resume,
                changes_summary,
                created_at,
                completed
            ) VALUES (?, ?, ?, ?, ?, ?);
            """,
            (
                job_description,
                original_resume,
                optimized_resume,
                changes_summary,
                now,
                1 if completed else 0,
            ),
        )
        return cursor.lastrowid


def get_submission(submission_id: int, db_path: str | None = None) -> dict[str, Any] | None:
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM submissions WHERE id = ?;", (submission_id,)).fetchone()
        return _row_to_dict(row) if row else None


def list_submissions(status: str | None = None, db_path: str | None = None) -> list[dict[str, Any]]:
    query = "SELECT * FROM submissions"
    params: list[Any] = []
    if status is not None:
        query += " WHERE status = ?"
        params.append(status)
    query += " ORDER BY created_at DESC;"

    with get_connection(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
        return [_row_to_dict(row) for row in rows]
