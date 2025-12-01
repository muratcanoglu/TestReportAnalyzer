"""Helpers for extracting Kielt/TÜV-specific metadata blocks."""
from __future__ import annotations

from pathlib import Path
import logging
import re
from typing import Dict, Iterable, List, Mapping, Optional

import pdfplumber
from PyPDF2 import PdfReader

logger = logging.getLogger(__name__)


def normalize_decimal(value_str: Optional[str]) -> Optional[float]:
    """Normalize locale-aware decimal strings into floats.

    Handles numbers that use comma or dot as decimal separators, optional
    thousand separators and whitespace. Returns ``None`` if the value cannot be
    parsed and logs a warning to aid debugging.
    """

    if value_str is None:
        return None

    text = value_str.strip().replace("\xa0", "")
    if not text:
        return None

    sign = 1
    if text[0] in "+-":
        if text[0] == "-":
            sign = -1
        text = text[1:]

    digits_only = text.replace(" ", "")
    if not digits_only or not re.fullmatch(r"[0-9.,]+", digits_only):
        logger.warning("normalize_decimal: non-numeric input skipped: %r", value_str)
        return None

    comma_pos = digits_only.rfind(",")
    dot_pos = digits_only.rfind(".")

    normalized = digits_only
    if comma_pos != -1 and dot_pos != -1:
        if comma_pos > dot_pos:
            normalized = digits_only.replace(".", "").replace(",", ".")
        else:
            normalized = digits_only.replace(",", "")
    elif comma_pos != -1:
        fractional_digits = len(digits_only) - comma_pos - 1
        if digits_only.count(",") == 1 and 0 < fractional_digits <= 2:
            normalized = digits_only.replace(",", ".")
        else:
            normalized = digits_only.replace(",", "")
    elif dot_pos != -1:
        normalized = digits_only

    if sign == -1:
        normalized = f"-{normalized}"

    try:
        return float(normalized)
    except ValueError:
        logger.warning(
            "normalize_decimal: unable to parse %r (normalized=%s)", value_str, normalized
        )
        return None

_SIMPLE_PAGE2_FIELDS: Mapping[str, Iterable[str]] = {
    "auftraggeber": ["Auftraggeber"],
    "anwesende": ["Anwesende"],
    "versuchsbedingungen": ["Versuchsbedingungen", "Prüfbedingungen", "Testbedingungen"],
    "justierung_kontrolle": ["Justierung/Kontrolle", "Justierung / Kontrolle"],
    "schlittenverzoegerung": ["Schlittenverzögerung", "Schlittenverzoegerung"],
    "examiner": ["Examiner"],
    "testfahrzeug": ["Testfahrzeug", "Test vehicle", "Versuchsfahrzeug"],
}

_PRUEFLING_FIELDS: Mapping[str, Iterable[str]] = {
    "bezeichnung": ["Bezeichnung"],
    "hersteller": ["Hersteller"],
    "typ": ["Typ"],
    "seriennummer": ["Serien-Nr.", "Seriennr.", "Seriennummer"],
    "baujahr": ["Baujahr"],
    "gewicht": ["Gewicht"],
}

_PRUEFERGEBNIS_FIELDS: Mapping[str, Iterable[str]] = {
    "ergebnis": ["Ergebnis"],
    "freigabe": ["Freigabe"],
    "pruefer": ["Prüfer", "Pruefer"],
    "datum": ["Datum"],
}

_PRUEFERGEBNIS_CRITERIA_PATTERNS: Mapping[str, str] = {
    "scharfe_kanten": r"Kriterium\s+[„\"“]scharfe\s+Kanten[”\"“]\s*[:=\-]?\s*(?P<value>.+?)(?:\r?\n|$)",
}

_ANGLE_POSITIONS: List[str] = [
    "hinten_links",
    "hinten_rechts",
    "vorne_links",
    "vorne_rechts",
]


def extract_simple_field(text: str, key: str, *, collapse_whitespace: bool = True) -> Optional[str]:
    """Extract a value that follows the given ``key`` label."""

    if not text or not key:
        return None

    escaped_key = re.escape(key.strip())
    if not escaped_key:
        return None

    next_heading = r"(?:\n\s*(?:-|\*)?\s*[A-ZÄÖÜ0-9][^:\n]{0,60}\s*(?:[:\-]))"
    pattern = re.compile(
        rf"^\s*(?:-|\*)?\s*{escaped_key}\s*(?:[:\-]\s*)?(?P<value>.+?)(?=(?:{next_heading})|\n\s*\n|\Z)",
        re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )

    match = pattern.search(text)
    if not match:
        return None

    value = match.group("value").strip()
    if not value:
        return None

    if collapse_whitespace:
        value = re.sub(r"\s+", " ", value)
    return value


