"""
Test configuration — sets environment variables via pytest_configure hook,
which runs BEFORE test collection. This ensures the Settings singleton
can be created when test modules import backend.config.
"""

import os


def pytest_configure(config):
    """Set test env vars before any test module is collected."""
    os.environ.setdefault("OPENAI_API_KEY", "sk-proj-test-key")
    os.environ.setdefault("GITHUB_TOKEN", "ghp_test_token")
    os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-secret")
