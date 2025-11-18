from pathlib import Path
import sys

import pytest


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.ai_response_handler import parse_ai_response_safely
from backend.measurement_analysis import build_measurement_analysis


def _sample_measurement_payload():
    return build_measurement_analysis(
        [
            {"name": "HAC Left", "value": 32.5},
            {"name": "ThAC Right", "value": 41.2},
            {"name": "FAC", "value": 7.8},
        ],
        report_id="report-123",
        test_conditions="Ambient 20C, humidity 45%",
    )


@pytest.mark.parametrize(
    "response_text",
    [
        "```markdown\n**Summary:** Values look good overall.\n- PASS metrics listed\n```",
        "AI response in plain text describing measurements without JSON formatting.",
    ],
)
def test_parse_ai_response_returns_measurement_fallback(response_text):
    fallback_payload = _sample_measurement_payload()
    assert "parsing_status" not in fallback_payload

    parsed = parse_ai_response_safely(response_text, fallback_data=fallback_payload)

    assert parsed["report_id"] == fallback_payload["report_id"]
    assert parsed["measured_values"] == fallback_payload["measured_values"]
    assert parsed["overall_summary"] == fallback_payload["overall_summary"]
    assert parsed["parsing_status"] == "fallback_used"
    assert parsed.get("ai_summary"), "AI summary should capture the raw response"
    assert parsed.get("raw_response_excerpt").startswith(response_text[:10])
    assert "parsing_status" not in fallback_payload
