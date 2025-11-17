from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.parsers.kielt_parser import (
    extract_lehnen_winkel_table,
    extract_pruefergebnis,
    extract_pruefling,
    extract_simple_field,
    extract_subfields,
    normalize_decimal,
)


@pytest.mark.parametrize(
    "value, expected",
    [
        ("1.234,56", 1234.56),
        ("1,234.56", 1234.56),
        ("-12,5", -12.5),
        ("7\u00a0654,3", 7654.3),
    ],
)
def test_normalize_decimal_handles_locale_formats(value: str, expected: float) -> None:
    assert normalize_decimal(value) == pytest.approx(expected)


def test_extract_simple_field_handles_bullets_and_headings() -> None:
    sample_text = """
    * Auftraggeber - Space Mobility GmbH
    Anwesende: Test Engineer
    """.strip()

    assert extract_simple_field(sample_text, "Auftraggeber") == "Space Mobility GmbH"
    assert extract_simple_field(sample_text, "Anwesende") == "Test Engineer"


def test_extract_pruefling_parses_mounting_sections() -> None:
    text = (
        "Prüfling:\n"
        "Bezeichnung: Modular Seat\n"
        "Hersteller: Future Seats\n"
        "Typ: X-99\n"
        "Serien-Nr.: 42\n"
        "Baujahr: 2022\n"
        "Gewicht: 78 kg\n"
        "Hinten montiert:\n"
        "    Sitzfläche: Bolted\n"
        "    Adapter: Steel\n"
        "Vorne montiert:\n"
        "    Sitzfläche: Hooked\n"
        "    Adapter: Aluminium"
    )

    pruefling = extract_pruefling(text)
    assert pruefling["bezeichnung"] == "Modular Seat"
    assert pruefling["seriennummer"] == "42"
    assert pruefling["hinten_montiert"] == {
        "sitzflaeche": "Bolted",
        "adapter": "Steel",
    }
    assert pruefling["vorne_montiert"] == {
        "sitzflaeche": "Hooked",
        "adapter": "Aluminium",
    }


def test_extract_pruefergebnis_includes_dummy_details() -> None:
    text = """
    Prüfergebnis:
    Ergebnis: bestanden
    Freigabe: frei
    Prüfer: Dr. Expert
    Datum: 01.01.2024
    Dummyprüfung:
        Dummy Checks: Hybrid III ready
        Rückhaltung: stabil
        Kanten: entgratet
        Bemerkung: notlar
    """.strip()

    result = extract_pruefergebnis(text)
    assert result["ergebnis"] == "bestanden"
    assert result["dummypruefung"] == {
        "dummy_checks": "Hybrid III ready",
        "rueckhaltung": "stabil",
        "kanten": "entgratet",
        "bemerkung": "notlar",
    }


def test_extract_lehnen_winkel_table_handles_mixed_separators() -> None:
    text = """
    Lehnen / Winkel:
    Vorher: 14,5° 13,9° 15.8° 15,6°
    Nachher: 13,7° 13,0° 15.2° 15,0°
    """.strip()

    table = extract_lehnen_winkel_table(text)
    assert table["vorher"]["hinten_links"] == pytest.approx(14.5)
    assert table["vorher"]["vorne_rechts"] == pytest.approx(15.6)
    assert table["nachher"]["hinten_rechts"] == pytest.approx(13.0)


def test_extract_subfields_collapses_wrapped_lines() -> None:
    text = """
    - Key One: Value part 1
      continues here
    - Key Two: Another
    """.strip()

    assert extract_subfields(text) == {
        "key_one": "Value part 1 continues here",
        "key_two": "Another",
    }
