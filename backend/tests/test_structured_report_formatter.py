# -*- coding: utf-8 -*-
from backend.structured_report_formatter import format_kielt_report_analysis


def test_kielt_formatter_uses_pruefling_bezeichnung_and_sharp_edges():
    pdf_data = {
        "filename": "kielt24_01.pdf",
        "structured_data": {
            "page_2_metadata": {
                "pruefling": {"bezeichnung": "Seri Koltuk A1"},
                "pruefergebnis": {"criteria": {"scharfe_kanten": "n.i.O."}},
            },
            "page_2": {"Prüfling": "Genel Koltuk", "Prüfergebnis": "n.i.O."},
        },
    }

    formatted = format_kielt_report_analysis(pdf_data, [])

    page_2 = formatted["page_2_conditions"]
    assert page_2["test_product"] == "Genel Koltuk"
    assert page_2["test_product_name"] == "Seri Koltuk A1"
    assert page_2["test_result_summary"] == "n.i.O."
    assert page_2["test_result_details"].get("sharp_edges") == "n.i.O."
