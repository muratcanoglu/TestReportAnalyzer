# -*- coding: utf-8 -*-
"""Utilities for parsing structured metadata inside PDF test reports."""
from __future__ import annotations

import re
from typing import Dict

try:  # pragma: no cover - prefer package imports when available
    from backend.pdf_section_analyzer import detect_subsections, identify_section_language
except ImportError:  # pragma: no cover - fallback for script execution
    try:
        from .pdf_section_analyzer import detect_subsections, identify_section_language  # type: ignore
    except ImportError:  # pragma: no cover - running from source tree directly
        from pdf_section_analyzer import detect_subsections, identify_section_language  # type: ignore


def _ensure_text_string(text_or_dict: object) -> str:
    """Return a plain string regardless of whether text arrives as dict or str."""

    if isinstance(text_or_dict, dict):
        structured = text_or_dict.get("structured_text")
        if structured:
            return str(structured)
        fallback = text_or_dict.get("text")
        if fallback:
            return str(fallback)
        return ""
    return str(text_or_dict or "")


def parse_key_value_pairs(text: str | dict) -> Dict[str, str]:
    """Extract key-value pairs from raw text using flexible patterns."""

    text = _ensure_text_string(text)
    if not text:
        return {}

    patterns = [
        r"([A-Za-zäöüÄÖÜß\s]+):\s*([^\n:]+)",
        r"(\w+)\s*:\s*([^\n]+)",
    ]

    pairs: Dict[str, str] = {}

    for pattern in patterns:
        try:
            matches = re.finditer(pattern, text)
        except re.error:
            continue
        for match in matches:
            key = (match.group(1) or "").strip().lower().replace(" ", "_")
            value = (match.group(2) or "").strip()
            if not key or not value or len(value) <= 1:
                continue
            pairs[key] = value

    return pairs


def parse_test_conditions_structured(text: str | dict) -> Dict[str, object]:
    """Parse a test conditions block into structured data."""

    cleaned = _ensure_text_string(text).strip()
    if not cleaned:
        return {"raw_text": ""}

    result: Dict[str, object] = {
        "raw_text": cleaned,
        "key_values": parse_key_value_pairs(cleaned),
        "subsections": detect_subsections(cleaned),
    }

    # Standard references (ECE-R 80, UN-R80, etc.)
    standard_match = re.search(r"(?:ECE-R|UN-R)\s*\d+", cleaned, re.IGNORECASE)
    if standard_match:
        result["standard"] = standard_match.group(0)

    # Date pattern (DD.MM.YYYY)
    date_match = re.search(r"\b\d{2}\.\d{2}\.\d{4}\b", cleaned)
    if date_match:
        result["date"] = date_match.group(0)

    # Test vehicle information
    vehicle_match = re.search(r"Test vehicle:\s*([^\n]+)", cleaned, re.IGNORECASE)
    if vehicle_match:
        result["test_vehicle"] = vehicle_match.group(1).strip()

    # Examiner or responsible person
    examiner_match = re.search(r"Examiner:\s*([^\n]+)", cleaned, re.IGNORECASE)
    if examiner_match:
        result["examiner"] = examiner_match.group(1).strip()

    # Test seat / device information
    seat_match = re.search(r"Test seat:\s*([^\n]+)", cleaned, re.IGNORECASE)
    if seat_match:
        result["test_seat"] = seat_match.group(1).strip()

    # Original file reference
    file_match = re.search(r"File:\s*([^\s]+)", cleaned, re.IGNORECASE)
    if file_match:
        result["file"] = file_match.group(1).strip()

    # Persist detected language for reference
    result["language"] = identify_section_language(cleaned)

    return result


def format_structured_data_for_ai(structured_data: Dict[str, object]) -> str:
    """Format structured data for AI prompts to ensure readability."""

    if not structured_data:
        return ""

    formatted_lines = ["=== TEST KOŞULLARI (YAPILANDIRILMIŞ) ==="]

    for key in ("standard", "date", "test_vehicle", "test_seat", "examiner"):
        value = structured_data.get(key)
        if value:
            label = key.replace("_", " ").title()
            formatted_lines.append(f"{label}: {value}")

    subsections = structured_data.get("subsections")
    if isinstance(subsections, dict):
        for name, content in subsections.items():
            if not content:
                continue
            formatted_lines.append(f"\n--- {name.upper().replace('_', ' ')} ---")
            formatted_lines.append(str(content).strip()[:500])

    tables = structured_data.get("tables")
    if isinstance(tables, list) and tables:
        formatted_lines.append("\n=== TABLO VERİLERİ ===")
        for table in tables:
            page = table.get("page")
            table_num = table.get("table_num")
            formatted_lines.append(f"\nSayfa {page}, Tablo {table_num}:")
            data_rows = table.get("data") or []
            for row in data_rows[:5]:
                row_values = [str(cell) if cell else "" for cell in row]
                formatted_lines.append("  | ".join(row_values))

    key_values = structured_data.get("key_values")
    if isinstance(key_values, dict) and key_values:
        formatted_lines.append("\n=== EK ALANLAR ===")
        for key, value in key_values.items():
            formatted_lines.append(f"{key}: {value}")

    return "\n".join(formatted_lines)


__all__ = [
    "format_structured_data_for_ai",
    "parse_key_value_pairs",
    "parse_test_conditions_structured",
]
