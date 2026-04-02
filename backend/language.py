"""
Language detection and translation for multi-language issue triage.
Supports: ES, ZH, JA, FR, DE with translation fallback.
"""

import logging
from typing import Optional, Tuple

from langdetect import detect, LangDetectException

from backend.config import settings
from backend.llm_service import call_llm_with_retry
from backend.logging_config import get_logger

logger = get_logger(__name__)

SUPPORTED_LANGUAGES = {
    "es": "Spanish",
    "zh": "Chinese",
    "ja": "Japanese",
    "fr": "French",
    "de": "German",
}


def detect_language(text: str) -> Tuple[str, float]:
    """
    Detect the language of the given text.
    Returns (language_code, confidence).
    Returns ("en", 1.0) for English or if detection fails.
    """
    if not text or len(text.strip()) < 10:
        return ("en", 1.0)

    try:
        lang = detect(text)
        # langdetect doesn't provide confidence directly, but we can
        # use detect_langs for probability distribution
        from langdetect import detect_langs
        langs = detect_langs(text)
        if langs:
            top_lang = langs[0]
            return (top_lang.lang, top_lang.prob)
        return (lang, 0.5)
    except LangDetectException:
        logger.debug("Language detection failed, defaulting to English")
        return ("en", 0.0)


def is_supported_language(lang_code: str) -> bool:
    """Check if the language is in our supported set."""
    return lang_code in SUPPORTED_LANGUAGES


def translate_to_english(text: str, source_language: str, trace_id: str = "", issue_id: int = 0) -> Optional[str]:
    """
    Translate text from source language to English using LLM.
    Preserves technical terms, code snippets, and error messages.
    """
    lang_name = SUPPORTED_LANGUAGES.get(source_language, source_language)

    messages = [
        {
            "role": "system",
            "content": f"""Translate the following text from {lang_name} to English.
Preserve technical terms, code snippets, and error messages exactly as written.
Do not add or remove any information. Only output the translation, nothing else.""",
        },
        {"role": "user", "content": text[:3000]},
    ]

    result = call_llm_with_retry(
        messages=messages,
        response_format=None,  # Free-form text, no structured output
        max_retries=2,
        temperature=0.1,
        max_tokens=2000,
        call_type="translation",
        trace_id=trace_id,
        issue_id=issue_id,
    )

    if result is None:
        logger.warning(f"Translation failed for {lang_name} text")
        return None

    # For free-form translation, the raw response is the translation
    return result


def translate_from_english(english_text: str, target_language: str, trace_id: str = "", issue_id: int = 0) -> Optional[str]:
    """
    Translate English text to the target language.
    Used for translating the response back to the issue author's language.
    """
    lang_name = SUPPORTED_LANGUAGES.get(target_language, target_language)

    messages = [
        {
            "role": "system",
            "content": f"""Translate the following English text to {lang_name}.
Maintain a friendly, professional tone appropriate for GitHub issue responses.
Only output the translation, nothing else.""",
        },
        {"role": "user", "content": english_text},
    ]

    result = call_llm_with_retry(
        messages=messages,
        response_format=None,
        max_retries=2,
        temperature=0.1,
        max_tokens=1000,
        call_type="response_translation",
        trace_id=trace_id,
        issue_id=issue_id,
    )

    if result is None:
        logger.warning(f"Response translation to {lang_name} failed")
        return None

    return result
