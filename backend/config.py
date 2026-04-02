"""
Centralized configuration for the Smart GitHub Triage Agent.
All environment variables are validated at startup via Pydantic BaseSettings.
Missing required vars cause immediate failure — no runtime surprises.
"""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import os


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Required
    openai_api_key: str = Field(..., description="OpenAI API key for GPT-4o calls")
    github_token: str = Field(..., description="GitHub Personal Access Token (repo scope)")
    github_webhook_secret: str = Field(..., description="Webhook HMAC secret from GitHub App config")

    # Optional with defaults
    auto_label_enabled: bool = Field(
        default=True,
        description="Enable auto-labeling when confidence >= 0.95",
    )
    auto_label_threshold: float = Field(
        default=0.95,
        ge=0.0,
        le=1.0,
        description="Confidence threshold for auto-labeling",
    )
    database_url: str = Field(
        default="sqlite:///./triage.db",
        description="SQLite database URL",
    )
    chroma_path: str = Field(
        default="./chroma_data",
        description="Path for Chroma persistent storage",
    )
    port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="Port for the FastAPI server",
    )
    embedding_model: str = Field(
        default="paraphrase-multilingual-MiniLM-L12-v2",
        description="Sentence transformer model for embeddings",
    )
    llm_model: str = Field(
        default="gpt-4o",
        description="OpenAI model for triage analysis",
    )
    max_workers: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum concurrent triage workers",
    )
    body_truncate_chars: int = Field(
        default=3000,
        ge=500,
        le=10000,
        description="Max characters of issue body sent to LLM",
    )
    diff_truncate_chars: int = Field(
        default=2000,
        ge=500,
        le=5000,
        description="Max characters of PR diff sent to LLM",
    )

    @field_validator("openai_api_key")
    @classmethod
    def validate_openai_key(cls, v: str) -> str:
        if not v.startswith("sk-") and not v.startswith("sk-proj-"):
            raise ValueError(
                "OPENAI_API_KEY must start with 'sk-' or 'sk-proj-'. "
                "Set it in your .env file."
            )
        return v

    @field_validator("github_token")
    @classmethod
    def validate_github_token(cls, v: str) -> str:
        if not v.startswith("ghp_") and not v.startswith("github_pat_"):
            raise ValueError(
                "GITHUB_TOKEN must start with 'ghp_' (classic PAT) or 'github_pat_' (fine-grained). "
                "Set it in your .env file."
            )
        return v


# Lazy singleton — import this everywhere
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create the settings singleton. Lazy to avoid import-time failures in tests."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Reset the settings singleton. Used in tests."""
    global _settings
    _settings = None


class _SettingsProxy:
    def __getattr__(self, name):
        return getattr(get_settings(), name)

    def __setattr__(self, name, value):
        setattr(get_settings(), name, value)


settings = _SettingsProxy()
