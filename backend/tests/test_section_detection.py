"""Tests for section detection using extended headings."""
from __future__ import annotations

import pathlib
import sys

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.pdf_section_analyzer import detect_sections


def test_detect_sections_handles_extended_headings():
    sample_text = """
    1. Versuchs- und Messbedingungen
    Prüfumgebung: Labor A
    İklim: 23°C

    2. Prüfergebnisse ve Değerlendirme
    Ölçüm sonuçları belirlenen toleransların içinde.

    3. Belastungsdaten / Yük Verileri
    Maksimum kuvvet: 4.5 kN
    Ortalama kuvvet: 3.9 kN
    """

    sections = detect_sections(sample_text)

    assert "Versuchs- und Messbedingungen" in sections["test_conditions"]
    assert sections["results"].lower().startswith("prüfergebnisse ve değerlendirme")
    assert "Maksimum kuvvet" in sections["load_values"]
