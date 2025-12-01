# -*- coding: utf-8 -*-
"""
Structured Report Formatter for ECE-R80 Test Reports
Formats PDF data into page-by-page analysis following CODEX_INSTRUCTIONS.md specification.
"""
from __future__ import annotations

import re
import logging
from typing import Any, Dict, List, Mapping, Optional, Sequence

logger = logging.getLogger(__name__)


def _coerce_float(value: object) -> float | None:
    """Convert value to float, handling None and string inputs."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _normalize_text(value: object) -> str:
    """Normalize value to string."""
    if value is None:
        return ""
    return str(value).strip()


def extract_report_id(filename: str) -> str:
    """
    Extract report ID from filename.
    Expected format: kielt19_19.pdf -> kielt19_19
    """
    if not filename:
        return ""

    # Remove .pdf extension
    base_name = filename.lower()
    if base_name.endswith('.pdf'):
        base_name = base_name[:-4]

    return base_name


def parse_report_id_components(report_id: str) -> Dict[str, str]:
    """
    Parse report ID into components.
    Format: kielt19_19
    - kiel: Company name
    - t: Test
    - 19: Year (2019)
    - _19: Test number (19th test)
    """
    if not report_id or len(report_id) < 7:
        return {
            "company": "",
            "type": "",
            "year": "",
            "test_number": "",
            "description": "Invalid report ID format"
        }

    # Extract components
    # Assuming format: [company][type][YY]_[number]
    parts = report_id.split('_')
    if len(parts) != 2:
        return {
            "company": report_id,
            "type": "",
            "year": "",
            "test_number": "",
            "description": "Non-standard report ID format"
        }

    prefix = parts[0]  # e.g., "kielt19"
    test_number = parts[1]  # e.g., "19"

    # Extract year (last 2 digits before underscore)
    year_match = re.search(r'(\d{2})$', prefix)
    year = year_match.group(1) if year_match else ""

    # Extract company and type
    if year_match:
        company_type = prefix[:year_match.start()]
        # Last character is usually type (e.g., 't' for test)
        company = company_type[:-1] if len(company_type) > 1 else company_type
        test_type = company_type[-1] if len(company_type) > 0 else ""
    else:
        company = prefix
        test_type = ""

    return {
        "company": company,
        "type": "test" if test_type == "t" else test_type,
        "year": f"20{year}" if year else "",
        "test_number": test_number,
        "description": f"Test #{test_number} in year 20{year}" if year else f"Test #{test_number}"
    }


def extract_field(pdf_data: Dict[str, Any], field_name: str, default: str = "") -> str:
    """
    Extract a field from PDF data structure.
    Handles both structured_data and comprehensive_analysis formats.
    """
    if not pdf_data:
        return default

    # Try structured_data first
    structured_data = pdf_data.get("structured_data", {})
    if isinstance(structured_data, dict):
        # Check direct field
        value = structured_data.get(field_name)
        if value:
            return _normalize_text(value)

        # Check in nested structures
        for section_key in ["metadata", "test_info", "test_conditions", "page_1", "page_2"]:
            section = structured_data.get(section_key, {})
            if isinstance(section, dict):
                value = section.get(field_name)
                if value:
                    return _normalize_text(value)

    # Try comprehensive_analysis
    comprehensive = pdf_data.get("comprehensive_analysis", {})
    if isinstance(comprehensive, dict):
        value = comprehensive.get(field_name)
        if value:
            return _normalize_text(value)

    # Try top level
    value = pdf_data.get(field_name)
    if value:
        return _normalize_text(value)

    return default


def format_measurement_values(measurement_params: Optional[Sequence[Mapping[str, Any]]]) -> Dict[str, Any]:
    """
    Format measurement parameters into detailed structure for page 3.

    Returns structured data for left and right dummies with all measurements.
    """
    if not measurement_params:
        return {
            "left_dummy": _get_empty_dummy_data("Sol Manken (Left Dummy)"),
            "right_dummy": _get_empty_dummy_data("Sağ Manken (Right Dummy)")
        }

    # Group measurements by type
    measurements = {
        "HAC": [],
        "ThAC": [],
        "FAC_right": [],
        "FAC_left": [],
        "Kopf_3ms": []
    }

    for param in measurement_params:
        if not isinstance(param, dict):
            continue

        name = _normalize_text(param.get("name", "")).lower()
        value = _coerce_float(param.get("value"))

        if value is None:
            continue

        # Categorize measurement
        if "hac" in name:
            measurements["HAC"].append({
                "value": value,
                "name": param.get("name", ""),
                "time_range": param.get("time_range", "N/A")
            })
        elif "thac" in name or "thorax" in name:
            measurements["ThAC"].append({
                "value": value,
                "name": param.get("name", ""),
                "unit": "g"
            })
        elif "fac" in name:
            if any(kw in name for kw in ["right", "rechts", "sağ"]):
                measurements["FAC_right"].append({
                    "value": value,
                    "name": param.get("name", ""),
                    "unit": "kN"
                })
            elif any(kw in name for kw in ["left", "links", "sol"]):
                measurements["FAC_left"].append({
                    "value": value,
                    "name": param.get("name", ""),
                    "unit": "kN"
                })
        elif "kopf" in name or "head" in name:
            if "3ms" in name or "3 ms" in name:
                measurements["Kopf_3ms"].append({
                    "value": value,
                    "name": param.get("name", ""),
                    "unit": "g"
                })

    # Build structured data for left and right dummies
    def get_measurement(meas_list: list, index: int) -> Optional[Dict[str, Any]]:
        return meas_list[index] if len(meas_list) > index else None

    left_dummy = {
        "title": "Sol Manken (Left Dummy)",
        "HAC": _format_hac_measurement(get_measurement(measurements["HAC"], 0)),
        "ThAC": _format_thac_measurement(get_measurement(measurements["ThAC"], 0)),
        "FAC_right": _format_fac_measurement(get_measurement(measurements["FAC_right"], 0), "right"),
        "FAC_left": _format_fac_measurement(get_measurement(measurements["FAC_left"], 0), "left"),
        "Kopf_3ms": _format_kopf_measurement(get_measurement(measurements["Kopf_3ms"], 0))
    }

    right_dummy = {
        "title": "Sağ Manken (Right Dummy)",
        "HAC": _format_hac_measurement(get_measurement(measurements["HAC"], 1)),
        "ThAC": _format_thac_measurement(get_measurement(measurements["ThAC"], 1)),
        "FAC_right": _format_fac_measurement(get_measurement(measurements["FAC_right"], 1), "right"),
        "FAC_left": _format_fac_measurement(get_measurement(measurements["FAC_left"], 1), "left"),
        "Kopf_3ms": _format_kopf_measurement(get_measurement(measurements["Kopf_3ms"], 1))
    }

    return {
        "left_dummy": left_dummy,
        "right_dummy": right_dummy
    }


def _get_empty_dummy_data(title: str) -> Dict[str, Any]:
    """Return empty dummy data structure."""
    return {
        "title": title,
        "HAC": _format_hac_measurement(None),
        "ThAC": _format_thac_measurement(None),
        "FAC_right": _format_fac_measurement(None, "right"),
        "FAC_left": _format_fac_measurement(None, "left"),
        "Kopf_3ms": _format_kopf_measurement(None)
    }


def _format_hac_measurement(data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Format HAC (Head Acceleration Criterion) measurement."""
    if not data:
        return {
            "value": "UNKNOWN",
            "limit": 500,
            "status": "UNKNOWN",
            "time_range": "N/A",
            "description": "HAC (Head Acceleration Criterion)"
        }

    value = data.get("value", 0)
    return {
        "value": value,
        "limit": 500,
        "status": "PASS" if value <= 500 else "FAIL",
        "time_range": data.get("time_range", "N/A"),
        "description": "HAC (Head Acceleration Criterion)"
    }


