"""
LLM service with retry, exponential backoff, fallback, and structured output.
Single entry point for all LLM calls — no direct OpenAI usage elsewhere.
"""

import time
import logging
from typing import Type, TypeVar, Optional

from openai import OpenAI, APITimeoutError, RateLimitError, AuthenticationError, APIConnectionError, BadRequestError
from pydantic import BaseModel

from backend.config import settings
from backend.logging_config import get_logger
from backend.database import log_llm_call

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


def call_llm_with_retry(
    messages: list[dict],
    response_format: Type[T],
    max_retries: int = 2,
    temperature: float = 0.1,
    max_tokens: int = 1000,
    call_type: str = "analysis",
    trace_id: str = "",
    issue_id: int = 0,
) -> Optional[T]:
    """
    Call OpenAI with structured output, retry on transient failures,
    and return a safe fallback on total failure.

    Args:
        messages: List of message dicts for the chat completion.
        response_format: Pydantic model for structured output.
        max_retries: Number of retry attempts (total attempts = max_retries + 1).
        temperature: Sampling temperature (low for classification).
        max_tokens: Maximum tokens in the response.
        call_type: Label for logging/cost tracking (e.g., "analysis", "draft", "critique").
        trace_id: Trace ID for log correlation.
        issue_id: GitHub issue ID for cost tracking.

    Returns:
        Parsed Pydantic model on success, None on total failure.
    """
    client = OpenAI(api_key=settings.openai_api_key)

    for attempt in range(max_retries + 1):
        start = time.time()
        try:
            response = client.beta.chat.completions.parse(
                model=settings.llm_model,
                messages=messages,
                response_format=response_format,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            latency_ms = int((time.time() - start) * 1000)
            result = response.choices[0].message.parsed

            input_tokens = response.usage.prompt_tokens if response.usage else 0
            output_tokens = response.usage.completion_tokens if response.usage else 0

            log_llm_call(
                trace_id=trace_id,
                issue_id=issue_id,
                call_type=call_type,
                model=settings.llm_model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
            )

            logger.info(
                f"LLM call succeeded: {call_type}",
                extra={"extra_context": {
                    "call_type": call_type,
                    "latency_ms": latency_ms,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "trace_id": trace_id,
                }},
            )
            return result

        except AuthenticationError as e:
            latency_ms = int((time.time() - start) * 1000)
            log_llm_call(
                trace_id=trace_id,
                issue_id=issue_id,
                call_type=call_type,
                model=settings.llm_model,
                latency_ms=latency_ms,
                error=f"AuthenticationError: {e}",
            )
            logger.critical(
                "LLM authentication failed — check OPENAI_API_KEY",
                extra={"extra_context": {"error": str(e), "trace_id": trace_id}},
            )
            return None

        except (APITimeoutError, RateLimitError, APIConnectionError) as e:
            latency_ms = int((time.time() - start) * 1000)
            if attempt < max_retries:
                backoff = 2 ** attempt
                logger.warning(
                    f"LLM call failed (attempt {attempt + 1}/{max_retries + 1}), retrying in {backoff}s",
                    extra={"extra_context": {"error": str(e), "trace_id": trace_id}},
                )
                time.sleep(backoff)
            else:
                log_llm_call(
                    trace_id=trace_id,
                    issue_id=issue_id,
                    call_type=call_type,
                    model=settings.llm_model,
                    latency_ms=latency_ms,
                    error=str(e),
                )
                logger.error(
                    f"LLM call failed after {max_retries + 1} attempts: {call_type}",
                    extra={"extra_context": {"error": str(e), "trace_id": trace_id}},
                )
                return None

        except BadRequestError as e:
            latency_ms = int((time.time() - start) * 1000)
            log_llm_call(
                trace_id=trace_id,
                issue_id=issue_id,
                call_type=call_type,
                model=settings.llm_model,
                latency_ms=latency_ms,
                error=str(e),
            )
            logger.error(
                f"LLM bad request: {call_type}",
                extra={"extra_context": {"error": str(e), "trace_id": trace_id}},
            )
            return None

        except Exception as e:
            latency_ms = int((time.time() - start) * 1000)
            if attempt < max_retries:
                backoff = 2 ** attempt
                logger.warning(
                    f"LLM unexpected error (attempt {attempt + 1}/{max_retries + 1}), retrying",
                    extra={"extra_context": {"error": str(e), "trace_id": trace_id}},
                )
                time.sleep(backoff)
            else:
                log_llm_call(
                    trace_id=trace_id,
                    issue_id=issue_id,
                    call_type=call_type,
                    model=settings.llm_model,
                    latency_ms=latency_ms,
                    error=str(e),
                )
                logger.error(
                    f"LLM call failed after {max_retries + 1} attempts: {call_type}",
                    extra={"extra_context": {"error": str(e), "trace_id": trace_id}},
                )
                return None

    return None
