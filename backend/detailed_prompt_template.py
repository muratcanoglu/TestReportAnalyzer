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

    === OUTPUT FORMAT (MANDATORY) ===

    You MUST respond with this EXACT JSON structure. Fill in the values based on the data above:

    {{
      "report_id": "kielt19_86",
      "test_type": "ECE-R80 Darbe Testi",
      "test_date": "YYYY-MM-DD",
      "test_conditions": {{
        "vehicle": "...",
        "seat": "...",
        "velocity": "...",
        "standard": "UN-R80"
      }},
      "measured_values": {{
        "left_dummy": {{
          "HAC": 98.27,
          "HAC_status": "PASS",
          "HAC_limit": 500,
          "ThAC": 14.51,
          "ThAC_status": "PASS",
          "ThAC_limit": 30,
          "FAC_right": 4.71,
          "FAC_left": 4.31,
          "FAC_status": "PASS",
          "FAC_limit": 10,
          "overall_result": "PASS"
        }},
        "right_dummy": {{
          "HAC": 119.41,
          "HAC_status": "PASS",
          "HAC_limit": 500,
          "ThAC": 14.91,
          "ThAC_status": "PASS",
          "ThAC_limit": 30,
          "FAC_right": 3.11,
          "FAC_left": 3.65,
          "FAC_status": "PASS",
          "FAC_limit": 10,
          "overall_result": "PASS"
        }}
      }},
      "graph_analysis": {{
        "head_acceleration": "HAC values: Left 98.27, Right 119.41. Both within limits.",
        "chest_acceleration": "ThAC values: Left 14.51g, Right 14.91g. Both within limits.",
        "thigh_force": "FAC values within acceptable range."
      }},
      "overall_summary": {{
        "total_tests": 4,
        "passed": 4,
        "failed": 0,
        "success_rate": "100.0%",
        "critical_findings": [],
        "expert_notes": [
          "All measurements within safety limits",
          "Test completed successfully"
        ]
      }}
    }}

    IMPORTANT:
    - Copy this structure exactly
    - Replace placeholder values with actual data
    - Keep all field names identical
    - Do NOT add any text before or after the JSON
    - Start your response with {{ and end with }}
    """

    return textwrap.dedent(prompt).strip()


__all__ = ["build_simplified_analysis_prompt"]
