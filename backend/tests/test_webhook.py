"""Tests for webhook receiver — signature verification, idempotency, payload validation."""

import pytest
import hmac
import hashlib
import json
import os
import tempfile
from fastapi.testclient import TestClient

from backend.config import Settings, reset_settings
from backend import database


@pytest.fixture(autouse=True)
def setup_test_settings():
    """Set up test settings with a unique temp DB before each test."""
    reset_settings()
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    test_settings = Settings(
        openai_api_key="sk-proj-test-key",
        github_token="ghp_test_token",
        github_webhook_secret="test-secret",
        database_url=f"sqlite:///{db_path}",
    )
    database._settings = test_settings
    database.init_db()

    yield db_path

    if os.path.exists(db_path):
        os.remove(db_path)
    reset_settings()


@pytest.fixture
def client(setup_test_settings):
    """Test client with fresh app instance."""
    from backend.main import app
    with TestClient(app) as c:
        yield c


def make_webhook_payload(action="opened", issue_id=123, issue_number=42, event_type="issues"):
    """Create a valid webhook payload."""
    if event_type == "issues":
        return {
            "action": action,
            "issue": {
                "id": issue_id,
                "number": issue_number,
                "title": "Test issue",
                "body": "Test body",
                "user": {"login": "testuser"},
                "html_url": f"https://github.com/test/repo/issues/{issue_number}",
            },
            "repository": {"full_name": "test/repo"},
        }
    else:
        return {
            "action": action,
            "pull_request": {
                "id": issue_id,
                "number": issue_number,
                "title": "Test PR",
                "body": "Test PR body",
                "user": {"login": "testuser"},
                "html_url": f"https://github.com/test/repo/pull/{issue_number}",
            },
            "repository": {"full_name": "test/repo"},
        }


def sign_payload(payload: dict, secret: str = "test-secret") -> str:
    """Sign a payload with HMAC-SHA256."""
    body = json.dumps(payload).encode()
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return sig


class TestHealthCheck:
    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "ok"


class TestWebhookSignature:
    def test_valid_signature_accepted(self, client):
        payload = make_webhook_payload(issue_id=10001, issue_number=100)
        sig = sign_payload(payload)
        response = client.post(
            "/webhook",
            content=json.dumps(payload).encode(),
            headers={
                "X-Hub-Signature-256": sig,
                "X-GitHub-Event": "issues",
                "Content-Type": "application/json",
            },
        )
        assert response.status_code == 200
        assert response.json()["status"] == "queued"

    def test_invalid_signature_rejected(self, client):
        payload = make_webhook_payload(issue_id=10002, issue_number=101)
        response = client.post(
            "/webhook",
            content=json.dumps(payload).encode(),
            headers={
                "X-Hub-Signature-256": "sha256=invalid",
                "X-GitHub-Event": "issues",
                "Content-Type": "application/json",
            },
        )
        assert response.status_code == 401

    def test_missing_signature_rejected(self, client):
        payload = make_webhook_payload(issue_id=10003, issue_number=102)
        response = client.post(
            "/webhook",
            content=json.dumps(payload).encode(),
            headers={"X-GitHub-Event": "issues"},
        )
        assert response.status_code == 401


class TestWebhookPayloadValidation:
    def test_malformed_json_rejected(self, client):
        response = client.post(
            "/webhook",
            content=b"not json",
            headers={
                "X-Hub-Signature-256": sign_payload({"action": "opened", "issue": {"id": 1}}),
                "X-GitHub-Event": "issues",
            },
        )
        assert response.status_code in (400, 401)

    def test_missing_issue_data_rejected(self, client):
        payload = {"action": "opened", "repository": {"full_name": "test/repo"}}
        sig = sign_payload(payload)
        response = client.post(
            "/webhook",
            content=json.dumps(payload).encode(),
            headers={
                "X-Hub-Signature-256": sig,
                "X-GitHub-Event": "issues",
            },
        )
        assert response.status_code == 400

    def test_unknown_event_ignored(self, client):
        payload = {"action": "labeled", "issue": {"id": 10004}}
        sig = sign_payload(payload)
        response = client.post(
            "/webhook",
            content=json.dumps(payload).encode(),
            headers={
                "X-Hub-Signature-256": sig,
                "X-GitHub-Event": "issues",
            },
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ignored"


class TestWebhookIdempotency:
    def test_duplicate_webhook_skipped(self, client):
        payload = make_webhook_payload(issue_id=10005, issue_number=103)
        sig = sign_payload(payload)

        response1 = client.post(
            "/webhook",
            content=json.dumps(payload).encode(),
            headers={
                "X-Hub-Signature-256": sig,
                "X-GitHub-Event": "issues",
            },
        )
        assert response1.status_code == 200
        assert response1.json()["status"] == "queued"

        response2 = client.post(
            "/webhook",
            content=json.dumps(payload).encode(),
            headers={
                "X-Hub-Signature-256": sig,
                "X-GitHub-Event": "issues",
            },
        )
        assert response2.status_code == 200
        assert response2.json()["status"] == "already_processing"


class TestWebhookEventRouting:
    def test_pr_opened_routed(self, client):
        payload = make_webhook_payload(event_type="pull_request", issue_id=10006, issue_number=104)
        sig = sign_payload(payload)
        response = client.post(
            "/webhook",
            content=json.dumps(payload).encode(),
            headers={
                "X-Hub-Signature-256": sig,
                "X-GitHub-Event": "pull_request",
            },
        )
        assert response.status_code == 200
        assert response.json()["status"] == "queued"
