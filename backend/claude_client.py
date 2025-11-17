# -*- coding: utf-8 -*-
"""Thin wrapper around the Anthropic Messages API."""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional, Tuple

from anthropic import Anthropic

try:  # pragma: no cover - prefer absolute imports in package context
    from backend.config import AI_ANTHROPIC_MODEL, AI_TIMEOUT_S, ANTHROPIC_API_KEY
    from backend.detailed_prompt_template import build_detailed_analysis_prompt
except ImportError:  # pragma: no cover - fallback for script execution
    try:
        from .config import AI_ANTHROPIC_MODEL, AI_TIMEOUT_S, ANTHROPIC_API_KEY  # type: ignore
        from .detailed_prompt_template import build_detailed_analysis_prompt  # type: ignore
    except ImportError:  # pragma: no cover - running from repository root
        from config import AI_ANTHROPIC_MODEL, AI_TIMEOUT_S, ANTHROPIC_API_KEY  # type: ignore
        from detailed_prompt_template import build_detailed_analysis_prompt  # type: ignore

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

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        if not ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY missing")
        timeout_value = max(AI_TIMEOUT_S, 120)
        _client = Anthropic(api_key=ANTHROPIC_API_KEY, default_timeout=timeout_value)
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


def _strip_markdown_code_fences(text: str) -> str:
    if not text:
        return ""
    cleaned = text.strip()
    code_block_pattern = re.compile(r"^```[a-zA-Z0-9]*\s*(?P<inner>[\s\S]+?)\s*```$", re.IGNORECASE)
    match = code_block_pattern.match(cleaned)
    if match:
        return match.group("inner").strip()
    return cleaned


def _parse_json_output(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    try:
        loaded = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            snippet = text[start : end + 1]
            try:
                loaded = json.loads(snippet)
            except json.JSONDecodeError:
                return None
        else:
            return None

    return loaded if isinstance(loaded, dict) else None


def analyze_with_claude(text: str) -> Dict[str, Any]:
    """Generate a detailed JSON analysis for the provided PDF text via Claude."""

    pdf_text, pdf_path, provided_metadata = _extract_payload(text)
    structured_metadata = _load_structured_metadata(provided_metadata, pdf_path)
    if not pdf_text:
        pdf_text = text

    prompt = build_detailed_analysis_prompt(pdf_text, structured_metadata)

    client = _get_client()
    message = client.messages.create(
        model=AI_ANTHROPIC_MODEL,
        max_tokens=4000,
        temperature=0.1,
        system="SADECE JSON formatında yanıt ver",
        messages=[{"role": "user", "content": prompt}],
    )

    text_out = ""
    try:
        if message.content:
            parts = []
            for block in message.content:
                block_text = getattr(block, "text", None)
                if block_text:
                    parts.append(str(block_text))
            text_out = "\n".join(parts)
    except Exception:  # pragma: no cover - fallback best effort
        text_out = str(message)

    raw_text = (text_out or "").strip()
    cleaned_text = _strip_markdown_code_fences(raw_text)
    parsed_json = _parse_json_output(cleaned_text)
    text_field = (
        json.dumps(parsed_json, ensure_ascii=False)
        if parsed_json is not None
        else cleaned_text
    )

    return {
        "provider": "claude",
        "model": AI_ANTHROPIC_MODEL,
        "text": text_field,
        "data": parsed_json,
        "raw_response": raw_text,
    }
