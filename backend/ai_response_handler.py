# -*- coding: utf-8 -*-
"""Helpers for parsing and validating AI JSON responses."""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


_CODE_BLOCK_PATTERN = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)


def clean_ai_json_response(text: str) -> str:
    """Strip markdown fences/preamble/postamble from an AI response."""

    if not text:
        return ""

    cleaned = str(text).strip()

    # Remove all markdown code blocks iteratively to handle multiple fences
    while True:
        match = _CODE_BLOCK_PATTERN.search(cleaned)
        if not match:
            break
        inner = match.group(1).strip()
        cleaned = (
            cleaned[: match.start()] + inner + cleaned[match.end() :]
        ).strip()

    # Remove any preamble before the first opening brace and trailing text
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end >= start:
        cleaned = cleaned[start : end + 1]

    return cleaned.strip()


def extract_json_from_text(text: str) -> Optional[str]:
    """Extract the JSON-like substring from within other surrounding text."""

    if not text:
        return None

    cleaned = str(text)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None

    return cleaned[start : end + 1]


def _try_load_json(candidate: str) -> Optional[Dict[str, Any]]:
    if not candidate:
        return None
    try:
        loaded = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    return loaded if isinstance(loaded, dict) else None


def parse_ai_response_safely(response_text: str) -> Dict[str, Any]:
    """Attempt to parse an AI response into JSON with multiple fallbacks."""

    raw_text = (response_text or "").strip()

    direct = _try_load_json(raw_text)
    if direct is not None:
        return direct

    logger.warning("Direct JSON parsing failed. Trying cleaned content.")
    cleaned = clean_ai_json_response(raw_text)
    cleaned_parsed = _try_load_json(cleaned)
    if cleaned_parsed is not None:
        return cleaned_parsed

    logger.warning("Cleaning the AI response was insufficient. Extracting braces content.")
    extracted = extract_json_from_text(cleaned)
    extracted_parsed = _try_load_json(extracted or "")
    if extracted_parsed is not None:
        return extracted_parsed

    return {"error": "JSON parse failed", "raw": raw_text}


def validate_analysis_response(data: Dict[str, Any]) -> bool:
    """Validate that the AI analysis contains the mandatory structure."""

    if not isinstance(data, dict):
        return False

    report_id = data.get("report_id")
    measured = data.get("measured_values")
    overall = data.get("overall_summary")

    if not report_id or not isinstance(measured, dict) or not isinstance(overall, dict):
        return False

    left_dummy = measured.get("left_dummy")
    right_dummy = measured.get("right_dummy")
    required_summary_keys = {"total_tests", "passed", "failed", "success_rate"}

    if not isinstance(left_dummy, dict) or not isinstance(right_dummy, dict):
        return False

    if not required_summary_keys.issubset(set(overall.keys())):
        return False

    return True


__all__ = [
    "clean_ai_json_response",
    "extract_json_from_text",
    "parse_ai_response_safely",
    "validate_analysis_response",
]
