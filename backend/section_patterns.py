# -*- coding: utf-8 -*-
"""Regex patterns for detecting structured sections inside PDF reports."""
from __future__ import annotations

SECTION_PATTERNS = {
    "test_conditions": {
        "tr": [
            r"Test Koşulları",
            r"Test Şartları",
            r"Deney Koşulları",
            r"Test Kurulumu",
            r"Test Ortamı",
        ],
        "en": [
            r"Test Conditions",
            r"Testing Conditions",
            r"Test Parameters",
            r"Test Setup",
            r"Test Environment",
        ],
        "de": [
            r"Testbedingungen",
            r"Prüfbedingungen",
            r"Versuchsbedingungen",
            r"Prüfaufbau",
            r"Versuchsaufbau",
            r"Versuchs-\s*und\s*Messbedingungen",
        ],
    },
    "graphs": {
        "tr": [
            r"Grafikler",
            r"Şekiller",
            r"Diyagramlar",
        ],
        "en": [
            r"Graphs",
            r"Charts",
            r"Figures",
            r"Diagrams",
        ],
        "de": [
            r"Diagramme",
            r"Grafiken",
            r"Abbildungen",
        ],
    },
    "results": {
        "tr": [
            r"Sonuçlar",
            r"Test Sonuçları",
            r"Bulgular",
            r"Değerlendirme",
        ],
        "en": [
            r"Results",
            r"Test Results",
            r"Findings",
            r"Assessment",
            r"Evaluation",
        ],
        "de": [
            r"Ergebnisse",
            r"Testergebnisse",
            r"Resultate",
            r"Prüfergebnisse",
            r"Bewertung",
            r"Auswertung",
        ],
    },
    "load_values": {
        "tr": [
            r"Belastungswerte",
            r"Yük\s*Değerleri",
            r"Yük\s*Verileri",
        ],
        "en": [
            r"Belastungswerte",
            r"Load\s*Values?",
            r"Load\s*Data",
            r"Loading\s*Values",
        ],
        "de": [
            r"Belastungswerte",
            r"Belastungsdaten",
            r"Belastungsverlauf",
            r"Kraftverlauf",
        ],
    },
    "summary": {
        "tr": [
            r"Özet",
            r"Genel Özet",
            r"Sonuç",
        ],
        "en": [
            r"Summary",
            r"Conclusion",
            r"Overview",
        ],
        "de": [
            r"Zusammenfassung",
            r"Übersicht",
            r"Fazit",
        ],
    },
}
