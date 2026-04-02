"""
LangGraph state machine orchestrator for the Smart GitHub Triage Agent.
Nodes: INTAKE → ANALYZE → LANGUAGE → (ENGLISH | TRANSLATE | FLAG) → SEARCH → DECIDE → DRAFT → CRITIQUE → POLICY → (AUTO-LABEL | PENDING_REVIEW) → COMPLETE

ASCII diagram of the state machine:

  ┌──────────┐   ┌──────────┐   ┌──────────────────┐
  │ INTAKE   │──►│ ANALYZE  │──►│ DETECT_LANGUAGE   │
  └──────────┘   └──────────┘   └─────────┬────────┘
                                          │
                          ┌───────────────┼───────────────┐
                          ▼               ▼               ▼
                   ┌──────────┐   ┌──────────┐   ┌──────────┐
                   │ ENGLISH  │   │TRANSLATE │   │  FLAG    │
                   │ PATH     │   │ + TRIAGE │   │ UNKNOWN  │
                   └────┬─────┘   └────┬─────┘   └────┬─────┘
                        │              │              │
                        └──────────────┼──────────────┘
                                       ▼
                              ┌──────────────────┐
                              │ SEARCH_SIMILAR    │
                              │ (+ template check)│
                              └─────────┬────────┘
                                        │
  ┌──────────────┐   ┌──────────┐      │
  │ DRAFT_REPLY  │◄──│ DECIDE   │◄─────┘
  └──────┬───────┘   └──────────┘
         │
  ┌──────▼───────┐   ┌──────────────┐
  │ SELF_CRITIQUE│──►│POLICY_ENGINE │
  └──────────────┘   └──────┬───────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │AUTO-LABEL│ │PENDING_  │ │  ERROR   │
        │(>=0.95)  │ │ REVIEW   │ │  PATH    │
        └────┬─────┘ └────┬─────┘ └────┬─────┘
             │            │            │
             └────────────┼────────────┘
                          ▼
                     ┌──────────┐
                     │ COMPLETE │
                     └──────────┘
"""

import uuid
import logging
from typing import Literal

from langgraph.graph import StateGraph, END

from backend.config import settings
from backend.models import TriageState, TriageAnalysis
from backend.llm_service import call_llm_with_retry
from backend.prompts import (
    build_triage_system_prompt,
    build_draft_comment_prompt,
    build_self_critique_prompt,
    build_translation_prompt,
    build_response_translation_prompt,
)
from backend.vector_db import search_similar, embed_and_store_issue
from backend.github_tools import GitHubTools
from backend.language import detect_language, is_supported_language, translate_to_english
from backend.policy import TriagePolicy
from backend.logging_config import TraceContext, get_logger

logger = get_logger(__name__)


def _log_node(state: TriageState, node_name: str, detail: str = ""):
    """Log a state transition with trace context."""
    TraceContext.set(state.trace_id)
    state.trace_log.append({
        "node": node_name,
        "detail": detail,
        "trace_id": state.trace_id,
    })
    logger.info(
        f"Node: {node_name}",
        extra={"extra_context": {
            "node": node_name,
            "issue_number": state.issue_number,
            "detail": detail,
            "trace_id": state.trace_id,
        }},
    )


def intake_node(state: TriageState) -> dict:
    """Validate and normalize input from the webhook."""
    _log_node(state, "INTAKE", f"issue #{state.issue_number}, body length={len(state.body)}")

    updates = {
        "trace_id": state.trace_id or str(uuid.uuid4()),
    }
    TraceContext.set(updates["trace_id"])

    # Detect empty or image-only issues
    body_stripped = state.body.strip()
    if not body_stripped:
        updates["is_empty"] = True
    elif body_stripped.count("![") > 0 and len(body_stripped.replace("![", "").replace("]", "").replace("(", "").replace(")", "").strip()) < 50:
        updates["is_image_only"] = True

    # Truncate body for LLM
    if len(state.body) > settings.body_truncate_chars:
        updates["body"] = state.body[:settings.body_truncate_chars]
        state.trace_log.append({
            "node": "INTAKE",
            "detail": f"Body truncated from {len(state.body)} to {settings.body_truncate_chars} chars",
            "trace_id": state.trace_id,
        })

    return updates


