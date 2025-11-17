from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import backend.pdf_analyzer as _pdf_analyzer_module
import backend.pdf_format_detector as _pdf_format_detector_module

sys.modules.setdefault("pdf_analyzer", _pdf_analyzer_module)
sys.modules.setdefault("pdf_format_detector", _pdf_format_detector_module)

from backend.pdf_analyzer import analyze_pdf_comprehensive


@pytest.mark.integration
@pytest.mark.skipif(
    not (PROJECT_ROOT / "test-samples" / "kielt22_10.pdf").exists(),
    reason="Sample PDF missing",
)
def test_parse_sample_pdf_page_2_metadata(capsys: pytest.CaptureFixture[str]) -> None:
    pdf_path = PROJECT_ROOT / "test-samples" / "kielt22_10.pdf"
    result = analyze_pdf_comprehensive(pdf_path)

    metadata = result.get("structured_data", {}).get("page_2_metadata")
    assert metadata, "page_2_metadata should be present for the synthetic sample"

    simple_keys = {
        "auftraggeber",
        "anwesende",
        "versuchsbedingungen",
        "justierung_kontrolle",
        "schlittenverzoegerung",
        "examiner",
        "testfahrzeug",
    }
    populated = {key: metadata.get(key, "") for key in simple_keys if metadata.get(key)}
    assert len(populated) == len(simple_keys)

    pruefling = metadata.get("pruefling", {})
    assert pruefling.get("bezeichnung") == "Reisebussitz Komfort"
    assert pruefling.get("hinten_montiert", {}).get("gurt") == "3-Punkt Serie"

    captured_counts = {
        "simple_fields": len(populated),
        "pruefling_keys": len([value for value in pruefling.values() if value]),
        "dummy_checks": bool(metadata.get("pruefergebnis", {}).get("dummypruefung")),
    }
    print(
        "Page-2 metadata summary:",
        f"simple_fields={captured_counts['simple_fields']}",
        f"pruefling_keys={captured_counts['pruefling_keys']}",
        f"has_dummy={captured_counts['dummy_checks']}",
    )

    out, _ = capsys.readouterr()
    assert "Page-2 metadata summary" in out
