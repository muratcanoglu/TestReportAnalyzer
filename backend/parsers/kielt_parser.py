"""Helpers for extracting Kielt/TÜV-specific metadata blocks."""
from __future__ import annotations

import logging
import re
from typing import Dict, Iterable, List, Mapping

from backend.pdf_format_detector import normalize_decimal

logger = logging.getLogger(__name__)

_SIMPLE_PAGE2_FIELDS: Mapping[str, Iterable[str]] = {
    "pruefbericht_nr": [r"Pr[üu]fbericht[-\s]*Nr\.?\s*[:\-]\s*([^\n]+)"],
    "auftrags_nr": [r"Auftrags[-\s]*Nr\.?\s*[:\-]\s*([^\n]+)"],
    "auftraggeber": [r"Auftraggeber\s*[:\-]\s*([^\n]+)"],
    "werk": [r"Werk\s*[:\-]\s*([^\n]+)"],
    "auftrag_vom": [r"Auftrag\s+vom\s*[:\-]\s*([^\n]+)"],
    "pruefort": [r"Pr[üu]fort\s*[:\-]\s*([^\n]+)"],
    "pruefdatum": [r"Pr[üu]fdatum\s*[:\-]\s*([^\n]+)"],
    "kundennummer": [r"Kundennummer\s*[:\-]\s*([^\n]+)"],
    "ansprechpartner": [r"Ansprechpartner\s*[:\-]\s*([^\n]+)"],
    "telefon": [r"Telefon\s*[:\-]\s*([^\n]+)"],
    "email": [r"E-Mail\s*[:\-]\s*([^\n]+)", r"Email\s*[:\-]\s*([^\n]+)"],
    "pruefgrundlage": [r"Pr[üu]fgrundlage\s*[:\-]\s*([^\n]+)"],
    "pruefumfang": [r"Pr[üu]fumfang\s*[:\-]\s*([^\n]+)"],
    "messmittel": [r"Messmittel\s*[:\-]\s*([^\n]+)"],
    "pruefmittelueberwachung": [r"Pr[üu]fmittel[\s-]*[ÜU]berwachung\s*[:\-]\s*([^\n]+)"]
}

_PRUEFLING_PATTERNS: Mapping[str, Iterable[str]] = {
    "bezeichnung": [r"Bezeichnung\s*[:\-]\s*([^\n]+)"],
    "hersteller": [r"Hersteller\s*[:\-]\s*([^\n]+)"],
    "typ": [r"Typ\s*[:\-]\s*([^\n]+)"],
    "seriennummer": [r"Serien[-\s]*Nr\.?\s*[:\-]\s*([^\n]+)"],
    "baujahr": [r"Baujahr\s*[:\-]\s*([^\n]+)"],
    "gewicht": [r"Gewicht\s*[:\-]\s*([^\n]+)"]
}

_PRUEFERGEBNIS_PATTERNS: Mapping[str, Iterable[str]] = {
    "ergebnis": [r"Ergebnis\s*[:\-]\s*([^\n]+)"],
    "pruefer": [r"Pr[üu]fer\s*[:\-]\s*([^\n]+)"],
    "freigabe": [r"Freigabe\s*[:\-]\s*([^\n]+)"],
    "datum": [r"Datum\s*[:\-]\s*([^\n]+)"]
}


def extract_simple_field(text: str, field_key: str, pattern: str) -> str:
    """Return the first regex capture group for a field or an empty string."""

    if not text:
        return ""

    try:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
    except re.error as exc:  # pragma: no cover - defensive guard
        logger.warning("Invalid regex for %s: %s", field_key, exc)
        return ""

    if not match:
        return ""

    value = match.group(1).strip()
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


def extract_subfields(
    text: str,
    block_label: str,
    field_patterns: Mapping[str, Iterable[str]],
) -> Dict[str, str]:
    """Extract key/value pairs from a labeled block."""

    block_text = _extract_block(text, block_label)
    if not block_text:
        return {key: "" for key in field_patterns}

    result: Dict[str, str] = {}
    for field_key, patterns in field_patterns.items():
        value = ""
        for pattern in patterns:
            value = extract_simple_field(block_text, field_key, pattern)
            if value:
                break
        result[field_key] = value
    return result


def extract_pruefling(text: str) -> Dict[str, str]:
    """Return structured Prüfling data."""

    return extract_subfields(text, "Prüfling", _PRUEFLING_PATTERNS)


def extract_pruefergebnis(text: str) -> Dict[str, str]:
    """Return structured Prüfergebnis data."""

    return extract_subfields(text, "Prüfergebnis", _PRUEFERGEBNIS_PATTERNS)


def normalize_float(value: str) -> str:
    """Normalize decimal strings by replacing commas and stripping units."""

    if not value:
        return ""

    normalised = normalize_decimal(value)
    if normalised is None:
        return ""
    normalized = ("%0.2f" % normalised).rstrip("0").rstrip(".")
    return normalized or "0"


def extract_lehnen_winkel_table(text: str) -> List[Dict[str, str]]:
    """Parse rows of the Lehnen/Winkel table."""

    block_text = _extract_block(text, r"Lehnen[\s/\-]*Winkel", treat_as_regex=True)
    if not block_text:
        return []

    rows: List[Dict[str, str]] = []
    row_pattern = re.compile(
        r"(?P<label>[^:]+?)\s*:?-?\s*links\s*(?P<linkes>-?\d+[\.,]?\d*)°?\s*(?:[|/,]|und|&)?\s*rechts\s*(?P<rechts>-?\d+[\.,]?\d*)°?",
        re.IGNORECASE,
    )

    for line in block_text.splitlines():
        clean = line.strip()
        if not clean:
            continue
        match = row_pattern.search(clean)
        if match:
            rows.append(
                {
                    "position": match.group("label").strip(),
                    "winkel_links": normalize_float(match.group("linkes")),
                    "winkel_rechts": normalize_float(match.group("rechts")),
                }
            )
            continue

        floats = re.findall(r"-?\d+[\.,]?\d*", clean)
        if len(floats) >= 2:
            rows.append(
                {
                    "position": clean.split(":", 1)[0].strip(),
                    "winkel_links": normalize_float(floats[0]),
                    "winkel_rechts": normalize_float(floats[1]),
                }
            )

    return rows


def parse_page_2_metadata(page_text: str) -> Dict[str, object]:
    """Parse all known metadata from page 2 of the Kielt format."""

    metadata: Dict[str, object] = {}
    for field_key, patterns in _SIMPLE_PAGE2_FIELDS.items():
        value = ""
        for pattern in patterns:
            value = extract_simple_field(page_text, field_key, pattern)
            if value:
                break
        metadata[field_key] = value

    metadata["pruefling"] = extract_pruefling(page_text)
    metadata["pruefergebnis"] = extract_pruefergebnis(page_text)
    metadata["lehnen_winkel_table"] = extract_lehnen_winkel_table(page_text)
    metadata["raw_page_text"] = page_text.strip()
    return metadata


__all__ = [
    "extract_simple_field",
    "extract_subfields",
    "extract_pruefling",
    "extract_pruefergebnis",
    "normalize_float",
    "extract_lehnen_winkel_table",
    "parse_page_2_metadata",
]