def _extract_block(text: str, block_label: str, *, treat_as_regex: bool = False) -> str:
    label = block_label if treat_as_regex else re.escape(block_label)
    pattern = rf"{label}\s*:?(.*?)(?:\n\s*\n|$)"
    try:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    except re.error as exc:  # pragma: no cover
        logger.warning("Invalid block regex for %s: %s", block_label, exc)
        return ""

    if not match:
        return ""

    return match.group(1).strip()


def _normalize_subfield_key(label: str) -> str:
    transliterated = (
        label.lower()
        .replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )
    normalized = re.sub(r"[^a-z0-9]+", "_", transliterated)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized or transliterated.strip()


def extract_subfields(text: str) -> Dict[str, str]:
    """Extract ``SubKey: SubValue`` pairs from ``text``."""

    if not text:
        return {}

    pairs: Dict[str, str] = {}
    pattern = re.compile(
        r"^\s*(?:-|\*)?\s*(?P<key>[A-Za-zÄÖÜäöüß0-9/().,%+\- ]+?)\s*[:=\-]\s*(?P<value>.+)$",
        re.MULTILINE,
    )
    current_key: Optional[str] = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            current_key = None
            continue
        match = pattern.match(line)
        if match:
            key = _normalize_subfield_key(match.group("key"))
            value = match.group("value").strip()
            value = re.sub(r"\s+", " ", value)
            pairs[key] = value
            current_key = key
            continue
        if current_key:
            continuation = re.sub(r"\s+", " ", stripped)
            if continuation:
                pairs[current_key] = f"{pairs[current_key]} {continuation}".strip()
    return pairs


def _match_first_value(text: str, labels: Iterable[str]) -> str:
    for label in labels:
        value = extract_simple_field(text, label)
        if value:
            return value
    return ""


def _extract_nested_section(text: str, heading: str) -> Optional[str]:
    pattern = re.compile(
        rf"{re.escape(heading)}\s*:?(?P<body>(?:\r?\n\s{{2,}}.+)+)",
        re.IGNORECASE,
    )
    match = pattern.search(text)
    if match:
        lines = [line.strip() for line in match.group("body").splitlines() if line.strip()]
        return "\n".join(lines)
    return extract_simple_field(text, heading, collapse_whitespace=False)


def extract_pruefling(text: str) -> Dict[str, object]:
    """Return structured Prüfling data, including mounting sub-sections."""

    block = _extract_block(text, "Prüfling")
    result: Dict[str, object] = {key: "" for key in _PRUEFLING_FIELDS}
    result["hinten_montiert"] = {}
    result["vorne_montiert"] = {}

    if not block:
        return result

    for field_key, labels in _PRUEFLING_FIELDS.items():
        result[field_key] = _match_first_value(block, labels)

    for section_label, result_key in ("Hinten montiert", "hinten_montiert"), ("Vorne montiert", "vorne_montiert"):
        section_text = _extract_nested_section(block, section_label)
        result[result_key] = extract_subfields(section_text) if section_text else {}

    return result


def _extract_dummy_field(text: str, pattern: str) -> str:
    try:
        match = re.search(pattern, text, re.IGNORECASE)
    except re.error as exc:  # pragma: no cover - defensive guard
        logger.warning("Invalid dummy regex %s: %s", pattern, exc)
        return ""
    if not match:
        return ""
    value = match.group("value").strip()
    return re.sub(r"\s+", " ", value)


_DUMMY_REGEX_PATTERNS: Mapping[str, str] = {
    "dummy_checks": r"(?:Dummypr[üu]fung\s*)?Dummy(?:\s*-?\s*Checks?)?\s*(?:[:=\-]\s*)?(?P<value>.+?)(?:\r?\n|$)",
    "rueckhaltung": r"R[üu]ckhaltung\s*(?:[:=\-]\s*)?(?P<value>.+?)(?:\r?\n|$)",
    "kanten": r"Kanten\s*(?:[:=\-]\s*)?(?P<value>.+?)(?:\r?\n|$)",
    "bemerkung": r"Bemerk(?:ung|ungen)\s*(?:[:=\-]\s*)?(?P<value>.+?)(?:\r?\n|$)",
}


