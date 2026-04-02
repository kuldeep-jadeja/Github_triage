"""
SQLite database operations for the Smart GitHub Triage Agent.
Schema: triage_jobs (state + decisions), llm_calls (cost tracking).
Includes startup integrity check and auto-recovery from corruption.
"""

import sqlite3
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from backend.config import settings

logger = logging.getLogger(__name__)


def get_connection() -> sqlite3.Connection:
    """Get a database connection with WAL mode for better concurrency."""
    conn = sqlite3.connect(
        settings.database_url.replace("sqlite:///", ""),
        timeout=30,  # 30s timeout for lock retries
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Initialize the database schema. Safe to call multiple times."""
    conn = get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS triage_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                issue_id INTEGER UNIQUE NOT NULL,
                issue_number INTEGER NOT NULL,
                repo_full_name TEXT NOT NULL,
                event_type TEXT NOT NULL DEFAULT 'issues.opened',
                status TEXT NOT NULL DEFAULT 'queued',
                title TEXT,
                body TEXT,
                author TEXT,
                language_detected TEXT,
                suggested_labels TEXT,
                suggested_priority TEXT,
                confidence REAL,
                reasoning TEXT,
                draft_comment TEXT,
                critique_notes TEXT,
                error TEXT,
                trace_log TEXT,
                version INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                approved_by TEXT,
                approved_at TEXT,
                executed_at TEXT,
                original_draft TEXT,
                edited_draft TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_triage_jobs_status ON triage_jobs(status);
            CREATE INDEX IF NOT EXISTS idx_triage_jobs_confidence ON triage_jobs(confidence);
            CREATE INDEX IF NOT EXISTS idx_triage_jobs_created ON triage_jobs(created_at);
            CREATE INDEX IF NOT EXISTS idx_triage_jobs_event ON triage_jobs(event_type);

            CREATE TABLE IF NOT EXISTS llm_calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trace_id TEXT NOT NULL,
                issue_id INTEGER NOT NULL,
                call_type TEXT NOT NULL,
                model TEXT NOT NULL,
                input_tokens INTEGER,
                output_tokens INTEGER,
                latency_ms INTEGER,
                error TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_llm_calls_trace ON llm_calls(trace_id);
            CREATE INDEX IF NOT EXISTS idx_llm_calls_issue ON llm_calls(issue_id);
        """)
        conn.commit()
        logger.info("Database schema initialized")
    finally:
        conn.close()


def check_integrity() -> bool:
    """Check SQLite database integrity. Returns True if healthy."""
    try:
        conn = get_connection()
        try:
            result = conn.execute("PRAGMA integrity_check").fetchone()
            return result[0] == "ok"
        finally:
            conn.close()
    except sqlite3.DatabaseError as e:
        logger.error(f"Database integrity check failed: {e}")
        return False


def recreate_db() -> None:
    """Recreate the database from scratch. USE WITH CAUTION — destroys all data."""
    db_path = settings.database_url.replace("sqlite:///", "")
    import os
    if os.path.exists(db_path):
        os.remove(db_path)
        logger.warning(f"Database file removed: {db_path}")
    init_db()
    logger.info("Database recreated from scratch")


def create_job(
    issue_id: int,
    issue_number: int,
    repo_full_name: str,
    event_type: str,
    title: str = "",
    body: str = "",
    author: str = "",
) -> int:
    """Create a new triage job. Returns the job ID."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """INSERT INTO triage_jobs
               (issue_id, issue_number, repo_full_name, event_type, title, body, author, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'queued')""",
            (issue_id, issue_number, repo_full_name, event_type, title, body, author),
        )
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        logger.warning(f"Duplicate job for issue_id={issue_id}, skipping")
        return -1
    finally:
        conn.close()


def update_job(job_id: int, **kwargs) -> None:
    """Update a triage job's fields."""
    if not kwargs:
        return
    set_clause = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values())
    values.append(datetime.now(timezone.utc).isoformat())
    values.append(job_id)

    conn = get_connection()
    try:
        conn.execute(
            f"UPDATE triage_jobs SET {set_clause}, updated_at = ? WHERE id = ?",
            values,
        )
        conn.commit()
    finally:
        conn.close()


def get_job_by_issue_id(issue_id: int) -> Optional[dict]:
    """Get a triage job by GitHub issue ID."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM triage_jobs WHERE issue_id = ?", (issue_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_job(job_id: int) -> Optional[dict]:
    """Get a triage job by internal ID."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM triage_jobs WHERE id = ?", (job_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_pending_jobs() -> list[dict]:
    """Get all jobs pending human review."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM triage_jobs WHERE status = 'pending_review' ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_recent_jobs(limit: int = 50) -> list[dict]:
    """Get recent jobs for history/audit log."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM triage_jobs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def log_llm_call(
    trace_id: str,
    issue_id: int,
    call_type: str,
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    latency_ms: int = 0,
    error: Optional[str] = None,
) -> None:
    """Log an LLM API call for cost tracking."""
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO llm_calls
               (trace_id, issue_id, call_type, model, input_tokens, output_tokens, latency_ms, error)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (trace_id, issue_id, call_type, model, input_tokens, output_tokens, latency_ms, error),
        )
        conn.commit()
    finally:
        conn.close()


def get_metrics() -> dict:
    """Get aggregate metrics for the dashboard."""
    conn = get_connection()
    try:
        total = conn.execute("SELECT COUNT(*) FROM triage_jobs").fetchone()[0]
        approved = conn.execute(
            "SELECT COUNT(*) FROM triage_jobs WHERE status = 'executed'"
        ).fetchone()[0]
        rejected = conn.execute(
            "SELECT COUNT(*) FROM triage_jobs WHERE status = 'rejected'"
        ).fetchone()[0]
        avg_conf = conn.execute(
            "SELECT AVG(confidence) FROM triage_jobs WHERE confidence IS NOT NULL"
        ).fetchone()[0] or 0.0
        auto_labeled = conn.execute(
            "SELECT COUNT(*) FROM triage_jobs WHERE status = 'auto_labeled'"
        ).fetchone()[0]

        total_tokens = conn.execute(
            "SELECT COALESCE(SUM(input_tokens + output_tokens), 0) FROM llm_calls"
        ).fetchone()[0]

        return {
            "total_triaged": total,
            "approved": approved,
            "rejected": rejected,
            "auto_labeled": auto_labeled,
            "avg_confidence": round(avg_conf, 3),
            "total_tokens": total_tokens,
            "approval_rate": round(approved / max(total - auto_labeled, 1), 3),
        }
    finally:
        conn.close()
