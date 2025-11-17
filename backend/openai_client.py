# -*- coding: utf-8 -*-
"""Thin wrapper around the OpenAI Responses API."""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional, Tuple

from openai import OpenAI

try:  # pragma: no cover - prefer absolute imports under package execution
    from backend.config import AI_OPENAI_MODEL, AI_TIMEOUT_S, OPENAI_API_KEY
    from backend.detailed_prompt_template import build_detailed_analysis_prompt
except ImportError:  # pragma: no cover - fallback for script execution
    try:
        from .config import AI_OPENAI_MODEL, AI_TIMEOUT_S, OPENAI_API_KEY  # type: ignore
        from .detailed_prompt_template import build_detailed_analysis_prompt  # type: ignore
    except ImportError:  # pragma: no cover - running from repository root
        from config import AI_OPENAI_MODEL, AI_TIMEOUT_S, OPENAI_API_KEY  # type: ignore
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

PREFERRED_OPENAI_MODELS = ("gpt-4-turbo-preview", "gpt-4")
_client: OpenAI | None = None


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


def analyze_with_openai(text: str) -> Dict[str, Any]:
    """Generate a detailed JSON analysis for the provided PDF text via OpenAI."""

    pdf_text, pdf_path, provided_metadata = _extract_payload(text)
    structured_metadata = _load_structured_metadata(provided_metadata, pdf_path)
    if not pdf_text:
        pdf_text = text

    prompt = build_detailed_analysis_prompt(pdf_text, structured_metadata)

    client = _get_client()
    model_name = AI_OPENAI_MODEL or PREFERRED_OPENAI_MODELS[0]
    if model_name not in PREFERRED_OPENAI_MODELS:
        model_name = PREFERRED_OPENAI_MODELS[0]

    response = client.responses.create(
        model=model_name,
        temperature=0.1,
        max_output_tokens=4000,
        input=[
            {"role": "system", "content": "SADECE JSON formatında yanıt ver"},
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
    cleaned_text = _strip_markdown_code_fences(raw_text)
    parsed_json = _parse_json_output(cleaned_text)
    text_field = (
        json.dumps(parsed_json, ensure_ascii=False)
        if parsed_json is not None
        else cleaned_text
    )

    return {
        "provider": "chatgpt",
        "model": model_name,
        "text": text_field,
        "data": parsed_json,
        "raw_response": raw_text,
    }