def extract_pruefergebnis(text: str) -> Dict[str, object]:
    """Return structured Prüfergebnis data with Dummyprüfung breakdown."""

    block = _extract_block(text, "Prüfergebnis")
    result: Dict[str, object] = {key: "" for key in _PRUEFERGEBNIS_FIELDS}
    dummy_details = {key: "" for key in _DUMMY_REGEX_PATTERNS}
    criteria_details = {key: "" for key in _PRUEFERGEBNIS_CRITERIA_PATTERNS}
    result["dummypruefung"] = dummy_details
    result["criteria"] = criteria_details

    if not block:
        return result

    for field_key, labels in _PRUEFERGEBNIS_FIELDS.items():
        result[field_key] = _match_first_value(block, labels)

    dummy_text = _extract_nested_section(block, "Dummyprüfung") or block
    for dummy_key, pattern in _DUMMY_REGEX_PATTERNS.items():
        dummy_details[dummy_key] = _extract_dummy_field(dummy_text, pattern)

    for criteria_key, pattern in _PRUEFERGEBNIS_CRITERIA_PATTERNS.items():
        criteria_details[criteria_key] = _extract_dummy_field(block, pattern)

    return result


def normalize_float(value: Optional[str]) -> Optional[float]:
    """Return a float from a localized string containing degrees."""

    if not value:
        return None

    cleaned = value.replace("°", "").strip()
    if not cleaned:
        return None

    return normalize_decimal(cleaned)


def extract_lehnen_winkel_table(text: str) -> Dict[str, Dict[str, Optional[float]]]:
    """Parse Vorher/Nachher rows of the Lehnen/Winkel table."""

    block_text = _extract_block(text, r"Lehnen[\s/\-]*Winkel", treat_as_regex=True)
    if not block_text:
        return {}

    table: Dict[str, Dict[str, Optional[float]]] = {}
    for row_label in ("Vorher", "Nachher"):
        row_text = extract_simple_field(block_text, row_label)
        if not row_text:
            continue
        values = re.findall(r"-?\d+[\.,]?\d*", row_text)
        if len(values) < len(_ANGLE_POSITIONS):
            continue
        normalized_values = [normalize_float(value) for value in values[: len(_ANGLE_POSITIONS)]]
        table[row_label.lower()] = {
            position: normalized
            for position, normalized in zip(_ANGLE_POSITIONS, normalized_values)
        }

    return table


def _parse_page_2_text(page_text: str) -> Dict[str, object]:
    """Parse all known metadata from page 2 of the Kielt format."""

    metadata: Dict[str, object] = {}
    for field_key, labels in _SIMPLE_PAGE2_FIELDS.items():
        value: Optional[str] = ""
        for label in labels:
            value = extract_simple_field(page_text, label)
            if value:
                break
        metadata[field_key] = value or ""

    metadata["pruefling"] = extract_pruefling(page_text)
    metadata["pruefergebnis"] = extract_pruefergebnis(page_text)
    metadata["lehnen_winkel_table"] = extract_lehnen_winkel_table(page_text)
    metadata["raw_page_text"] = page_text.strip()
    return metadata


def parse_page_2_metadata(pdf_path: Path | str) -> Dict[str, object]:
    """Read the PDF and parse metadata found on page 2.

    The function first attempts to extract the raw text using ``pdfplumber`` and
    falls back to ``PyPDF2`` if needed. Any exception is logged and returned as
    part of the response to align with the Phase 2.3 specification.
    """

    pdf_path_obj = Path(pdf_path)

    pdf_handle: Optional[pdfplumber.PDF] = None
    try:
        pdf_handle = pdfplumber.open(pdf_path_obj)
        if len(pdf_handle.pages) < 2:
            raise ValueError("PDF contains fewer than 2 pages")
        page_text = pdf_handle.pages[1].extract_text() or ""
        if not page_text.strip():
            raise ValueError("Page 2 text is empty")
        return _parse_page_2_text(page_text)
    except Exception as plumber_exc:  # pragma: no cover - logging only
        logger.warning(
            "parse_page_2_metadata(pdfplumber) failed for %s: %s",
            pdf_path_obj,
            plumber_exc,
        )
    finally:
        if pdf_handle is not None:
            try:
                pdf_handle.close()
            except Exception:  # pragma: no cover - defensive close
                logger.debug("Failed to close pdfplumber handle for %s", pdf_path_obj)

    try:
        reader = PdfReader(str(pdf_path_obj))
        if len(reader.pages) < 2:
            raise ValueError("PDF contains fewer than 2 pages")
        page_text = reader.pages[1].extract_text() or ""
        if not page_text.strip():
            raise ValueError("Page 2 text is empty")
        return _parse_page_2_text(page_text)
    except Exception as exc:
        logger.exception("parse_page_2_metadata failed for %s", pdf_path_obj)
        return {"error": str(exc)}


__all__ = [
    "extract_simple_field",
    "extract_subfields",
    "extract_pruefling",
    "extract_pruefergebnis",
    "normalize_float",
    "extract_lehnen_winkel_table",
    "parse_page_2_metadata",
]
