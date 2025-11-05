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
from backend.pdf_format_detector import extract_measurement_params
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


def test_extract_measurement_params_from_tables():
    tables = _sample_measurement_tables()

    params = extract_measurement_params("", tables=tables)

    assert params == [
        {
            "name": "Baş ivmesi (a Kopf über 3 ms)",
            "unit": "g",
            "values": ["58.15", "64.72"],
        },
        {
            "name": "Göğüs ivmesi (ThAC)",
            "unit": "g",
            "values": ["18.40", "18.27"],
        },
        {
            "name": "Sağ femur kuvveti (FAC right)",
            "unit": "kN",
            "values": ["4.40", "5.94"],
        },
        {
            "name": "Sol femur kuvveti (FAC left)",
            "unit": "kN",
            "values": ["4.82", "6.34"],
        },
        {
            "name": "HAC (Head Acceleration Criterion)",
            "unit": "",
            "values": ["161.18", "283.27"],
        },
    ]


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
