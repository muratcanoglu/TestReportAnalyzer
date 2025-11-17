# -*- coding: utf-8 -*-
"""Prompt builder for simplified, structured PDF analyses."""
from __future__ import annotations

import json
import textwrap
from typing import Any, Dict, Optional


def _serialize_payload(data: Dict[str, Any]) -> str:
    try:
        return json.dumps(data, ensure_ascii=False, indent=2)
    except TypeError:
        return json.dumps(json.loads(json.dumps(data, default=str)), ensure_ascii=False, indent=2)


def build_simplified_analysis_prompt(structured_data: Optional[Dict[str, Any]]) -> str:
    """Create a concise prompt where numerical fields are pre-filled."""

    structured = structured_data or {}
    page_3 = structured.get("page_3_dummy_loads") or {}
    overall_summary = structured.get("overall_summary") or {}

    prompt_payload = {
        "report_id": structured.get("test_conditions", {}).get("report_id"),
        "test_conditions": structured.get("test_conditions"),
        "page_3_dummy_loads": page_3,
        "page_4_sled": structured.get("page_4_sled", {"deceleration_analysis": ""}),
        "photo_documentation": structured.get(
            "photo_documentation",
            {"pre_test": "", "during_test": "", "post_test": ""},
        ),
        "overall_summary": overall_summary,
    }

    json_snapshot = _serialize_payload(prompt_payload)
    text_excerpt = structured.get("raw_text_excerpt", "") or ""

    prompt = f"""
    Sen bir ECE-R80 darbe testi uzmanısın. PDF tablosundan çıkarılan sayısal alanlar aşağıdaki JSON içinde hazır durumda.

    Görevin:
    - graph_analysis alanlarını tablo verilerine dayanarak açıklamak,
    - overall_summary.notes kısmına genel bir başarı yorumu eklemek,
    - test_conditions içindeki eksik metinsel alanları ham metin özetinden tamamlamak.
    - JSON yapısını değiştirme ve SADECE JSON döndür.

    Başlangıç verisi:
    {json_snapshot}

    Ham metin özeti:
    {text_excerpt}
    """

    return textwrap.dedent(prompt).strip()


__all__ = ["build_simplified_analysis_prompt"]
