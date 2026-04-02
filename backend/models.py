"""
Pydantic models for the Smart GitHub Triage Agent.
Used for structured LLM output, state management, and API validation.
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any


class TriageAnalysis(BaseModel):
    """Structured output from the triage LLM call."""
    labels: List[str] = Field(
        description="Labels to apply. MUST be from the provided available_labels list."
    )
    priority: str = Field(
        description="One of: P0, P1, P2, P3"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Overall confidence in the triage decision"
    )
    reasoning: str = Field(
        description="2-3 sentence explanation of why these labels and priority"
    )
    missing_info: List[str] = Field(
        description="Specific questions to ask the issue author"
    )
    is_feature_request: bool = Field(
        default=False,
        description="Whether this is a feature request rather than a bug"
    )
    is_question: bool = Field(
        default=False,
        description="Whether this is primarily a question"
    )
    severity_signals: List[str] = Field(
        default_factory=list,
        description="What signals indicate severity (crash, data loss, security, etc.)"
    )

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        if v not in ("P0", "P1", "P2", "P3"):
            raise ValueError(f"Priority must be P0, P1, P2, or P3, got '{v}'")
        return v


class TriageState(BaseModel):
    """LangGraph state for a triage job."""
    # Input
    issue_id: int
    issue_number: int
    repo_full_name: str
    event_type: str = "issues.opened"
    title: str = ""
    body: str = ""
    author: str = ""
    trace_id: str = ""

    # Processing
    language_detected: str = "en"
    is_empty: bool = False
    is_image_only: bool = False
    extracted_info: Dict[str, Any] = {}
    similar_issues: List[Dict[str, Any]] = []
    available_labels: List[str] = []
    template_validation: Dict[str, Any] = {}

    # PR-specific
    pr_changed_files: List[str] = []
    pr_diff_summary: str = ""
    suggested_reviewers: List[str] = []

    # Decisions
    suggested_labels: List[str] = []
    suggested_priority: str = "P2"
    missing_info: List[str] = []
    duplicate_candidate: Optional[Dict[str, Any]] = None
    confidence: float = 0.0
    reasoning: str = ""

    # Output
    draft_comment: str = ""
    critique_notes: str = ""
    actions_proposed: List[Dict[str, Any]] = []

    # Meta
    status: str = "queued"
    error: Optional[str] = None
    trace_log: List[Dict[str, Any]] = []


class WebhookPayload(BaseModel):
    """Validated webhook payload structure."""
    action: str
    issue_id: int
    issue_number: int
    repo_full_name: str
    title: str = ""
    body: str = ""
    author: str = ""
    html_url: str = ""
    state: str = "open"
    labels: List[str] = []
    is_pull_request: bool = False


class DashboardReview(BaseModel):
    """Review item for the dashboard API."""
    id: int
    issue_id: int
    issue_number: int
    title: str
    author: str
    suggested_labels: List[str]
    suggested_priority: str
    confidence: float
    reasoning: str
    similar_issues: List[Dict[str, Any]]
    missing_info: List[str]
    status: str
    created_at: str
    trace_id: str = ""
