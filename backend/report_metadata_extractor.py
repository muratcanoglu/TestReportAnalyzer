from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Dict, Iterable, Mapping, Optional, Sequence

import pdfplumber
from PyPDF2 import PdfReader

logger = logging.getLogger(__name__)


def _normalize_text(value: object) -> str:
    """Return a cleaned, single-line string representation for metadata values."""

    if value is None:
        return ""

    text = str(value).strip()
    if not text:
        return ""

    return re.sub(r"\s+", " ", text)


def _parse_json_if_needed(structured_data: object) -> Mapping[str, object]:
    """Ensure structured data is a mapping even when stored as JSON text."""

    if isinstance(structured_data, Mapping):
        return structured_data

    if isinstance(structured_data, str):
        try:
            parsed = json.loads(structured_data)
            if isinstance(parsed, Mapping):
                return parsed
        except json.JSONDecodeError:
            logger.debug("Structured data JSON decode failed", exc_info=True)

    return {}


def _extract_label_from_text(text: str, labels: Iterable[str]) -> str:
    """Extract the value that follows any of the provided labels."""

    for label in labels:
        escaped = re.escape(label)
        pattern = re.compile(rf"{escaped}\s*[:=\-]\s*(?P<value>.+)", re.IGNORECASE)
        for line in text.splitlines():
            match = pattern.search(line)
            if match:
                return _normalize_text(match.group("value"))
    return ""


def _strip_at_label(value: str, stop_labels: Iterable[str]) -> str:
    """Remove trailing content that starts with any of the provided labels."""

    if not value:
        return value

    for label in stop_labels:
        pattern = re.compile(rf"(?i)\b{re.escape(label)}\b\s*[:=\-]?")
        match = pattern.search(value)
        if match:
            value = value[: match.start()]
            break

    return _normalize_text(value)


def _safe_page_texts(page_texts: Optional[Sequence[str]]) -> list[str]:
    return [text or "" for text in page_texts] if page_texts else []


def _load_page_texts(pdf_path: Path | str | None) -> list[str]:
    path = Path(pdf_path or "")
    if not path.exists():
        return []

    # First try pdfplumber for consistent extraction
    try:
        with pdfplumber.open(path) as pdf:
            return [page.extract_text() or "" for page in pdf.pages]
    except Exception:
        logger.debug("pdfplumber page extraction failed for %s", path, exc_info=True)

    # Fallback to PyPDF2 if pdfplumber fails
    try:
        reader = PdfReader(str(path))
        return [page.extract_text() or "" for page in reader.pages]
    except Exception:
        logger.warning("Unable to extract page texts for %s", path, exc_info=True)
        return []


def _extract_seat_model(structured_data: Mapping[str, object]) -> str:
    page_2_metadata = structured_data.get("page_2_metadata")
    if isinstance(page_2_metadata, Mapping):
        pruefling = page_2_metadata.get("pruefling")
        if isinstance(pruefling, Mapping):
            seat_model = pruefling.get("bezeichnung") or pruefling.get("typ")
            if seat_model:
                return _normalize_text(seat_model)
        elif isinstance(pruefling, str) and pruefling.strip():
            return _normalize_text(pruefling)

    return ""


def _extract_vehicle_from_metadata(structured_data: Mapping[str, object]) -> str:
    page_2_metadata = structured_data.get("page_2_metadata")
    if isinstance(page_2_metadata, Mapping):
        for key in ("testfahrzeug", "test_vehicle", "fahrzeug"):
            candidate = page_2_metadata.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return _normalize_text(candidate)
    return ""


def _extract_test_standard(structured_data: Mapping[str, object], page_texts: Sequence[str]) -> str:
    page_2_metadata = structured_data.get("page_2_metadata")
    if isinstance(page_2_metadata, Mapping):
        for key in ("versuchsbedingungen", "testbedingungen", "test_conditions"):
            candidate = page_2_metadata.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return _normalize_text(candidate)

    if len(page_texts) >= 2:
        value = _extract_label_from_text(page_texts[1], labels=("Versuchsbedingungen", "Testbedingungen"))
        return _normalize_text(value)

    return ""


def derive_report_metadata(
    structured_data: object | None,
    *,
    page_texts: Optional[Sequence[str]] = None,
    pdf_path: Path | str | None = None,
) -> Dict[str, str]:
    """
    Derive high-level metadata fields from structured data and page text content.

    This function is intentionally lightweight and defensive: it accepts structured
    data stored as either dictionaries or JSON strings and falls back to direct page
    text parsing for fields that appear on later pages of the report.
    """

    data = _parse_json_if_needed(structured_data)
    pages = _safe_page_texts(page_texts)
    if not pages and pdf_path is not None:
        pages = _safe_page_texts(_load_page_texts(pdf_path))

    seat_model = _extract_seat_model(data)
    test_standard = _extract_test_standard(data, pages)

    lab_name = ""
    if len(pages) >= 3:
        lab_name = _extract_label_from_text(pages[2], labels=("Bearbeiter",))
        lab_name = _strip_at_label(lab_name, stop_labels=("Versuchsbed. nach",))

    vehicle_platform = ""
    if len(pages) >= 4:
        vehicle_platform = _extract_label_from_text(
            pages[3], labels=("Test vehicle", "Testfahrzeug", "Versuchsfahrzeug")
        )

    if not vehicle_platform:
        vehicle_platform = _extract_vehicle_from_metadata(data)

    return {
        "seat_model": seat_model,
        "test_standard": test_standard,
        "lab_name": lab_name,
        "vehicle_platform": vehicle_platform,
    }


__all__ = ["derive_report_metadata"]
