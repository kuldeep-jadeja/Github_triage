"""Tests for database operations — schema, CRUD, integrity, metrics."""

import pytest
import os
import tempfile

from backend import database
from backend import config as config_module
from backend.config import Settings, reset_settings


def _make_test_settings(db_path: str) -> Settings:
    """Create a Settings instance pointing to a specific test DB."""
    return Settings(
        openai_api_key="sk-proj-test",
        github_token="ghp_test_token",
        github_webhook_secret="test",
        database_url=f"sqlite:///{db_path}",
    )


@pytest.fixture
def temp_db():
    """Create a unique temporary SQLite database for each test."""
    reset_settings()
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    # Patch the config module's _settings so the proxy returns our test settings
    config_module._settings = _make_test_settings(db_path)
    database.init_db()
    yield db_path

    # Close all connections before removing the file (Windows file locking)
    import sqlite3
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.close()
    except Exception:
        pass

    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except PermissionError:
            pass  # Windows may still have a lock; acceptable for temp files
    reset_settings()


class TestDatabaseInit:
    def test_init_creates_tables(self, temp_db):
        conn = database.get_connection()
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = [t["name"] for t in tables]
        assert "triage_jobs" in table_names
        assert "llm_calls" in table_names
        conn.close()

    def test_init_idempotent(self, temp_db):
        database.init_db()
        database.init_db()
        conn = database.get_connection()
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        conn.close()
        assert len(tables) == 2


class TestDatabaseIntegrity:
    def test_check_integrity_healthy(self, temp_db):
        assert database.check_integrity() is True


class TestJobCRUD:
    def test_create_job(self, temp_db):
        job_id = database.create_job(
            issue_id=100,
            issue_number=1,
            repo_full_name="test/repo",
            event_type="issues.opened",
            title="Test issue",
            body="Test body",
            author="testuser",
        )
        assert job_id > 0

    def test_create_duplicate_job(self, temp_db):
        job_id1 = database.create_job(
            issue_id=200,
            issue_number=2,
            repo_full_name="test/repo",
            event_type="issues.opened",
        )
        assert job_id1 > 0

        job_id2 = database.create_job(
            issue_id=200,
            issue_number=2,
            repo_full_name="test/repo",
            event_type="issues.opened",
        )
        assert job_id2 == -1

    def test_get_job_by_issue_id(self, temp_db):
        database.create_job(
            issue_id=300,
            issue_number=3,
            repo_full_name="test/repo",
            event_type="issues.opened",
            title="Find me",
        )
        job = database.get_job_by_issue_id(300)
        assert job is not None
        assert job["title"] == "Find me"

    def test_get_nonexistent_job(self, temp_db):
        job = database.get_job_by_issue_id(9999)
        assert job is None

    def test_update_job(self, temp_db):
        job_id = database.create_job(
            issue_id=400,
            issue_number=4,
            repo_full_name="test/repo",
            event_type="issues.opened",
        )
        database.update_job(job_id, status="running", confidence=0.85)
        job = database.get_job(job_id)
        assert job["status"] == "running"
        assert job["confidence"] == 0.85

    def test_get_pending_jobs(self, temp_db):
        database.create_job(issue_id=501, issue_number=1, repo_full_name="test/repo", event_type="issues.opened")
        database.create_job(issue_id=502, issue_number=2, repo_full_name="test/repo", event_type="issues.opened")
        database.update_job(1, status="pending_review")
        database.update_job(2, status="pending_review")

        pending = database.get_pending_jobs()
        assert len(pending) == 2

    def test_get_recent_jobs(self, temp_db):
        for i in range(10):
            database.create_job(
                issue_id=600 + i,
                issue_number=i + 1,
                repo_full_name="test/repo",
                event_type="issues.opened",
            )
        recent = database.get_recent_jobs(limit=5)
        assert len(recent) == 5


class TestMetrics:
    def test_empty_metrics(self, temp_db):
        metrics = database.get_metrics()
        assert metrics["total_triaged"] == 0
        assert metrics["avg_confidence"] == 0.0

    def test_metrics_with_data(self, temp_db):
        database.create_job(issue_id=701, issue_number=1, repo_full_name="test/repo", event_type="issues.opened")
        database.update_job(1, status="executed", confidence=0.9)
        database.create_job(issue_id=702, issue_number=2, repo_full_name="test/repo", event_type="issues.opened")
        database.update_job(2, status="rejected", confidence=0.3)

        metrics = database.get_metrics()
        assert metrics["total_triaged"] == 2
        assert metrics["approved"] == 1
        assert metrics["rejected"] == 1
        assert metrics["avg_confidence"] == 0.6
