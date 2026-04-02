"""
Rule-based safety layer for the triage agent.
Overrides or constrains the LLM's suggestions based on configurable policies.
"""

import logging
from typing import List, Dict, Any, Optional

from backend.config import settings
from backend.logging_config import get_logger

logger = get_logger(__name__)


class TriagePolicy:
    """
    Rules that override or constrain the LLM's suggestions.
    All rules are evaluated in order; the first matching rule wins.
    """

    BLOCKED_ACTIONS = {"close", "lock", "transfer", "delete"}
    MAX_LABELS = 4

    @classmethod
    def apply(
        cls,
        triage_result,
        proposed_actions: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Apply policy rules to the triage result and proposed actions.

        Returns:
            {
                "actions": filtered list of actions,
                "needs_review": bool,
                "auto_applicable": bool,
                "warning": optional warning message,
            }
        """
        filtered_actions = []
        warning = None

        # Rule 1: Block destructive actions
        for action in proposed_actions:
            action_type = action.get("type", "")
            if action_type in cls.BLOCKED_ACTIONS:
                logger.warning(f"Blocked action: {action_type}")
                continue
            filtered_actions.append(action)

        # Rule 2: Limit number of labels
        if hasattr(triage_result, "labels") and len(triage_result.labels) > cls.MAX_LABELS:
            triage_result.labels = triage_result.labels[:cls.MAX_LABELS]
            warning = f"Limited labels to {cls.MAX_LABELS}"
            logger.info(f"Limited labels from {len(proposed_actions)} to {cls.MAX_LABELS}")

        # Rule 3: Confidence-based routing
        confidence = getattr(triage_result, "confidence", 0.0)
        needs_review = confidence < settings.auto_label_threshold

        # Rule 4: Auto-label eligibility
        auto_applicable = (
            settings.auto_label_enabled
            and confidence >= settings.auto_label_threshold
            and not needs_review
            and not warning
        )

        return {
            "actions": filtered_actions,
            "needs_review": needs_review,
            "auto_applicable": auto_applicable,
            "warning": warning,
        }

    @classmethod
    def validate_labels(cls, labels: List[str], available_labels: List[str]) -> List[str]:
        """Filter labels to only those that exist in the repo."""
        available_set = set(available_labels)
        valid = [l for l in labels if l in available_set]
        invalid = [l for l in labels if l not in available_set]
        if invalid:
            logger.warning(f"Filtered out invalid labels: {invalid}")
        return valid