def analyze_node(state: TriageState) -> dict:
    """Call LLM to extract structured triage analysis."""
    _log_node(state, "ANALYZE")

    tools = GitHubTools(repo_name=state.repo_full_name)
    available_labels = tools.get_available_labels()

    # Fetch similar issues if not already done
    similar_issues = state.similar_issues

    system_prompt = build_triage_system_prompt(
        repo_name=state.repo_full_name,
        available_labels=available_labels,
        similar_issues=similar_issues,
    )
    user_prompt = f"Issue Title: {state.title}\n\nIssue Body:\n{state.body}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    result = call_llm_with_retry(
        messages=messages,
        response_format=TriageAnalysis,
        max_retries=2,
        temperature=0.1,
        max_tokens=1000,
        call_type="analysis",
        trace_id=state.trace_id,
        issue_id=state.issue_id,
    )

    if result is None:
        # Fallback triage
        return {
            "suggested_labels": ["needs-triage"],
            "suggested_priority": "P2",
            "confidence": 0.0,
            "reasoning": "LLM analysis failed after retries",
            "missing_info": [],
            "available_labels": available_labels,
        }

    # Post-validation: filter out hallucinated labels
    valid_labels = TriagePolicy.validate_labels(result.labels, available_labels)

    return {
        "suggested_labels": valid_labels,
        "suggested_priority": result.priority,
        "confidence": result.confidence,
        "reasoning": result.reasoning,
        "missing_info": result.missing_info,
        "available_labels": available_labels,
        "extracted_info": {
            "is_feature_request": result.is_feature_request,
            "is_question": result.is_question,
            "severity_signals": result.severity_signals,
        },
    }


def detect_language_node(state: TriageState) -> dict:
    """Detect the language of the issue body."""
    _log_node(state, "DETECT_LANGUAGE")

    lang_code, confidence = detect_language(state.body)
    updates = {
        "language_detected": lang_code,
    }

    if lang_code != "en" and is_supported_language(lang_code):
        _log_node(state, "DETECT_LANGUAGE", f"Detected {lang_code} (confidence={confidence:.2f})")
    elif lang_code != "en":
        _log_node(state, "DETECT_LANGUAGE", f"Unsupported language: {lang_code}")

    return updates


def translate_node(state: TriageState) -> dict:
    """Translate non-English issue to English for triage."""
    _log_node(state, "TRANSLATE", f"Translating from {state.language_detected}")

    translated = translate_to_english(
        text=state.body,
        source_language=state.language_detected,
        trace_id=state.trace_id,
        issue_id=state.issue_id,
    )

    if translated:
        return {"body": translated}

    # Translation failed — continue with original text
    logger.warning("Translation failed, continuing with original text")
    return {}


def search_similar_node(state: TriageState) -> dict:
    """Search for similar past issues in the vector DB."""
    _log_node(state, "SEARCH_SIMILAR")

    similar = search_similar(state.title, state.body, top_k=5)

    # Check issue templates
    tools = GitHubTools(repo_name=state.repo_full_name)
    templates = tools.get_issue_templates()
    template_validation = {"templates_found": len(templates)}

    return {
        "similar_issues": similar,
        "template_validation": template_validation,
    }


def decide_node(state: TriageState) -> dict:
    """Apply policy engine and determine next action."""
    _log_node(state, "DECIDE")

    # Build proposed actions
    proposed_actions = []
    for label in state.suggested_labels:
        proposed_actions.append({"type": "label", "value": label})
    proposed_actions.append({"type": "comment", "value": "draft_pending"})

    # Apply policy
    from backend.models import TriageAnalysis as _TA
    class _MockResult:
        def __init__(self, labels, confidence):
            self.labels = labels
            self.confidence = confidence

    mock_result = _MockResult(state.suggested_labels, state.confidence)
    policy_result = TriagePolicy.apply(mock_result, proposed_actions)

    return {
        "actions_proposed": policy_result["actions"],
        "status": "auto_labeled" if policy_result["auto_applicable"] else "pending_review",
    }


