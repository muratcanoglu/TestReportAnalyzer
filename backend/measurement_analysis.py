# -*- coding: utf-8 -*-
"""Helpers for building measurement-based fallback analyses."""
from __future__ import annotations

import logging
from typing import Any, Dict, Mapping, Sequence

try:  # pragma: no cover - prefer absolute imports
    from backend.structured_analyzer import calculate_pass_fail_status
except ImportError:  # pragma: no cover - fallback for package-relative imports
    try:
        from .structured_analyzer import calculate_pass_fail_status  # type: ignore
    except ImportError:  # pragma: no cover - repository root execution
        from structured_analyzer import calculate_pass_fail_status  # type: ignore

logger = logging.getLogger(__name__)

DEFAULT_TEST_TYPE = "ECE-R80 Darbe Testi"


def _coerce_float(value: object) -> float | None:
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


def _normalise_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _summarise_test_conditions(value: object, max_length: int = 400) -> str:
    text = ""
    if isinstance(value, str):
        text = value.strip()
    elif isinstance(value, Mapping):
        parts: list[str] = []
        for key in ("summary", "text", "description"):
            candidate = value.get(key)
            candidate_text = _normalise_text(candidate)
            if candidate_text:
                parts.append(candidate_text)
        key_values = value.get("key_values") if isinstance(value, Mapping) else None
        if isinstance(key_values, Mapping):
            kv_parts = [
                f"{_normalise_text(key)}: {_normalise_text(val)}"
                for key, val in key_values.items()
                if _normalise_text(key) and _normalise_text(val)
            ]
            if kv_parts:
                parts.append("; ".join(kv_parts))
        text = " ".join(part for part in parts if part)
    else:
        text = _normalise_text(value)

    text = text.strip()
    if len(text) > max_length:
        return text[:max_length].rstrip() + "..."
    return text


def _group_measurement_entries(
    measurement_params: Sequence[Mapping[str, Any]] | None,
) -> Dict[str, list[float]]:
    grouped = {
        "HAC": [],
        "ThAC": [],
        "FAC_LEFT": [],
        "FAC_RIGHT": [],
        "FAC_GENERIC": [],
    }

    for entry in measurement_params or []:
        name = _normalise_text(entry.get("name")).lower()
        value = _coerce_float(entry.get("value"))
        if not name or value is None:
            continue

        if "hac" in name:
            grouped["HAC"].append(value)
        elif "thac" in name or "thorax" in name:
            grouped["ThAC"].append(value)
        elif "fac" in name:
            if any(keyword in name for keyword in ("right", "rechts", "sağ")):
                grouped["FAC_RIGHT"].append(value)
            elif any(keyword in name for keyword in ("left", "links", "sol")):
                grouped["FAC_LEFT"].append(value)
            else:
                grouped["FAC_GENERIC"].append(value)

    return grouped


def _assign_femur_value(
    specific: Sequence[float],
    fallback_values: Sequence[float],
    index: int,
) -> float | None:
    if specific and len(specific) > index:
        return specific[index]
    if fallback_values and len(fallback_values) > index:
        return fallback_values[index]
    if fallback_values:
        return fallback_values[0]
    return None


def build_measurement_analysis(
    measurement_params: Sequence[Mapping[str, Any]] | None,
    report_id: object,
    test_conditions: object = "",
) -> Dict[str, Any]:
    """Build a structured fallback analysis from raw measurement parameters."""

    normalized_report_id = _normalise_text(report_id) or "measurement-analysis"
    grouped = _group_measurement_entries(measurement_params)

    left_dummy = {
        "HAC": grouped["HAC"][0] if grouped["HAC"] else None,
        "ThAC": grouped["ThAC"][0] if grouped["ThAC"] else None,
        "FAC": _assign_femur_value(
            grouped["FAC_LEFT"], grouped["FAC_GENERIC"], index=0
        ),
    }
    right_dummy = {
        "HAC": grouped["HAC"][1] if len(grouped["HAC"]) > 1 else None,
        "ThAC": grouped["ThAC"][1] if len(grouped["ThAC"]) > 1 else None,
        "FAC": _assign_femur_value(
            grouped["FAC_RIGHT"], grouped["FAC_GENERIC"], index=1
        ),
    }

    measured_values = {"left_dummy": left_dummy, "right_dummy": right_dummy}
    status_payload = calculate_pass_fail_status(measured_values)

    analysis = {
        "report_id": normalized_report_id,
        "test_type": DEFAULT_TEST_TYPE,
        "measured_values": status_payload.get("measured_values", measured_values),
        "overall_summary": status_payload.get(
            "overall_summary",
            {
                "total_tests": 0,
                "passed": 0,
                "failed": 0,
                "success_rate": "0.0%",
            },
        ),
        "test_conditions_summary": _summarise_test_conditions(test_conditions),
        "data_source": "measurement_extraction",
        "ai_analysis_available": False,
    }

    if not any(value for value in (grouped["HAC"], grouped["ThAC"], grouped["FAC_LEFT"], grouped["FAC_RIGHT"], grouped["FAC_GENERIC"])):
        analysis.setdefault(
            "notes",
            "Ölçüm parametreleri çıkarılamadı; değerler UNKNOWN olarak işaretlendi.",
        )

    return analysis


def _resolve_report_identifier(payload: Mapping[str, Any], fallback: str) -> str:
    candidates: list[object] = []
    for key in ("report_id", "document_id", "test_file_id"):
        candidates.append(payload.get(key))
    test_conditions = payload.get("test_conditions")
    if isinstance(test_conditions, Mapping):
        for key in ("report_id", "id", "name"):
            candidates.append(test_conditions.get(key))
    candidates.append(payload.get("pdf_path"))
    candidates.append(fallback)

    for candidate in candidates:
        text = _normalise_text(candidate)
        if text:
            return text
    return fallback


def build_measurement_fallback_from_payload(
    structured_payload: Mapping[str, Any] | None,
    *,
    default_report_id: str = "measurement-analysis",
) -> Dict[str, Any]:
    """Create a fallback analysis from a structured payload used for AI prompts."""

    payload: Mapping[str, Any] = structured_payload or {}
    measurement_params: Sequence[Mapping[str, Any]] | None = (
        payload.get("raw_measurements")
        or payload.get("measurement_params")
        or []
    )
    test_conditions_source = payload.get("test_conditions") or payload.get(
        "raw_text_excerpt", ""
    )
    report_identifier = _resolve_report_identifier(payload, default_report_id)
    return build_measurement_analysis(
        measurement_params=measurement_params,
        report_id=report_identifier,
        test_conditions=test_conditions_source,
    )


__all__ = [
    "build_measurement_analysis",
    "build_measurement_fallback_from_payload",
]
