from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.parsers.kielt_parser import parse_page_2_metadata
from backend.pdf_analyzer import analyze_pdf_comprehensive
import backend.pdf_analyzer as _pdf_analyzer_module
import backend.pdf_format_detector as _pdf_format_detector_module

sys.modules.setdefault("pdf_format_detector", _pdf_format_detector_module)
sys.modules.setdefault("pdf_analyzer", _pdf_analyzer_module)


_SAMPLE_PAGE2_TEXT = """
Seite 2
Prüfbericht-Nr.: KIELT-2024-009
Auftrags-Nr.: A-7788
Auftraggeber: Mustermann GmbH
Werk: Bursa Werk 1
Auftrag vom: 14.03.2024
Prüfort: Testhalle Kiel
Prüfdatum: 21.03.2024
Kundennummer: 445-33
Ansprechpartner: Dipl.-Ing. Paul Adler
Telefon: +49 431 0000
E-Mail: paul.adler@example.com
Prüfgrundlage: ECE-R 80
Prüfumfang: Lehnenversuch
Messmittel: GOM ZX
Prüfmittelüberwachung: gültig bis 03/2025

Prüfling:
Bezeichnung: Reisebussitz Doppelsitz
Hersteller: SeatWorks GmbH
Typ: LX-900
Serien-Nr.: SN-456
Baujahr: 2023
Gewicht: 85 kg

Prüfergebnis:
Ergebnis: bestanden
Freigabe: Serienfertigung frei
Prüfer: Dipl.-Ing. Schmidt
Datum: 22.03.2024

Lehnen / Winkel:
1. Reihe links 14,5° | rechts 13,8°
2. Reihe links 16,2° | rechts 16,1°
""".strip()


@pytest.fixture()
def sample_page2_text() -> str:
    return _SAMPLE_PAGE2_TEXT


def test_parse_page2_metadata(sample_page2_text: str):
    metadata = parse_page_2_metadata(sample_page2_text)

    expected_simple_fields = {
        "pruefbericht_nr": "KIELT-2024-009",
        "auftrags_nr": "A-7788",
        "auftraggeber": "Mustermann GmbH",
        "werk": "Bursa Werk 1",
        "auftrag_vom": "14.03.2024",
        "pruefort": "Testhalle Kiel",
        "pruefdatum": "21.03.2024",
        "kundennummer": "445-33",
        "ansprechpartner": "Dipl.-Ing. Paul Adler",
        "telefon": "+49 431 0000",
        "email": "paul.adler@example.com",
        "pruefgrundlage": "ECE-R 80",
        "pruefumfang": "Lehnenversuch",
        "messmittel": "GOM ZX",
        "pruefmittelueberwachung": "gültig bis 03/2025",
    }

    for key, value in expected_simple_fields.items():
        assert metadata[key] == value

    assert metadata["pruefling"] == {
        "bezeichnung": "Reisebussitz Doppelsitz",
        "hersteller": "SeatWorks GmbH",
        "typ": "LX-900",
        "seriennummer": "SN-456",
        "baujahr": "2023",
        "gewicht": "85 kg",
    }

    assert metadata["pruefergebnis"] == {
        "ergebnis": "bestanden",
        "freigabe": "Serienfertigung frei",
        "pruefer": "Dipl.-Ing. Schmidt",
        "datum": "22.03.2024",
    }

    assert metadata["lehnen_winkel_table"] == [
        {"position": "1. Reihe", "winkel_links": 14.5, "winkel_rechts": 13.8},
        {"position": "2. Reihe", "winkel_links": 16.2, "winkel_rechts": 16.1},
    ]

    simple_values = {
        key: value
        for key, value in metadata.items()
        if key
        not in {"pruefling", "pruefergebnis", "lehnen_winkel_table", "raw_page_text"}
    }
    assert len(simple_values) == 15


def test_analyze_pdf_attaches_page2_metadata(monkeypatch: pytest.MonkeyPatch):
    fake_metadata = {"pruefbericht_nr": "KIELT-2024-009", "pruefling": {}, "pruefergebnis": {}, "lehnen_winkel_table": []}

    def _fake_extract_text_from_pdf(_):
        return {
            "text": "",
            "structured_text": "",
            "tables": [],
            "page_texts": ["page-1", _SAMPLE_PAGE2_TEXT],
        }

    monkeypatch.setattr(
        "backend.pdf_analyzer.extract_text_from_pdf", _fake_extract_text_from_pdf
    )

    pdf_module = sys.modules["pdf_format_detector"]
    monkeypatch.setattr(pdf_module, "detect_pdf_format", lambda _text: "kielt_format")
    monkeypatch.setattr(pdf_module, "parse_kielt_format", lambda _text: {})
    monkeypatch.setattr(pdf_module, "extract_measurement_params", lambda *_args, **_kwargs: [])

    monkeypatch.setattr(
        "backend.pdf_analyzer.parse_page_2_metadata", lambda _text: fake_metadata
    )

    monkeypatch.setattr(
        "backend.pdf_analyzer.analyze_test_conditions", lambda *_args, **_kwargs: "conditions"
    )
    monkeypatch.setattr(
        "backend.pdf_analyzer.analyze_results", lambda *_args, **_kwargs: "results"
    )
    monkeypatch.setattr(
        "backend.pdf_analyzer.generate_comprehensive_report", lambda analysis: analysis
    )
    monkeypatch.setattr(
        "backend.pdf_analyzer.parse_test_results", lambda *_args, **_kwargs: []
    )
    monkeypatch.setattr(
        "backend.pdf_analyzer.extract_graph_images", lambda _path: []
    )
    monkeypatch.setattr(
        "backend.pdf_analyzer.ocr_graph_images", lambda _images: []
    )
    monkeypatch.setattr(
        "backend.pdf_analyzer.analyze_graphs",
        lambda *_args, **_kwargs: "graphs",
    )

    result = analyze_pdf_comprehensive("dummy.pdf")

    assert result["structured_data"].get("page_2_metadata") == fake_metadata