def draft_reply_node(state: TriageState) -> dict:
    """Generate a draft comment for the issue."""
    _log_node(state, "DRAFT_REPLY")

    similar_formatted = state.similar_issues[:3]

    system_prompt = build_draft_comment_prompt(
        issue_number=state.issue_number,
        author=state.author,
        labels=state.suggested_labels,
        priority=state.suggested_priority,
        similar_issues=similar_formatted,
        missing_info=state.missing_info,
    )
    user_prompt = f"Issue Title: {state.title}\n\nIssue Body:\n{state.body}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    result = call_llm_with_retry(
        messages=messages,
        response_format=None,
        max_retries=2,
        temperature=0.3,
        max_tokens=500,
        call_type="draft",
        trace_id=state.trace_id,
        issue_id=state.issue_id,
    )

    if result is None:
        # Fallback draft
        draft = f"Thank you for reporting this issue (#{state.issue_number}). Our team will review it shortly."
    else:
        draft = str(result)

    return {"draft_comment": draft}


def self_critique_node(state: TriageState) -> dict:
    """Self-critique the triage output and draft comment."""
    _log_node(state, "SELF_CRITIQUE")

    system_prompt = build_self_critique_prompt(
        triage_json=str({
            "labels": state.suggested_labels,
            "priority": state.suggested_priority,
            "confidence": state.confidence,
            "reasoning": state.reasoning,
        }),
        draft_comment=state.draft_comment,
        available_labels=state.available_labels,
    )
    user_prompt = "Review the above and respond with PASS or REVISE: [specific issue]"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    result = call_llm_with_retry(
        messages=messages,
        response_format=None,
        max_retries=1,
        temperature=0.1,
        max_tokens=200,
        call_type="critique",
        trace_id=state.trace_id,
        issue_id=state.issue_id,
    )

    critique = str(result) if result else "PASS"
    return {"critique_notes": critique}


def complete_node(state: TriageState) -> dict:
    """Final node — store the issue in vector DB and mark complete."""
    _log_node(state, "COMPLETE")

    # Store the issue in vector DB for future similarity searches
    try:
        embed_and_store_issue({
            "number": state.issue_number,
            "title": state.title,
            "body": state.body,
            "state": "open",
            "labels": state.suggested_labels,
            "created_at": "",
            "html_url": f"https://github.com/{state.repo_full_name}/issues/{state.issue_number}",
        })
    except Exception as e:
        logger.error(f"Failed to store issue in vector DB: {e}")

    return {"status": state.status}


# --- Routing functions ---

def route_after_language(state: TriageState) -> Literal["translate", "search_similar", "search_similar"]:
    """Route based on detected language."""
    if state.language_detected != "en" and is_supported_language(state.language_detected):
        return "translate"
    return "search_similar"


def route_after_analyze(state: TriageState) -> Literal["search_similar", "draft_reply"]:
    """Handle edge cases before full processing."""
    if state.is_empty or state.is_image_only:
        return "draft_reply"
    return "search_similar"


def build_triage_graph():
    """Build and compile the LangGraph state machine."""
    graph = StateGraph(TriageState)

    # Add nodes
    graph.add_node("intake", intake_node)
    graph.add_node("analyze", analyze_node)
    graph.add_node("detect_language", detect_language_node)
    graph.add_node("translate", translate_node)
    graph.add_node("search_similar", search_similar_node)
    graph.add_node("decide", decide_node)
    graph.add_node("draft_reply", draft_reply_node)
    graph.add_node("self_critique", self_critique_node)
    graph.add_node("complete", complete_node)

    # Set entry point
    graph.set_entry_point("intake")

    # Linear flow: intake → analyze → detect_language
    graph.add_edge("intake", "analyze")
    graph.add_edge("analyze", "detect_language")

    # Language routing
    graph.add_conditional_edges(
        "detect_language",
        route_after_language,
        {"translate": "translate", "search_similar": "search_similar"},
    )
    graph.add_edge("translate", "search_similar")

    # Edge case routing from analyze
    graph.add_conditional_edges(
        "search_similar",
        lambda s: "draft_reply" if (s.is_empty or s.is_image_only) else "decide",
        {"draft_reply": "draft_reply", "decide": "decide"},
    )

    # Main flow
    graph.add_edge("decide", "draft_reply")
    graph.add_edge("draft_reply", "self_critique")
    graph.add_edge("self_critique", "complete")
    graph.add_edge("complete", END)

    return graph.compile()