def _format_thac_measurement(data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Format ThAC (Thorax Acceleration Criterion) measurement."""
    if not data:
        return {
            "value": "UNKNOWN",
            "unit": "g",
            "limit": 30,
            "status": "UNKNOWN",
            "description": "ThAC (Thorax Acceleration Criterion)"
        }

    value = data.get("value", 0)
    return {
        "value": value,
        "unit": "g",
        "limit": 30,
        "status": "PASS" if value <= 30 else "FAIL",
        "description": "ThAC (Thorax Acceleration Criterion)"
    }


def _format_fac_measurement(data: Optional[Dict[str, Any]], side: str) -> Dict[str, Any]:
    """Format FAC (Femur Acceleration) measurement."""
    side_label = "Right" if side == "right" else "Left"
    if not data:
        return {
            "value": "UNKNOWN",
            "unit": "kN",
            "limit": 10,
            "status": "UNKNOWN",
            "description": f"FAC {side_label} (Femur Acceleration {side_label})"
        }

    value = data.get("value", 0)
    return {
        "value": value,
        "unit": "kN",
        "limit": 10,
        "status": "PASS" if value <= 10 else "FAIL",
        "description": f"FAC {side_label} (Femur Acceleration {side_label})"
    }


def _format_kopf_measurement(data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Format Kopf 3ms (Head Acceleration over 3ms) measurement."""
    if not data:
        return {
            "value": "UNKNOWN",
            "unit": "g",
            "limit": 80,
            "status": "UNKNOWN",
            "description": "Kopf 3ms (Head Acceleration over 3ms)"
        }

    value = data.get("value", 0)
    return {
        "value": value,
        "unit": "g",
        "limit": 80,
        "status": "PASS" if value <= 80 else "FAIL",
        "description": "Kopf 3ms (Head Acceleration over 3ms)"
    }


def calculate_overall_summary(page_3_measurements: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate overall test summary from page 3 measurements.

    Returns summary with total tests, passed, failed, and overall status.
    """
    total_tests = 0
    passed_tests = 0
    failed_tests = 0

    # Count tests from both dummies
    for dummy_key in ["left_dummy", "right_dummy"]:
        dummy_data = page_3_measurements.get(dummy_key, {})
        for measurement_key in ["HAC", "ThAC", "FAC_right", "FAC_left", "Kopf_3ms"]:
            measurement = dummy_data.get(measurement_key, {})
            status = measurement.get("status", "UNKNOWN")

            if status != "UNKNOWN":
                total_tests += 1
                if status == "PASS":
                    passed_tests += 1
                elif status == "FAIL":
                    failed_tests += 1

    overall_status = "ALL TESTS PASSED" if failed_tests == 0 and total_tests > 0 else "SOME TESTS FAILED"
    if total_tests == 0:
        overall_status = "NO TEST DATA"

    success_rate = (passed_tests / total_tests * 100.0) if total_tests > 0 else 0.0

    return {
        "total_tests": total_tests,
        "passed_tests": passed_tests,
        "failed_tests": failed_tests,
        "success_rate": f"{success_rate:.1f}%",
        "overall_status": overall_status
    }


def format_kielt_report_analysis(
    pdf_data: Dict[str, Any],
    measurement_params: Optional[Sequence[Mapping[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Format PDF data into structured page-by-page analysis.
    Follows CODEX_INSTRUCTIONS.md specification exactly.

    Args:
        pdf_data: Dictionary containing PDF extraction results
        measurement_params: List of measurement parameters from PDF

    Returns:
        Dictionary with structured page-by-page analysis
    """
    # Extract report ID from filename
    filename = pdf_data.get("filename", "")
    report_id = extract_report_id(filename)
    report_id_breakdown = parse_report_id_components(report_id)

    structured_data = pdf_data.get("structured_data", {}) if isinstance(pdf_data, dict) else {}
    page_2_metadata = structured_data.get("page_2_metadata") if isinstance(structured_data, dict) else {}

    pruefling_details: Dict[str, Any] = {}
    if isinstance(page_2_metadata, dict):
        maybe_pruefling = page_2_metadata.get("pruefling")
        if isinstance(maybe_pruefling, dict):
            pruefling_details = maybe_pruefling

    test_product_name = _normalize_text(pruefling_details.get("bezeichnung")) if pruefling_details else ""

    # Page 1: Cover Page
    page_1_cover = {
        "report_title": "Prüfbericht (Test Report)",
        "test_type": "ECE-R80 Darbe Testi (M2/M3)",
        "test_type_full": "Aufpralluntersuchung nach ECE-R80, M2/M3 (Impact Test according to ECE-R80)",
        "report_id": report_id,
        "report_id_breakdown": report_id_breakdown,
        "prepared_by": extract_field(pdf_data, "Bearbeiter", "N/A"),
        "commissioned_by": extract_field(pdf_data, "im Auftrag der", "N/A")
    }

    # Page 2: Test Conditions & Metadata
    page_2_conditions = {
        "client": extract_field(pdf_data, "Auftraggeber", "N/A"),
        "participants": extract_field(pdf_data, "Anwesende", "N/A"),
        "consultant": extract_field(pdf_data, "Sachverständiger", "N/A"),
        "file": report_id,
        "test_conditions": {
            "standard": extract_field(pdf_data, "Versuchsbedingungen", "ECE-R 80, M3/M2"),
            "type": extract_field(pdf_data, "test_type", "Abnahmetest (Acceptance test)"),
            "equipment": extract_field(pdf_data, "Verwendete Geräte", "N/A"),
            "control": extract_field(pdf_data, "Justierung/Kontrolle", "N/A")
        },
        "test_product": extract_field(pdf_data, "Prüfling", "N/A"),
        "test_product_name": test_product_name or "N/A",
        "test_result_summary": extract_field(pdf_data, "Prüfergebnis", "N/A"),
        "test_result_details": {}
    }

    if isinstance(page_2_metadata, dict):
        pruefergebnis_details = page_2_metadata.get("pruefergebnis")
        criteria_details = {}
        if isinstance(pruefergebnis_details, dict):
            raw_criteria = pruefergebnis_details.get("criteria")
            if isinstance(raw_criteria, dict):
                criteria_details = raw_criteria
            elif "scharfe_kanten" in pruefergebnis_details:
                criteria_details = {"scharfe_kanten": pruefergebnis_details.get("scharfe_kanten")}

        sharp_edge_value = _normalize_text(criteria_details.get("scharfe_kanten")) if criteria_details else ""
        if sharp_edge_value:
            page_2_conditions["test_result_details"]["sharp_edges"] = sharp_edge_value

    if not page_2_conditions["test_product_name"] and page_2_conditions["test_product"]:
        page_2_conditions["test_product_name"] = page_2_conditions["test_product"]

    # Page 3: Measurement Values (CRITICAL!)
    page_3_measurements = format_measurement_values(measurement_params)

    # Page 4: Sled Deceleration
    page_4_sled = {
        "examiner": extract_field(pdf_data, "Examiner", "IWW"),
        "test_conditions": extract_field(pdf_data, "Test conditions", "UN-R80"),
        "date": extract_field(pdf_data, "Date", "N/A"),
        "test_vehicle": extract_field(pdf_data, "Test vehicle", "N/A"),
        "test_seat": extract_field(pdf_data, "Test seat", "N/A"),
        "seat_belt": extract_field(pdf_data, "Seat belt", "Beckengurt (Lap belt)"),
        "occupant": extract_field(pdf_data, "Occupant", "2x 50% Mann (2 male dummies)"),
        "sled_velocity": extract_field(pdf_data, "Sled velocity", "30 - 32 / 30.5 km/h"),
        "graph_description": "Sled deceleration curve analysis"
    }

    # Pages 5-6: Photo Documentation
    pages_5_6_photos = {
        "pre_test": "Abb.1 - Abb.6 (6 photographs)",
        "post_test": "Abb.7 - Abb.12 (6 photographs)",
        "total": 12,
        "description": "Fotodokumentation: Test setup and results"
    }

    # Overall Summary
    overall_summary = calculate_overall_summary(page_3_measurements)

    return {
        "format_version": "1.0",
        "report_type": "ECE-R80",
        "page_1_cover": page_1_cover,
        "page_2_conditions": page_2_conditions,
        "page_3_measurements": page_3_measurements,
        "page_4_sled": page_4_sled,
        "pages_5_6_photos": pages_5_6_photos,
        "overall_summary": overall_summary
    }


__all__ = [
    "format_kielt_report_analysis",
    "extract_report_id",
    "parse_report_id_components",
    "format_measurement_values",
    "calculate_overall_summary"
]
