# -*- coding: utf-8 -*-
"""Structured data preparation helpers for AI analysis."""
from __future__ import annotations

import logging
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional

try:  # pragma: no cover - prefer absolute imports when running as package
    from backend.pdf_analyzer import extract_text_from_pdf
    from backend.pdf_format_detector import extract_measurement_params
    from backend.pdf_format_detector import normalize_decimal  # noqa: F401  # compatibility
    from backend.pdf_format_detector import parse_kielt_format
    from backend.structured_data_parser import parse_test_conditions_structured
except ImportError:  # pragma: no cover - fallback for script execution
    try:
        from .pdf_analyzer import extract_text_from_pdf  # type: ignore
        from .pdf_format_detector import (  # type: ignore
            extract_measurement_params,
            normalize_decimal,
            parse_kielt_format,
        )
        from .structured_data_parser import parse_test_conditions_structured  # type: ignore
    except ImportError:  # pragma: no cover - running from repository root
        from pdf_analyzer import extract_text_from_pdf  # type: ignore
        from pdf_format_detector import (  # type: ignore
            extract_measurement_params,
            normalize_decimal,
            parse_kielt_format,
        )
        from structured_data_parser import parse_test_conditions_structured  # type: ignore


logger = logging.getLogger(__name__)

DEFAULT_LIMITS = {"HAC": 500.0, "ThAC": 30.0, "FAC": 10.0}
_FAC_UNIT = "kN"
_ACC_UNIT = "g"
_REPORT_ID_PATTERN = re.compile(r"kielt\d+_\d+", re.IGNORECASE)


def _clean_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_identifier(value: object) -> str:
    text = _clean_text(value)
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = normalized.lower()
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return normalized.strip()


def _group_measurements(entries: List[Dict[str, Any]]) -> Dict[str, List[float]]:
    grouped: Dict[str, List[float]] = {
        "HAC": [],
        "ThAC": [],
        "FAC_LEFT": [],
        "FAC_RIGHT": [],
        "FAC": [],
    }

    for entry in entries:
        value = entry.get("value")
        if value is None:
            continue
        identifier = _normalize_identifier(entry.get("name"))
        if not identifier:
            continue
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            continue

        if "hac" in identifier:
            grouped["HAC"].append(numeric_value)
        elif "thac" in identifier or "thorax" in identifier:
            grouped["ThAC"].append(numeric_value)
        elif "fac" in identifier:
            if any(keyword in identifier for keyword in ("right", "rechts", "sag")):
                grouped["FAC_RIGHT"].append(numeric_value)
            elif any(keyword in identifier for keyword in ("left", "links", "sol")):
                grouped["FAC_LEFT"].append(numeric_value)
            else:
                grouped["FAC"].append(numeric_value)

    return grouped


def extract_test_values_from_tables(
    tables_data: Optional[List[Dict[str, Any]]],
) -> Dict[str, Any]:
    """Extract dummy load values from parsed PDF tables."""

    measured_values = {
        "left_dummy": {"HAC": None, "ThAC": None, "FAC": None},
        "right_dummy": {"HAC": None, "ThAC": None, "FAC": None},
    }

    raw_measurements: List[Dict[str, Any]] = []
    if tables_data and extract_measurement_params:
        try:
            raw_measurements = extract_measurement_params("", tables=tables_data) or []
        except Exception as exc:  # pragma: no cover - runtime safety
            logger.warning("Failed to parse measurement tables: %s", exc)

    grouped = _group_measurements(raw_measurements)

    def _assign_dual(metric: str, values: List[float]) -> None:
        if not values:
            return
        measured_values["left_dummy"][metric] = values[0]
        if len(values) >= 2:
            measured_values["right_dummy"][metric] = values[1]

    _assign_dual("HAC", grouped.get("HAC", []))
    _assign_dual("ThAC", grouped.get("ThAC", []))

    if grouped.get("FAC_LEFT"):
        measured_values["left_dummy"]["FAC"] = grouped["FAC_LEFT"][0]
    if grouped.get("FAC_RIGHT"):
        measured_values["right_dummy"]["FAC"] = grouped["FAC_RIGHT"][0]

    fallback_fac = grouped.get("FAC", [])
    if fallback_fac:
        if measured_values["left_dummy"].get("FAC") is None:
            measured_values["left_dummy"]["FAC"] = fallback_fac[0]
        if (
            len(fallback_fac) >= 2
            and measured_values["right_dummy"].get("FAC") is None
        ):
            measured_values["right_dummy"]["FAC"] = fallback_fac[1]

    return {
        "measured_values": measured_values,
        "raw_measurements": raw_measurements,
    }


