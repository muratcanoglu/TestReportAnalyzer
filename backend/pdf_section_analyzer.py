# -*- coding: utf-8 -*-
"""Utilities for detecting structured sections inside PDF report text."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

try:  # pragma: no cover - prefer absolute imports when packaged
    from backend.section_patterns import SECTION_PATTERNS
except ImportError:  # pragma: no cover - fallback for script execution
    try:
        from .section_patterns import SECTION_PATTERNS  # type: ignore
    except ImportError:  # pragma: no cover - running from repository root
        from section_patterns import SECTION_PATTERNS  # type: ignore


SUBSECTION_PATTERNS: Dict[str, Dict[str, str]] = {
    "sled_deceleration": {
        "de": r"Schlittenverzögerung:",
        "en": r"Sled\s+deceleration:",
        "tr": r"Kızak\s+(?:gecikmesi|yavaşlaması):",
    },
    "load_values": {
        "de": r"Belastungswerte:",
        "en": r"Load\s+values:",
        "tr": r"Yük\s+değerleri:",
    },
    "photo_documentation": {
        "de": r"Fotodokumentation:",
        "en": r"Photo\s+documentation:",
        "tr": r"Fotoğraf\s+dokümantasyonu:",
    },
    "test_setup": {
        "de": r"Abb\.\s*\d+:\s*(?:Aufbau|Setup)",
        "en": r"Fig\.\s*\d+:\s*(?:Setup|Configuration)",
        "tr": r"Şekil\s*\d+:\s*(?:Kurulum|Yapılandırma)",
    },
}


@dataclass(frozen=True)
class SectionMarker:
    """Represents a detected section heading inside the PDF text."""

    start: int
    end: int
    section: str
    language: str
    heading: str


def _ensure_text_string(text_or_dict: object) -> str:
    """Return a plain string from either raw text or extraction dict results."""

    if isinstance(text_or_dict, dict):
        structured = text_or_dict.get("structured_text")
        if structured:
            return str(structured)
        fallback = text_or_dict.get("text")
        if fallback:
            return str(fallback)
        return ""
    return str(text_or_dict or "")


def _compile_heading_patterns(patterns: Iterable[str]) -> str:
    escaped = [f"(?:{pattern})" for pattern in patterns]
    return r"|".join(escaped)


def _iter_section_markers(text: str | dict) -> List[SectionMarker]:
    markers: List[SectionMarker] = []
    text = _ensure_text_string(text)
    if not text:
        return markers

    for section_key, language_map in SECTION_PATTERNS.items():
        for language, pattern_list in language_map.items():
            if not pattern_list:
                continue
            combined = _compile_heading_patterns(pattern_list)
            regex = re.compile(rf"^(?P<heading>\s*(?:{combined})\s*)$", re.IGNORECASE | re.MULTILINE)
            for match in regex.finditer(text):
                heading = (match.group("heading") or "").strip()
                markers.append(
                    SectionMarker(
                        start=match.start(),
                        end=match.end(),
                        section=section_key,
                        language=language,
                        heading=heading,
                    )
                )
    markers.sort(key=lambda item: item.start)
    return markers


def extract_section(text: str | dict, start_pattern: str, end_pattern: Optional[str] = None) -> str:
    """Extract a section using explicit start and optional end regex patterns."""

    text = _ensure_text_string(text)
    if not text:
        return ""

    start_regex = re.compile(start_pattern, re.IGNORECASE | re.MULTILINE)
    start_match = start_regex.search(text)
    if not start_match:
        return ""

    start_index = start_match.end()
    newline_index = text.find("\n", start_index)
    if newline_index != -1:
        start_index = newline_index + 1

    end_index = len(text)
    if end_pattern:
        end_regex = re.compile(end_pattern, re.IGNORECASE | re.MULTILINE)
        end_match = end_regex.search(text, start_index)
        if end_match:
            end_index = end_match.start()

    return text[start_index:end_index].strip()


def identify_section_language(text: str | dict) -> str:
    """Best-effort language detection based on known section headings."""

    text = _ensure_text_string(text)
    if not text:
        return "tr"

    scores = {"tr": 0, "en": 0, "de": 0}
    lower_text = text.lower()
    for section_map in SECTION_PATTERNS.values():
        for language, pattern_list in section_map.items():
            for pattern in pattern_list:
                if not pattern:
                    continue
                try:
                    occurrences = len(re.findall(pattern, lower_text, re.IGNORECASE))
                except re.error:
                    occurrences = 0
                scores[language] = scores.get(language, 0) + occurrences

    best_language = max(scores, key=scores.get)
    if scores[best_language] == 0:
        return "tr"
    return best_language


def detect_sections(text: str | dict) -> Dict[str, str]:
    """Detect major sections of a PDF report and return their contents."""

    logger = logging.getLogger(__name__)
    text = _ensure_text_string(text)

    if not text:
        logger.warning("detect_sections: Boş text!")
        return {}

    sections: Dict[str, str] = {}

    section_patterns: Dict[str, List[str]] = {
        "test_conditions": [
            r"(?:Test\s*(?:Conditions|Koşulları|bedingungen))",
            r"(?:Versuchsbedingungen)",
            r"(?:Prüfbedingungen)",
            r"(?:Examiner\s*:)",
            r"(?:Prüfaufbau)",
            r"(?:Versuchsaufbau)",
            r"(?:Versuchs-\s*und\s*Messbedingungen)",
            r"(?:Test\s*Setup)",
            r"(?:Test\s*Environment)",
            r"(?:Test\s*Kurulumu)",
            r"(?:Test\s*Ortamı)",
        ],
        "graphs": [
            r"(?:Graphs?|Grafikler|Diagramme?)",
            r"(?:Abbildungen?)",
            r"(?:Figures?)",
        ],
        "results": [
            r"(?:Prüfergebnisse)",
            r"(?:Results?|Sonuçlar|Ergebnisse)",
            r"(?:Test\s*Results?)",
            r"(?:Summary)",
            r"(?:Zusammenfassung)",
            r"(?:Bewertung)",
            r"(?:Auswertung)",
            r"(?:Assessment)",
            r"(?:Evaluation)",
            r"(?:Değerlendirme)",
        ],
        "load_values": [
            r"(?:Belastungswerte)",
            r"(?:Load\s*Values?)",
            r"(?:Yük\s*Değerleri)",
            r"(?:Load\s*Data)",
            r"(?:Loading\s*Values)",
            r"(?:Belastungsdaten)",
            r"(?:Belastungsverlauf)",
            r"(?:Kraftverlauf)",
            r"(?:Yük\s*Verileri)",
        ],
    }

    for section_key, patterns in section_patterns.items():
        for pattern in patterns:
            try:
                match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            except re.error:
                match = None
            if match:
                start = match.start()
                next_section_start = len(text)

                for other_key, other_patterns in section_patterns.items():
                    if other_key == section_key:
                        continue
                    for other_pattern in other_patterns:
                        try:
                            other_match = re.search(other_pattern, text[start + 10 :], re.IGNORECASE)
                        except re.error:
                            continue
                        if other_match:
                            potential_end = start + 10 + other_match.start()
                            if potential_end < next_section_start:
                                next_section_start = potential_end

                section_content = text[start:next_section_start].strip()
                if section_content:
                    sections[section_key] = section_content
                    logger.info("Bölüm bulundu: %s (%s karakter)", section_key, len(section_content))
                break

    if not sections:
        logger.warning("Hiçbir bölüm bulunamadı, tüm text 'test_conditions' olarak işleniyor")
        sections["test_conditions"] = text

    for default_key in (
        "test_conditions",
        "graphs",
        "results",
        "load_values",
        "summary",
        "header",
        "detailed_data",
    ):
        sections.setdefault(default_key, "")

    return sections


def detect_subsections(text: str | dict) -> Dict[str, str]:
    """Detect known subsections within a larger section text."""

    text = _ensure_text_string(text)
    if not text:
        return {}

    language = identify_section_language(text)
    markers: List[SectionMarker] = []

    for key, language_map in SUBSECTION_PATTERNS.items():
        pattern = language_map.get(language) or language_map.get("en")
        if not pattern:
            continue
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error:
            continue
        for match in regex.finditer(text):
            markers.append(
                SectionMarker(
                    start=match.start(),
                    end=match.end(),
                    section=key,
                    language=language,
                    heading=match.group(0),
                )
            )

    if not markers:
        return {}

    markers.sort(key=lambda item: item.start)
    subsections: Dict[str, str] = {}

    for index, marker in enumerate(markers):
        start_index = marker.start
        end_index = len(text)
        for next_marker in markers[index + 1 :]:
            if next_marker.start > marker.start:
                end_index = next_marker.start
                break
        content = text[start_index:end_index].strip()
        if content:
            subsections[marker.section] = content

    return subsections
