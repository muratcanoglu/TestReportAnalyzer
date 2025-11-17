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
Auftraggeber: Metrobus GmbH
Anwesende: Herr Mustermann, Frau Testerin
Versuchsbedingungen: UN-R80 Phase 2.2, Sitzrückhaltesystem
Justierung/Kontrolle: MINIdau 200 Hz, Prüfstand kalibriert am 12.03.2024
Schlittenverzögerung: 35 g / 120 ms
Examiner: IWW Kiel
Testfahrzeug: MAN Lion's Coach C (M3)

Prüfling:
Bezeichnung: Reisebussitz Doppelsitz
Hersteller: SeatWorks GmbH
Typ: LX-900
Serien-Nr.: SN-456
Baujahr: 2023
Gewicht: 85 kg
Hinten montiert:
    Gurt: 3-Punkt Serie
    Adapter: Standardaufnahme
Vorne montiert:
    Gurt: 3-Punkt Serie
    Adapter: Crash-Adapter B

Prüfergebnis:
Ergebnis: bestanden
Freigabe: Serienfertigung frei
Prüfer: Dipl.-Ing. Schmidt
Datum: 22.03.2024
Dummyprüfung:
    Dummy Checks: P10 + 50M Hybrid III geprüft
    Rückhaltung: keine Auffälligkeiten
    Kanten: alle Kanten gerundet
    Bemerkung: keine Beanstandung

Lehnen / Winkel:
Position          Hinten links   Hinten rechts   Vorne links   Vorne rechts
Vorher:           14,5°          13,8°           16,2°         16,1°
Nachher:          13,5°          13,2°           15,9°         15,5°
""".strip()


@pytest.fixture()
def sample_page2_text() -> str:
    return _SAMPLE_PAGE2_TEXT


def test_parse_page2_metadata(sample_page2_text: str):
    metadata = parse_page_2_metadata(sample_page2_text)

    expected_simple_fields = {
        "auftraggeber": "Metrobus GmbH",
        "anwesende": "Herr Mustermann, Frau Testerin",
        "versuchsbedingungen": "UN-R80 Phase 2.2, Sitzrückhaltesystem",
        "justierung_kontrolle": "MINIdau 200 Hz, Prüfstand kalibriert am 12.03.2024",
        "schlittenverzoegerung": "35 g / 120 ms",
        "examiner": "IWW Kiel",
        "testfahrzeug": "MAN Lion's Coach C (M3)",
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
        "hinten_montiert": {"gurt": "3-Punkt Serie", "adapter": "Standardaufnahme"},
        "vorne_montiert": {"gurt": "3-Punkt Serie", "adapter": "Crash-Adapter B"},
    }

    assert metadata["pruefergebnis"] == {
        "ergebnis": "bestanden",
        "freigabe": "Serienfertigung frei",
        "pruefer": "Dipl.-Ing. Schmidt",
        "datum": "22.03.2024",
        "dummypruefung": {
            "dummy_checks": "P10 + 50M Hybrid III geprüft",
            "rueckhaltung": "keine Auffälligkeiten",
            "kanten": "alle Kanten gerundet",
            "bemerkung": "keine Beanstandung",
        },
    }

    assert metadata["lehnen_winkel_table"] == {
        "vorher": {
            "hinten_links": 14.5,
            "hinten_rechts": 13.8,
            "vorne_links": 16.2,
            "vorne_rechts": 16.1,
        },
        "nachher": {
            "hinten_links": 13.5,
            "hinten_rechts": 13.2,
            "vorne_links": 15.9,
            "vorne_rechts": 15.5,
        },
    }

    simple_values = {
        key: value
        for key, value in metadata.items()
        if key
        not in {"pruefling", "pruefergebnis", "lehnen_winkel_table", "raw_page_text"}
    }
    assert len(simple_values) == len(expected_simple_fields)


def test_analyze_pdf_attaches_page2_metadata(monkeypatch: pytest.MonkeyPatch):
    fake_metadata = {
        "auftraggeber": "Metrobus GmbH",
        "pruefling": {},
        "pruefergebnis": {},
        "lehnen_winkel_table": {},
    }

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
