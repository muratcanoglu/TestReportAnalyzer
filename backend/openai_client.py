# -*- coding: utf-8 -*-
"""Thin wrapper around the OpenAI Responses API."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional, Tuple

from openai import OpenAI

try:  # pragma: no cover - prefer absolute imports under package execution
    from backend.ai_response_handler import (
        parse_ai_response_safely,
        validate_analysis_response,
    )
    from backend.config import AI_OPENAI_MODEL, AI_TIMEOUT_S, OPENAI_API_KEY
    from backend.detailed_prompt_template import build_simplified_analysis_prompt
    from backend.measurement_analysis import build_measurement_fallback_from_payload
    from backend.structured_analyzer import build_structured_data_for_ai
except ImportError:  # pragma: no cover - fallback for script execution
    try:
        from .ai_response_handler import (  # type: ignore
            parse_ai_response_safely,
            validate_analysis_response,
        )
        from .config import AI_OPENAI_MODEL, AI_TIMEOUT_S, OPENAI_API_KEY  # type: ignore
        from .detailed_prompt_template import (  # type: ignore
            build_simplified_analysis_prompt,
        )
        from .measurement_analysis import (  # type: ignore
            build_measurement_fallback_from_payload,
        )
        from .structured_analyzer import build_structured_data_for_ai  # type: ignore
    except ImportError:  # pragma: no cover - running from repository root
        from ai_response_handler import (  # type: ignore
            parse_ai_response_safely,
            validate_analysis_response,
        )
        from config import AI_OPENAI_MODEL, AI_TIMEOUT_S, OPENAI_API_KEY  # type: ignore
        from detailed_prompt_template import (  # type: ignore
            build_simplified_analysis_prompt,
        )
        from measurement_analysis import (  # type: ignore
            build_measurement_fallback_from_payload,
        )
        from structured_analyzer import build_structured_data_for_ai  # type: ignore

try:  # pragma: no cover - optional dependency in some environments
    from backend.parsers.kielt_parser import parse_page_2_metadata
except ImportError:  # pragma: no cover - fallback for script execution
    try:
        from .parsers.kielt_parser import parse_page_2_metadata  # type: ignore
    except ImportError:  # pragma: no cover - running from repository root
        try:
            from parsers.kielt_parser import parse_page_2_metadata  # type: ignore
        except ImportError:  # pragma: no cover - parser not available
            parse_page_2_metadata = None  # type: ignore

PREFERRED_OPENAI_MODELS = ("gpt-4-turbo-preview", "gpt-4")
_client: OpenAI | None = None
logger = logging.getLogger(__name__)


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        if not OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY missing")
        timeout_value = max(AI_TIMEOUT_S, 120)
        _client = OpenAI(api_key=OPENAI_API_KEY, timeout=timeout_value)
    return _client


def _coerce_to_dict(value: object) -> Optional[Dict[str, Any]]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            loaded = json.loads(stripped)
        except json.JSONDecodeError:
            return {"raw": value}
        if isinstance(loaded, dict):
            return loaded
        return None
    return None


def _extract_payload(text: str) -> Tuple[str, Optional[str], Optional[Dict[str, Any]]]:
    pdf_text = text
    pdf_path: Optional[str] = None
    structured_metadata: Optional[Dict[str, Any]] = None

    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            pdf_text = str(
                payload.get("pdf_text")
                or payload.get("text")
                or payload.get("content")
                or text
            )
            pdf_path_value = payload.get("pdf_path") or payload.get("path")
            if isinstance(pdf_path_value, str):
                pdf_path = pdf_path_value
            structured_metadata = _coerce_to_dict(
                payload.get("structured_metadata")
                or payload.get("page_2_metadata")
            )

    return pdf_text, pdf_path, structured_metadata


def _load_structured_metadata(
    provided_metadata: Optional[Dict[str, Any]],
    pdf_path: Optional[str],
) -> Optional[Dict[str, Any]]:
    if provided_metadata is not None:
        return provided_metadata

    if pdf_path and parse_page_2_metadata is not None:
        try:
            metadata = parse_page_2_metadata(pdf_path)
            if isinstance(metadata, dict):
                return metadata
            return {"raw": metadata}
        except Exception as exc:  # pragma: no cover - runtime safety
            return {"status": "error", "error": str(exc)}

    return None


def analyze_with_openai(text: str) -> Dict[str, Any]:
    """Generate a detailed JSON analysis for the provided PDF text via OpenAI."""

    pdf_text, pdf_path, provided_metadata = _extract_payload(text)
    structured_metadata = _load_structured_metadata(provided_metadata, pdf_path)
    if not pdf_text:
        pdf_text = text

    structured_payload = build_structured_data_for_ai(
        pdf_path,
        fallback_text=pdf_text,
        metadata=structured_metadata,
    )
    prompt = build_simplified_analysis_prompt(structured_payload)
    measurement_fallback = build_measurement_fallback_from_payload(
        structured_payload,
        default_report_id=pdf_path or "openai-analysis",
    )

    client = _get_client()
    model_name = AI_OPENAI_MODEL or PREFERRED_OPENAI_MODELS[0]
    if model_name not in PREFERRED_OPENAI_MODELS:
        model_name = PREFERRED_OPENAI_MODELS[0]

    response = client.responses.create(
        model=model_name,
        temperature=0.0,
        max_output_tokens=4000,
        input=[
            {
                "role": "system",
                "content": (
                    "You are a test report analyzer. You MUST respond ONLY with valid JSON.\n\n"
                    "CRITICAL RULES:\n"
                    "- Response MUST start with {\n"
                    "- Response MUST end with }\n"
                    "- NO markdown code blocks\n"
                    "- NO explanatory text before or after JSON\n"
                    "- NO comments inside JSON\n"
                    "- Use double quotes for strings\n"
                    "- Ensure all brackets and braces are balanced\n\n"
                    "If you cannot extract a value, use null instead of omitting the field."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    )

    output_text = getattr(response, "output_text", None)
    if output_text is None:
        try:
            parts = []
            for item in getattr(response, "output", []) or []:
                content = getattr(item, "content", None)
                if content is None:
                    parts.append(str(item))
                    continue
                if isinstance(content, (list, tuple)):
                    for block in content:
                        block_text = getattr(block, "text", None)
                        if block_text:
                            parts.append(str(block_text))
                else:
                    parts.append(str(content))
            output_text = "\n".join(parts)
        except Exception:  # pragma: no cover - fallback best effort
            output_text = str(response)

    raw_text = (output_text or "").strip()
    parsed_data = parse_ai_response_safely(
        raw_text,
        fallback_data=measurement_fallback,
    )

    if not validate_analysis_response(parsed_data):
        logger.error("Invalid AI response: %s", parsed_data)
        return {
            "error": "AI returned invalid format",
            "raw_response": raw_text[:500],
        }

    return parsed_data
