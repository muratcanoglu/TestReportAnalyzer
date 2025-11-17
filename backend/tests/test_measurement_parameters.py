# -*- coding: utf-8 -*-
"""Tests for extracting measurement parameters from structured tables."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.pdf_analyzer import analyze_pdf_comprehensive
from backend.pdf_format_detector import extract_measurement_params, normalize_decimal
import backend.pdf_format_detector as _pdf_format_detector_module

sys.modules.setdefault("pdf_format_detector", _pdf_format_detector_module)


def _sample_measurement_tables() -> List[dict]:
    return [
        {
            "page": 2,
            "table_num": 1,
            "data": [
                ["Messgröße", "Einheit", "Test 1", "Test 2", "Grenzwert"],
                ["a Kopf über 3 ms", "g", "58,15", "64,72", "80"],
                ["ThAC", "g", "18,40", "18,27", "40"],
                ["FAC right F", "kN", "4,40", "5,94", "9"],
                ["FAC left F", "kN", "4,82", "6,34", "9"],
                ["HAC", "", "161,18", "283,27", ""],
            ],
        }
    ]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("58,15", 58.15),
        ("1234.56", 1234.56),
        ("1.234,56", 1234.56),
        ("1,234.56", 1234.56),
        ("-4,82", -4.82),
    ],
)
def test_normalize_decimal_variants(raw: str, expected: float):
    result = normalize_decimal(raw)
    assert result is not None
    assert result == pytest.approx(expected)


def test_normalize_decimal_invalid_input_logs(caplog: pytest.LogCaptureFixture):
    with caplog.at_level("WARNING"):
        assert normalize_decimal("not-a-number") is None
    assert any("normalize_decimal" in record.message for record in caplog.records)


def test_extract_measurement_params_from_tables():
    tables = _sample_measurement_tables()

    params = extract_measurement_params("", tables=tables)

    expected = [
        ("Baş ivmesi (a Kopf über 3 ms)", "g", 58.15, "58,15"),
        ("Baş ivmesi (a Kopf über 3 ms)", "g", 64.72, "64,72"),
        ("Göğüs ivmesi (ThAC)", "g", 18.4, "18,40"),
        ("Göğüs ivmesi (ThAC)", "g", 18.27, "18,27"),
        ("Sağ femur kuvveti (FAC right)", "kN", 4.4, "4,40"),
        ("Sağ femur kuvveti (FAC right)", "kN", 5.94, "5,94"),
        ("Sol femur kuvveti (FAC left)", "kN", 4.82, "4,82"),
        ("Sol femur kuvveti (FAC left)", "kN", 6.34, "6,34"),
        ("HAC (Head Acceleration Criterion)", "", 161.18, "161,18"),
        ("HAC (Head Acceleration Criterion)", "", 283.27, "283,27"),
    ]

    assert len(params) == len(expected)
    for measurement, (name, unit, value, raw) in zip(params, expected):
        assert measurement["name"] == name
        assert measurement["unit"] == unit
        assert measurement["raw"] == raw
        assert measurement["value"] == pytest.approx(value)


def test_extract_measurement_params_from_text_supports_commas():
    text = """
    a Kopf über 3 ms [g] 58,15
    ThAC [g] 18,40
    FAC right F [kN] 4,40
    FAC left F [kN] 4,82
    HAC, [120,10, 146,05 ms] 161,18
    """

    params = extract_measurement_params(text)

    head_values = [
        entry["value"]
        for entry in params
        if entry["name"].startswith("Baş")
    ]
    assert head_values == pytest.approx([58.15])

    thac_entries = [
        entry for entry in params if entry["name"].startswith("Göğüs")
    ]
    assert [entry["value"] for entry in thac_entries] == pytest.approx([18.4])
    assert thac_entries[0]["raw"] == "18,40"


def test_analyze_pdf_comprehensive_passes_measurement_params(monkeypatch: pytest.MonkeyPatch):
    tables = _sample_measurement_tables()
    expected_params = extract_measurement_params("", tables=tables)
    captured: dict = {}

    def _fake_extract_text_from_pdf(_):
        return {"text": "", "structured_text": "", "tables": tables}

    monkeypatch.setattr(
        "backend.pdf_analyzer.extract_text_from_pdf", _fake_extract_text_from_pdf
    )

    pdf_module = sys.modules["pdf_format_detector"]
    monkeypatch.setattr(pdf_module, "detect_pdf_format", lambda _text: "kielt_format")
    monkeypatch.setattr(
        pdf_module, "parse_kielt_format", lambda _text: {"measurement_data": "tablo"}
    )
    monkeypatch.setattr(
        "backend.pdf_analyzer.analyze_test_conditions",
        lambda *_args, **_kwargs: "conditions",
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

    def _fake_analyze_graphs(graph_text, *, tables, measurement_params):
        captured["graph_text"] = graph_text
        captured["tables"] = tables
        captured["measurement_params"] = measurement_params
        return "graphs"

    monkeypatch.setattr("backend.pdf_analyzer.analyze_graphs", _fake_analyze_graphs)

    result = analyze_pdf_comprehensive("dummy.pdf")

    assert captured["measurement_params"] == expected_params
    assert captured["tables"] == tables
    assert result["measurement_params"] == expected_params
    assert result["comprehensive_analysis"]["graphs"] == "graphs"
