"""Tests for config module — validation, defaults, error cases."""

import pytest
from pydantic import ValidationError

from backend.config import Settings, reset_settings


@pytest.fixture(autouse=True)
def reset_settings_fixture():
    """Reset settings singleton before each test."""
    reset_settings()
    yield
    reset_settings()


class TestSettingsValidation:
    def test_valid_settings(self):
        settings = Settings(
            openai_api_key="sk-proj-test-key",
            github_token="ghp_test_token",
            github_webhook_secret="test-secret",
        )
        assert settings.openai_api_key == "sk-proj-test-key"
        assert settings.auto_label_enabled is True
        assert settings.port == 8000

    def test_missing_required_fields(self):
        # Clear env vars so Settings() has no fallback
        import os
        old = {k: os.environ.pop(k, None) for k in ("OPENAI_API_KEY", "GITHUB_TOKEN", "GITHUB_WEBHOOK_SECRET")}
        try:
            reset_settings()
            with pytest.raises(ValidationError):
                Settings()
        finally:
            for k, v in old.items():
                if v is not None:
                    os.environ[k] = v

    def test_invalid_openai_key(self):
        with pytest.raises(ValidationError, match="OPENAI_API_KEY"):
            Settings(
                openai_api_key="invalid-key",
                github_token="ghp_test",
                github_webhook_secret="test",
            )

    def test_invalid_github_token(self):
        with pytest.raises(ValidationError, match="GITHUB_TOKEN"):
            Settings(
                openai_api_key="sk-proj-test",
                github_token="invalid-token",
                github_webhook_secret="test",
            )

    def test_fine_grained_pat_accepted(self):
        settings = Settings(
            openai_api_key="sk-proj-test",
            github_token="github_pat_test",
            github_webhook_secret="test",
        )
        assert settings.github_token == "github_pat_test"

    def test_defaults(self):
        settings = Settings(
            openai_api_key="sk-proj-test",
            github_token="ghp_test",
            github_webhook_secret="test",
        )
        assert settings.auto_label_enabled is True
        assert settings.auto_label_threshold == 0.95
        assert settings.database_url == "sqlite:///./triage.db"
        assert settings.port == 8000
        assert settings.max_workers == 3
        assert settings.embedding_model == "paraphrase-multilingual-MiniLM-L12-v2"

    def test_custom_values(self):
        settings = Settings(
            openai_api_key="sk-proj-test",
            github_token="ghp_test",
            github_webhook_secret="test",
            auto_label_enabled=False,
            port=9000,
            max_workers=5,
        )
        assert settings.auto_label_enabled is False
        assert settings.port == 9000
        assert settings.max_workers == 5