def calculate_pass_fail_status(
    measured_values: Dict[str, Dict[str, Optional[float]]]
) -> Dict[str, Any]:
    """Compare measured values with predefined limits and build a summary."""

    status_data: Dict[str, Dict[str, Any]] = {}
    total_tests = 0
    passed = 0
    failed = 0

    for dummy_name, dummy_values in (measured_values or {}).items():
        dummy_status: Dict[str, Any] = {metric: value for metric, value in dummy_values.items()}
        metric_results: List[bool] = []
        for metric, limit in DEFAULT_LIMITS.items():
            value = dummy_values.get(metric) if dummy_values else None
            if value is None:
                dummy_status[f"{metric}_status"] = "UNKNOWN"
                continue
            total_tests += 1
            if value <= limit:
                metric_results.append(True)
                passed += 1
                dummy_status[f"{metric}_status"] = "PASS"
            else:
                metric_results.append(False)
                failed += 1
                dummy_status[f"{metric}_status"] = "FAIL"
            dummy_status[f"{metric}_limit"] = limit

        if metric_results and all(metric_results):
            dummy_status["overall_result"] = "PASS"
        elif metric_results and any(metric_results):
            dummy_status["overall_result"] = "PARTIAL"
        elif metric_results:
            dummy_status["overall_result"] = "FAIL"
        else:
            dummy_status["overall_result"] = "UNKNOWN"

        status_data[dummy_name] = dummy_status

    success_rate = (passed / total_tests * 100.0) if total_tests else 0.0
    summary = {
        "total_tests": total_tests,
        "passed": passed,
        "failed": failed,
        "success_rate": f"{success_rate:.1f}%",
        "notes": "",
    }

    return {"measured_values": status_data, "overall_summary": summary}


def extract_test_conditions(
    text: str, metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Extract key test condition metadata from text or parser output."""

    structured = parse_test_conditions_structured(text or "")
    if metadata:
        kv = structured.setdefault("key_values", {})
        for key, value in metadata.items():
            if key not in kv:
                kv[key] = value

    if "report_id" not in structured and text:
        match = _REPORT_ID_PATTERN.search(text)
        if match:
            structured["report_id"] = match.group(0)

    return structured


def _format_metric_comment(
    metric: str,
    measured_values: Dict[str, Dict[str, Optional[float]]],
    *,
    unit: str,
) -> str:
    left_value = measured_values.get("left_dummy", {}).get(metric)
    right_value = measured_values.get("right_dummy", {}).get(metric)
    limit = DEFAULT_LIMITS.get(metric)
    parts: List[str] = []
    if left_value is not None:
        parts.append(f"sol manken {left_value:.2f} {unit}")
    if right_value is not None:
        parts.append(f"sağ manken {right_value:.2f} {unit}")
    if not parts:
        return "Tablo verilerinde bu ölçüm bulunamadı."
    limit_text = f"limit {limit:.0f} {unit}" if limit is not None else "limit belirtilmedi"
    return f"{metric} ölçümleri {' ve '.join(parts)} olup {limit_text} değerine göre karşılaştırılabilir."


def build_structured_data_for_ai(
    pdf_path: Optional[str],
    *,
    fallback_text: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a structured payload (tables + metadata) for the AI prompt."""

    extracted_text = fallback_text or ""
    tables: List[Dict[str, Any]] = []

    if pdf_path:
        path_obj = Path(pdf_path)
        if path_obj.exists():
            try:
                pdf_content = extract_text_from_pdf(path_obj)
                extracted_text = (
                    pdf_content.get("structured_text")
                    or pdf_content.get("text")
                    or extracted_text
                )
                tables = pdf_content.get("tables") or []
            except Exception as exc:  # pragma: no cover - runtime safety
                logger.warning("PDF extraction failed for %s: %s", pdf_path, exc)
        else:
            logger.warning("PDF path does not exist: %s", pdf_path)

    sections = {}
    if extracted_text:
        try:
            sections = parse_kielt_format(extracted_text)
        except Exception as exc:  # pragma: no cover - runtime safety
            logger.debug("parse_kielt_format failed: %s", exc)

    test_conditions_text = sections.get("test_conditions") if sections else extracted_text
    test_conditions = extract_test_conditions(test_conditions_text or "", metadata)

    table_payload = extract_test_values_from_tables(tables)
    status_payload = calculate_pass_fail_status(table_payload["measured_values"])

    measured_values = status_payload["measured_values"]
    graph_analysis = {
        "head_acceleration": _format_metric_comment("HAC", measured_values, unit=_ACC_UNIT),
        "chest_acceleration": _format_metric_comment(
            "ThAC", measured_values, unit=_ACC_UNIT
        ),
        "femur_load": _format_metric_comment("FAC", measured_values, unit=_FAC_UNIT),
    }

    structured_payload = {
        "pdf_path": pdf_path or "",
        "test_conditions": test_conditions,
        "page_3_dummy_loads": {
            "measured_values": measured_values,
            "graph_analysis": graph_analysis,
            "limits": DEFAULT_LIMITS,
        },
        "overall_summary": status_payload["overall_summary"],
        "raw_measurements": table_payload["raw_measurements"],
        "raw_text_excerpt": (extracted_text or "")[:2000],
        "tables_found": len(tables),
        "page_4_sled": {"sled_velocity": None, "deceleration_analysis": ""},
        "photo_documentation": {"pre_test": "", "during_test": "", "post_test": ""},
    }

    structured_payload["overall_summary"].setdefault("notes", "")

    if metadata:
        structured_payload["page_2_metadata"] = metadata

    return structured_payload


__all__ = [
    "build_structured_data_for_ai",
    "calculate_pass_fail_status",
    "extract_test_conditions",
    "extract_test_values_from_tables",
]
