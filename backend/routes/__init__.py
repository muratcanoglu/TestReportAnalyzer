"""Flask routes for the TestReportAnalyzer backend."""
from __future__ import annotations

import os
import logging
import difflib
import re
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

from flask import Blueprint, current_app, jsonify, request, send_file
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)

try:  # pragma: no cover - prefer absolute imports
    from backend import database
    from backend.database import (
        insert_report,
        insert_test_result,
        report_exists_with_filename,
        update_report_comprehensive_analysis,
        update_report_stats,
    )
    from backend.ai_analyzer import ai_analyzer
    from backend.translation_utils import fallback_translate_text
    from backend.measurement_analysis import build_measurement_analysis
    from backend.structured_report_formatter import format_kielt_report_analysis
    from backend.pdf_analyzer import (
        REPORT_TYPE_LABELS,
        analyze_pdf_comprehensive,
        extract_text_from_pdf,
        infer_report_type,
        parse_test_results,
    )
except ImportError:  # pragma: no cover - fallback for script execution
    logger.warning(
        "backend.routes falling back to relative imports for critical dependencies",
    )
    try:
        from .. import database  # type: ignore
        from ..database import (  # type: ignore
            insert_report,
            insert_test_result,
            report_exists_with_filename,
            update_report_comprehensive_analysis,
            update_report_stats,
        )
        from ..ai_analyzer import ai_analyzer  # type: ignore
        from ..translation_utils import fallback_translate_text  # type: ignore
        from ..measurement_analysis import build_measurement_analysis  # type: ignore
        from ..structured_report_formatter import format_kielt_report_analysis  # type: ignore
        from ..pdf_analyzer import (  # type: ignore
            REPORT_TYPE_LABELS,
            analyze_pdf_comprehensive,
            extract_text_from_pdf,
            infer_report_type,
            parse_test_results,
        )
    except ImportError:  # pragma: no cover - running from repository root
        logger.warning(
            "backend.routes using local import paths; ensure PYTHONPATH includes project root.",
        )
        import database  # type: ignore
        from database import (  # type: ignore
            insert_report,
            insert_test_result,
            report_exists_with_filename,
            update_report_comprehensive_analysis,
            update_report_stats,
        )
        from ai_analyzer import ai_analyzer  # type: ignore
        from translation_utils import fallback_translate_text  # type: ignore
        from measurement_analysis import build_measurement_analysis  # type: ignore
        from structured_report_formatter import format_kielt_report_analysis  # type: ignore
        from pdf_analyzer import (  # type: ignore
            REPORT_TYPE_LABELS,
            analyze_pdf_comprehensive,
            extract_text_from_pdf,
            infer_report_type,
            parse_test_results,
        )

reports_bp = Blueprint("reports", __name__)
bp = reports_bp


@bp.route('/health', methods=['GET'])
def health_check():
    """Backend sağlık kontrolü"""
    return jsonify({
        'status': 'ok',
        'message': 'Backend çalışıyor',
        'timestamp': datetime.now().isoformat()
    })


def _json_error(message: str, status_code: int = 400):
    response = jsonify({"error": message})
    response.status_code = status_code
    return response


def _resolve_report_type_label(raw_type: str | None) -> str:
    key = (raw_type or "unknown").strip().lower()
    default_label = REPORT_TYPE_LABELS.get("unknown", "Bilinmeyen")
    return REPORT_TYPE_LABELS.get(key, default_label)


def _derive_alignment_key(total_tests: int, passed_tests: int, failed_tests: int) -> str:
    if total_tests <= 0:
        return "unknown"
    if failed_tests == 0 and passed_tests > 0:
        return "strong"
    if passed_tests == 0 and failed_tests > 0:
        return "critical"
    if passed_tests > 0 and failed_tests > 0:
        return "mixed"
    return "unknown"


SUMMARY_LABELS = {
    "tr": {
        "summary": "Genel Özet",
        "conditions": "Test Koşulları",
        "improvements": "İyileştirme Önerileri",
        "technical": "Teknik Analiz Detayları",
        "highlights": "Öne Çıkan Bulgular",
        "failures": "Kritik Testler",
    },
    "en": {
        "summary": "Summary",
        "conditions": "Test Conditions",
        "improvements": "Improvement Suggestions",
        "technical": "Technical Analysis Details",
        "highlights": "Key Highlights",
        "failures": "Critical Tests",
    },
    "de": {
        "summary": "Zusammenfassung",
        "conditions": "Testbedingungen",
        "improvements": "Verbesserungsvorschläge",
        "technical": "Technische Analyse",
        "highlights": "Wesentliche Erkenntnisse",
        "failures": "Kritische Tests",
    },
}

ENGINE_LABELS = {
    "chatgpt": "ChatGPT",
    "claude": "Claude",
}


def _normalise_engine(engine: str | None) -> tuple[str, str]:
    key = (engine or "chatgpt").strip().lower()
    if key not in ENGINE_LABELS:
        key = "chatgpt"
    return key, ENGINE_LABELS[key]

LANGUAGE_TEMPLATES = {
    "tr": {
        "summary": (
            "{engine}, {filename} raporunu {report_type} kapsamında değerlendirdi. "
            "Toplam {total} testin {passed}'i başarılı, {failed}'i başarısız. Başarı oranı %{success_rate}."
        ),
        "no_tests": (
            "{engine}, {filename} raporunda değerlendirilecek test kaydı bulamadı."
        ),
        "conditions": (
            "Grafik ve metin bulguları karşılaştırıldığında test koşulları ile sonuçlar {alignment} uyum gösteriyor."
        ),
        "no_tests_conditions": (
            "Grafik ve metin içerikleri sınırlı olduğu için koşul/sonuç kıyaslaması yapılamadı."
        ),
        "alignment_words": {
            "strong": "yüksek",
            "mixed": "kısmi",
            "critical": "düşük",
            "unknown": "belirsiz",
        },
        "improvements_intro": "Başarısız testlerin başarıya ulaşması için öneriler:",
        "failure_with_fix": "{test} -> {reason}. Öneri: {fix}.",
        "failure_without_fix": (
            "{test} -> {reason}. Ek veri gerekli, test parametrelerini gözden geçirin."
        ),
        "improvements_success": (
            "Tüm testler başarıyla tamamlandı; mevcut süreç korunmalıdır."
        ),
        "no_tests_improvements": (
            "Ölçümleri içeren güncel bir test raporu yükleyerek analizi yeniden başlatın."
        ),
        "unknown_test_name": "Bilinmeyen Test",
        "default_reason": "Başarısızlık nedeni belirtilmedi",
        "labels": SUMMARY_LABELS["tr"],
    },
    "en": {
        "summary": (
            "{engine} reviewed {filename} as part of the {report_type} scope. "
            "A total of {total} tests were evaluated: {passed} passed, {failed} failed. Overall success rate {success_rate}%."
        ),
        "no_tests": (
            "{engine} could not find evaluable test results in {filename}."
        ),
        "conditions": (
            "Comparing charts and textual findings indicates {alignment} alignment between test conditions and outcomes."
        ),
        "no_tests_conditions": (
            "No comparison of conditions versus outcomes was possible because the report lacks measurements."
        ),
        "alignment_words": {
            "strong": "strong",
            "mixed": "partial",
            "critical": "low",
            "unknown": "unclear",
        },
        "improvements_intro": "To recover the failing tests, consider the following actions:",
        "failure_with_fix": "{test} -> {reason}. Recommendation: {fix}.",
        "failure_without_fix": (
            "{test} -> {reason}. Provide additional diagnostics and review acceptance criteria."
        ),
        "improvements_success": (
            "All tests passed; maintain the current validation approach."
        ),
        "no_tests_improvements": (
            "Upload a version of the report that includes executed test steps to receive guidance."
        ),
        "unknown_test_name": "Unnamed Test",
        "default_reason": "Failure cause not specified",
        "labels": SUMMARY_LABELS["en"],
    },
    "de": {
        "summary": (
            "{engine} hat den Bericht {filename} im Rahmen des {report_type} geprüft. "
            "Insgesamt {total} Tests: {passed} bestanden, {failed} fehlgeschlagen. Erfolgsquote {success_rate}%."
        ),
        "no_tests": (
            "{engine} konnte im Bericht {filename} keine auswertbaren Testergebnisse finden."
        ),
        "conditions": (
            "Der Vergleich von Diagrammen und Text zeigt eine {alignment} Übereinstimmung zwischen Prüfbedingungen und Ergebnissen."
        ),
        "no_tests_conditions": (
            "Ohne Messdaten ist kein Vergleich zwischen Bedingungen und Ergebnissen möglich."
        ),
        "alignment_words": {
            "strong": "hohe",
            "mixed": "teilweise",
            "critical": "geringe",
            "unknown": "unklare",
        },
        "improvements_intro": (
            "Um fehlgeschlagene Tests zu verbessern, werden folgende Schritte empfohlen:"
        ),
        "failure_with_fix": "{test} -> {reason}. Empfehlung: {fix}.",
        "failure_without_fix": (
            "{test} -> {reason}. Zusätzliche Messdaten bereitstellen und Grenzwerte überprüfen."
        ),
        "improvements_success": (
            "Alle Tests waren erfolgreich; der bestehende Prüfablauf kann beibehalten werden."
        ),
        "no_tests_improvements": (
            "Bitte eine Version des Berichts mit durchgeführten Tests hochladen, um Analysen zu erhalten."
        ),
        "unknown_test_name": "Unbenannter Test",
        "default_reason": "Fehlerursache nicht angegeben",
        "labels": SUMMARY_LABELS["de"],
    },
}

COMPARISON_LABELS = {
    "tr": {"overview": "Karşılaştırma Özeti", "details": "Teknik Farklar"},
    "en": {"overview": "Comparison Overview", "details": "Technical Differences"},
    "de": {"overview": "Vergleichsübersicht", "details": "Technische Unterschiede"},
}

COMPARISON_ZERO_OVERVIEW = {
    "tr": "Seçilen raporların test sonuçları birebir aynı görünüyor; farklılık tespit edilmedi.",
    "en": "The selected reports share the same test outcomes; no differences were detected.",
    "de": "Die ausgewählten Berichte zeigen keine Abweichungen in den Testergebnissen.",
}

COMPARISON_EMPTY_DETAILS = {
    "tr": "Farklılık bulunamadı.",
    "en": "No differing points were identified.",
    "de": "Es wurden keine Unterschiede festgestellt.",
}


def _merge_localized_summaries(
    fallback: dict, overrides: dict | None, *, translator=None
) -> dict:
    languages = ("tr", "en", "de")
    overrides = overrides if isinstance(overrides, dict) else {}
    fallback = fallback if isinstance(fallback, dict) else {}

    def _collect_field(field: str) -> tuple[dict[str, str], str, str]:
        collected: dict[str, str] = {}
        source_language = ""
        source_text = ""

        for language in languages:
            entry = overrides.get(language, {}) if isinstance(overrides, dict) else {}
            value = str(entry.get(field) or "").strip()
            if not value:
                continue

            detected_language = _detect_language(value)
            target_language = detected_language or language
            collected[target_language] = value

            if not source_language:
                source_language = target_language
                source_text = value

        if not collected:
            for language in languages:
                entry = fallback.get(language, {}) if isinstance(fallback, dict) else {}
                value = str(entry.get(field) or "").strip()
                if value and language not in collected:
                    collected[language] = value
                    if not source_language:
                        source_language = language
                        source_text = value

        ensured = (
            _ensure_multilingual_entries(collected, translator=translator)
            if collected
            else {}
        )

        return ensured, source_language, source_text

    summary_entries, summary_source_lang, summary_source_text = _collect_field("summary")
    conditions_entries, conditions_source_lang, conditions_source_text = _collect_field(
        "conditions"
    )
    improvements_entries, improvements_source_lang, improvements_source_text = _collect_field(
        "improvements"
    )

    merged: dict[str, dict[str, str]] = {}

    for language in languages:
        default_entry = fallback.get(language, {}) if isinstance(fallback, dict) else {}
        override_entry = overrides.get(language, {}) if isinstance(overrides, dict) else {}

        labels = dict(SUMMARY_LABELS.get(language, {}))
        for candidate in (default_entry, override_entry):
            candidate_labels = candidate.get("labels") if isinstance(candidate, dict) else {}
            if isinstance(candidate_labels, dict):
                for key, value in candidate_labels.items():
                    value_str = str(value).strip()
                    if value_str:
                        labels[key] = value_str

        fallback_summary = str(default_entry.get("summary") or "").strip()
        summary_text = str(summary_entries.get(language, "")).strip()
        if not summary_text and fallback_summary:
            summary_text = fallback_summary
        elif (
            summary_source_lang
            and language != summary_source_lang
            and summary_text == summary_source_text
            and fallback_summary
            and fallback_summary != summary_source_text
        ):
            summary_text = fallback_summary

        fallback_conditions = str(default_entry.get("conditions") or "").strip()
        conditions_text = str(conditions_entries.get(language, "")).strip()
        if not conditions_text and fallback_conditions:
            conditions_text = fallback_conditions
        elif (
            conditions_source_lang
            and language != conditions_source_lang
            and conditions_text == conditions_source_text
            and fallback_conditions
            and fallback_conditions != conditions_source_text
        ):
            conditions_text = fallback_conditions

        fallback_improvements = str(default_entry.get("improvements") or "").strip()
        improvements_text = str(improvements_entries.get(language, "")).strip()
        if not improvements_text and fallback_improvements:
            improvements_text = fallback_improvements
        elif (
            improvements_source_lang
            and language != improvements_source_lang
            and improvements_text == improvements_source_text
            and fallback_improvements
            and fallback_improvements != improvements_source_text
        ):
            improvements_text = fallback_improvements

        merged[language] = {
            "summary": summary_text,
            "conditions": conditions_text,
            "improvements": improvements_text,
            "labels": labels,
        }

    return merged


def _ensure_multilingual_entries(
    values: dict[str, str], *, translator=None
) -> dict[str, str]:
    normalised: dict[str, str] = {}
    for language, text in values.items():
        language_key = str(language).strip().lower()
        cleaned = str(text or "").strip()
        if language_key and cleaned:
            normalised[language_key] = cleaned

    if not normalised:
        return {}

    required_languages = ("tr", "en", "de")
    missing = [lang for lang in required_languages if not normalised.get(lang)]
    if not missing:
        return normalised

    source_language = None
    for candidate in required_languages:
        if normalised.get(candidate):
            source_language = candidate
            break

    if not source_language:
        sample_text = next(iter(normalised.values()), "")
        detected_language = _detect_language(sample_text)
        if detected_language:
            source_language = detected_language
        else:
            source_language = next(iter(normalised.keys()), "en")

    source_text = normalised.get(source_language) or next(iter(normalised.values()))

    translations: dict[str, str] = {}
    if translator and source_text:
        try:
            translations = translator.translate_texts(
                source_text,
                source_language=source_language,
                target_languages=missing,
            )
        except Exception as exc:  # pragma: no cover - yalnızca tanılama
            print(f"[routes] Çeviri isteği başarısız: {exc}")
            translations = {}

    for language in missing:
        translated = (translations.get(language) or "").strip() if translations else ""
        if not translated and source_text:
            translated = fallback_translate_text(
                source_text, source_language=source_language, target_language=language
            )
        if not translated:
            translated = source_text
        normalised[language] = translated

    return normalised


_LANGUAGE_DIACRITIC_HINTS = {
    "tr": "çğıöşüâîûı",
    "de": "äöüß",
}

_LANGUAGE_KEYWORD_HINTS = {
    "tr": (
        " koşul",
        " değerlendirme",
        " uzman",
        " rapor",
        " başar",
        " ölçüm",
        " cihaz",
        " sonuç",
    ),
    "de": (
        " der ",
        " die ",
        " und ",
        " wurde ",
        " mit ",
        " kamer",
        " aufzeich",
        "prüfung",
        " messung",
        " gerät",
        " fehler",
        " erfolg",
    ),
    "en": (
        " the ",
        " and ",
        " with ",
        " recorded",
        " camera",
        " failure",
        " success",
        " analysis",
        " conditions",
        " results",
        " notes",
        " note ",
    ),
}


def _detect_language(text: str) -> str | None:
    if not text:
        return None

    lowered = text.lower()
    normalized = re.sub(r"[^a-z0-9äöüßçğıöşüâîûı]+", " ", lowered).strip()
    padded = f" {normalized} " if normalized else ""
    scores: dict[str, int] = {"tr": 0, "en": 0, "de": 0}

    for language, characters in _LANGUAGE_DIACRITIC_HINTS.items():
        diacritic_score = sum(lowered.count(char) for char in characters)
        if diacritic_score:
            scores[language] += diacritic_score * 3

    for language, keywords in _LANGUAGE_KEYWORD_HINTS.items():
        for keyword in keywords:
            target = keyword.strip()
            if not target:
                continue

            if keyword.startswith(" ") or keyword.endswith(" "):
                haystack = padded
                needle = f" {target} "
                if haystack and needle in haystack:
                    scores[language] += 2 if len(target) > 3 else 1
            else:
                if target in normalized:
                    scores[language] += 2 if len(target) > 3 else 1

    best_language, best_score = max(scores.items(), key=lambda item: item[1])
    if best_score <= 0:
        return None

    if sum(1 for score in scores.values() if score == best_score) > 1:
        return None

    return best_language


def _wrap_multilingual_text(text: str) -> dict[str, str]:
    cleaned = (text or "").strip()
    if not cleaned:
        return {}
    detected_language = _detect_language(cleaned)
    if detected_language:
        return {detected_language: cleaned}
    return {"en": cleaned}


def _normalize_structured_section_value(value: object) -> dict[str, str]:
    if isinstance(value, dict):
        normalized: dict[str, str] = {}
        for language, text in value.items():
            language_key = str(language).strip().lower()
            cleaned = str(text or "").strip()
            if language_key and cleaned:
                normalized[language_key] = cleaned
        return normalized

    if isinstance(value, list):
        joined = " ".join(str(item).strip() for item in value if str(item).strip())
        return _wrap_multilingual_text(joined)

    if value is None:
        return {}

    return _wrap_multilingual_text(str(value))


def _merge_structured_sections(
    fallback: dict, overrides: dict | None, *, translator=None
) -> dict:
    overrides = overrides or {}
    if not isinstance(overrides, dict):
        overrides = {}

    merged: dict[str, dict[str, str]] = {}
    for key in ("graphs", "conditions", "results", "comments"):
        base = _normalize_structured_section_value(fallback.get(key))
        override_value = _normalize_structured_section_value(overrides.get(key))
        combined: dict[str, str] = {}
        combined.update(base)
        combined.update(override_value)
        combined = {
            str(language).strip().lower(): str(text or "").strip()
            for language, text in combined.items()
            if str(language).strip() and str(text or "").strip()
        }
        if combined:
            merged[key] = _ensure_multilingual_entries(combined, translator=translator)
    return merged


def _merge_highlights(fallback: list[str], overrides: list[str] | None) -> list[str]:
    base = [item for item in fallback if item]
    if not isinstance(overrides, list):
        return base

    for item in overrides:
        text = str(item).strip()
        if text and text not in base:
            base.append(text)
    return base[:5]


def _split_into_sentences(text: str) -> list[str]:
    if not text:
        return []
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [sentence.strip() for sentence in sentences if sentence and sentence.strip()]


def _extract_keyword_sentences(text: str, keywords: tuple[str, ...], limit: int = 3) -> str:
    sentences = _split_into_sentences(text)
    matches: list[str] = []
    lowered = [keyword.lower() for keyword in keywords]
    for sentence in sentences:
        sentence_lower = sentence.lower()
        if any(keyword in sentence_lower for keyword in lowered):
            matches.append(sentence)
        if len(matches) >= limit:
            break
    return " ".join(matches)


def _build_structured_sections_from_text(
    text: str,
    total_tests: int,
    passed_tests: int,
    failed_tests: int,
    failure_details: list[dict],
    report_type_label: str,
) -> dict:
    graphs = _extract_keyword_sentences(
        text,
        ("graph", "grafik", "figure", "chart", "spektrum", "spectrum", "plot"),
    )
    conditions = _extract_keyword_sentences(
        text,
        ("condition", "koşul", "ambient", "environment", "temperature", "setup", "montaj"),
    )
    comments = _extract_keyword_sentences(
        text,
        ("comment", "yorum", "assessment", "değerl", "note", "gözlem"),
    )

    if graphs:
        graphs_value = _wrap_multilingual_text(graphs)
    else:
        graphs_value = {
            "tr": (
                "Rapor metninde grafiklere dair belirgin bir açıklama bulunamadı; PDF içeriği manuel olarak incelenmeli."
            ),
            "en": (
                "No specific chart description was found in the report; the PDF should be reviewed manually."
            ),
            "de": (
                "Im Berichtstext wurde keine eindeutige Beschreibung der Grafiken gefunden; bitte das PDF manuell prüfen."
            ),
        }

    if conditions:
        conditions_value = _wrap_multilingual_text(conditions)
    else:
        conditions_value = {
            "tr": (
                "Test koşulları bölümü metinde sınırlı yer alıyor. {report_type} için standart prosedürler esas alınmalıdır."
            ).format(report_type=report_type_label),
            "en": (
                "The section describing the test conditions is limited in the text. Standard procedures for {report_type} should be followed."
            ).format(report_type=report_type_label),
            "de": (
                "Der Abschnitt zu den Testbedingungen ist im Text nur begrenzt vorhanden. Es sollten die Standardverfahren für {report_type} beachtet werden."
            ).format(report_type=report_type_label),
        }
    success_rate = (passed_tests / total_tests * 100.0) if total_tests else 0.0
    results_tr = (
        f"Toplam {total_tests} testin {passed_tests}'i başarılı, {failed_tests}'i başarısız. "
        f"Başarı oranı %{success_rate:.1f}."
    )
    results_en = (
        f"{total_tests} tests in total: {passed_tests} passed, {failed_tests} failed. "
        f"Success rate {success_rate:.1f}%."
    )
    results_de = (
        f"Insgesamt {total_tests} Tests: {passed_tests} bestanden, {failed_tests} nicht bestanden. "
        f"Erfolgsquote {success_rate:.1f}%."
    )
    if failure_details:
        first_failure = failure_details[0]
        failure_reason = first_failure.get("failure_reason") or first_failure.get("error_message") or ""
        if failure_reason:
            highlight = first_failure.get("test_name", "Bilinmeyen Test")
            results_tr += f" Öne çıkan başarısızlık: {highlight} - {failure_reason}."
            results_en += f" Highlighted failure: {highlight} - {failure_reason}."
            results_de += f" Hervorgehobener Fehler: {highlight} - {failure_reason}."

    if comments:
        comments_value = _wrap_multilingual_text(comments)
    else:
        comments_value = {
            "tr": "Rapor genelinde ek yorum veya uzman görüşü bulunamadı; değerlendiricinin notları sınırlı.",
            "en": "No additional comments or expert opinions were found in the report; reviewer notes are limited.",
            "de": "Im Bericht wurden keine zusätzlichen Kommentare oder Expertenmeinungen gefunden; die Gutachternotizen sind begrenzt.",
        }

    return {
        "graphs": graphs_value,
        "conditions": conditions_value,
        "results": {"tr": results_tr, "en": results_en, "de": results_de},
        "comments": comments_value,
    }


def _build_highlights_from_data(
    total_tests: int,
    passed_tests: int,
    failed_tests: int,
    failure_details: list[dict],
    report_type_label: str,
) -> list[str]:
    highlights = [
        f"{report_type_label} kapsamında {total_tests} test incelendi.",
        f"Başarı/başarısızlık dağılımı: {passed_tests} PASS / {failed_tests} FAIL.",
    ]
    for failure in failure_details[:3]:
        reason = failure.get("failure_reason") or failure.get("error_message") or ""
        if reason:
            highlights.append(
                f"{failure.get('test_name', 'Bilinmeyen Test')}: {reason}"
            )
    return highlights


def _normalize_test_name_for_key(name: str | None) -> str:
    return re.sub(r"\s+", " ", (name or "").strip()).lower()


def _compose_result_detail(result: dict | None) -> str:
    if not result:
        return ""
    for key in ("failure_reason", "error_message", "suggested_fix"):
        value = (result.get(key) or "").strip()
        if value:
            return value
    return ""


def _collect_test_differences(
    first_results: list[dict],
    second_results: list[dict],
) -> list[dict]:
    first_map = {
        _normalize_test_name_for_key(result.get("test_name")): result for result in first_results
    }
    second_map = {
        _normalize_test_name_for_key(result.get("test_name")): result for result in second_results
    }

    differences: list[dict] = []
    all_keys = set(first_map) | set(second_map)
    for key in sorted(all_keys):
        first_result = first_map.get(key)
        second_result = second_map.get(key)
        first_status = (first_result.get("status") if first_result else "MISSING") or "MISSING"
        second_status = (second_result.get("status") if second_result else "MISSING") or "MISSING"

        if first_status == second_status and first_status != "MISSING":
            continue

        differences.append(
            {
                "test_name": first_result.get("test_name")
                if first_result and first_result.get("test_name")
                else (second_result.get("test_name") if second_result else "Bilinmeyen Test"),
                "first_status": first_status.upper(),
                "second_status": second_status.upper(),
                "first_detail": _compose_result_detail(first_result),
                "second_detail": _compose_result_detail(second_result),
            }
        )

    return differences


_STATUS_LABELS = {
    "tr": {"PASS": "test başarılı", "FAIL": "test başarısız", "MISSING": "raporda yer almıyor"},
    "en": {"PASS": "test passed", "FAIL": "test failed", "MISSING": "not present"},
    "de": {"PASS": "Test bestanden", "FAIL": "Test nicht bestanden", "MISSING": "nicht enthalten"},
}


def _format_difference_sentence(language: str, difference: dict) -> str:
    labels = _STATUS_LABELS.get(language, _STATUS_LABELS["tr"])
    test_name = difference.get("test_name") or "Test"
    first_status = labels.get(difference.get("first_status", "").upper(), labels["MISSING"])
    second_status = labels.get(difference.get("second_status", "").upper(), labels["MISSING"])
    first_detail = difference.get("first_detail") or ""
    second_detail = difference.get("second_detail") or ""

    first_sentence = first_status
    if first_detail:
        first_sentence += f" ({first_detail})"
    second_sentence = second_status
    if second_detail:
        second_sentence += f" ({second_detail})"

    if language == "en":
        template = (
            f"In the {test_name} test, the first report is {first_sentence}, while the second report is {second_sentence}."
        )
    elif language == "de":
        template = (
            f"Beim Test {test_name} ist der erste Bericht {first_sentence}, der zweite Bericht hingegen {second_sentence}."
        )
    else:
        template = (
            f"{test_name} testinde ilk rapor {first_sentence}, ikinci rapor ise {second_sentence}."
        )

    return template


def _build_localized_comparison_summary(
    first_report_label: str,
    second_report_label: str,
    differences: list[dict],
) -> dict:
    summaries = {}
    difference_count = len(differences)

    for language in ("tr", "en", "de"):
        labels = dict(COMPARISON_LABELS.get(language, {}))

        if difference_count == 0:
            overview = COMPARISON_ZERO_OVERVIEW.get(language, "")
            sentences: list[str] = []
        else:
            sentences = [_format_difference_sentence(language, diff) for diff in differences]
            if language == "en":
                overview = (
                    f"{difference_count} test differs between {first_report_label} and {second_report_label}."
                )
            elif language == "de":
                overview = (
                    f"Zwischen {first_report_label} und {second_report_label} unterscheiden sich {difference_count} Tests."
                )
            else:
                overview = (
                    f"{first_report_label} ile {second_report_label} arasında {difference_count} test sonucunda farklılık var."
                )

        entry = {"overview": overview, "details": sentences, "labels": labels}
        if not sentences:
            entry["empty_details"] = COMPARISON_EMPTY_DETAILS.get(language, "")

        summaries[language] = entry

    return summaries


def _compare_kielt_page2_metadata(first_pdf_path: Path, second_pdf_path: Path) -> dict:
    """Compare Page 2 metadata from two Kielt reports."""
    try:
        from backend.kielt_parser import parse_page_2_metadata
    except ImportError:
        try:
            from kielt_parser import parse_page_2_metadata
        except ImportError:
            logger.warning("kielt_parser not available for metadata comparison")
            return {"error": "kielt_parser module not found"}

    try:
        first_metadata = parse_page_2_metadata(first_pdf_path)
        second_metadata = parse_page_2_metadata(second_pdf_path)

        if "error" in first_metadata or "error" in second_metadata:
            return {"error": "Could not parse Page 2 metadata"}

        # Compare simple fields
        simple_fields_comparison = {}
        for field in ["auftraggeber", "anwesende", "versuchsbedingungen", "examiner"]:
            first_val = first_metadata.get(field, "")
            second_val = second_metadata.get(field, "")
            simple_fields_comparison[field] = {
                "first": first_val,
                "second": second_val,
                "identical": first_val == second_val
            }

        # Compare Prüfling (test object)
        first_pruefling = first_metadata.get("pruefling", {})
        second_pruefling = second_metadata.get("pruefling", {})
        pruefling_comparison = {}

        for field in ["bezeichnung", "hersteller", "typ"]:
            first_val = first_pruefling.get(field, "")
            second_val = second_pruefling.get(field, "")
            pruefling_comparison[field] = {
                "first": first_val,
                "second": second_val,
                "identical": first_val == second_val
            }

        # Compare mounting sections
        for mount_key in ["hinten_montiert", "vorne_montiert"]:
            first_mount = first_pruefling.get(mount_key, {})
            second_mount = second_pruefling.get(mount_key, {})
            mount_comparison = {}

            all_keys = set(first_mount.keys()) | set(second_mount.keys())
            for key in all_keys:
                first_val = first_mount.get(key, "")
                second_val = second_mount.get(key, "")
                mount_comparison[key] = {
                    "first": first_val,
                    "second": second_val,
                    "identical": first_val == second_val
                }

            pruefling_comparison[mount_key] = mount_comparison

        # Compare Lehnen-Winkel table (most critical!)
        first_angles = first_metadata.get("lehnen_winkel_table", {})
        second_angles = second_metadata.get("lehnen_winkel_table", {})

        angle_comparison = {}
        for row in ["vorher", "nachher"]:
            first_row = first_angles.get(row, {})
            second_row = second_angles.get(row, {})

            row_comparison = {}
            for position in ["hinten_links", "hinten_rechts", "vorne_links", "vorne_rechts"]:
                first_val = first_row.get(position)
                second_val = second_row.get(position)

                identical = False
                if first_val is not None and second_val is not None:
                    identical = abs(first_val - second_val) < 0.1  # 0.1 degree tolerance
                elif first_val is None and second_val is None:
                    identical = True

                row_comparison[position] = {
                    "first": first_val,
                    "second": second_val,
                    "identical": identical,
                    "difference": abs(first_val - second_val) if (first_val is not None and second_val is not None) else None
                }

            angle_comparison[row] = row_comparison

        # Compare Prüfergebnis
        first_ergebnis = first_metadata.get("pruefergebnis", {})
        second_ergebnis = second_metadata.get("pruefergebnis", {})

        ergebnis_comparison = {}
        for field in ["ergebnis", "freigabe", "pruefer", "datum"]:
            first_val = first_ergebnis.get(field, "")
            second_val = second_ergebnis.get(field, "")
            ergebnis_comparison[field] = {
                "first": first_val,
                "second": second_val,
                "identical": first_val == second_val
            }

        # Dummy prüfung details
        first_dummy = first_ergebnis.get("dummypruefung", {})
        second_dummy = second_ergebnis.get("dummypruefung", {})
        dummy_comparison = {}

        for field in ["dummy_checks", "rueckhaltung", "kanten", "bemerkung"]:
            first_val = first_dummy.get(field, "")
            second_val = second_dummy.get(field, "")
            dummy_comparison[field] = {
                "first": first_val,
                "second": second_val,
                "identical": first_val == second_val
            }

        ergebnis_comparison["dummypruefung"] = dummy_comparison

        # Calculate overall statistics
        total_fields = 0
        identical_fields = 0
        critical_differences = 0

        # Count simple fields
        for field_data in simple_fields_comparison.values():
            total_fields += 1
            if field_data["identical"]:
                identical_fields += 1

        # Count Prüfling fields
        for field, data in pruefling_comparison.items():
            if field in ["hinten_montiert", "vorne_montiert"]:
                for subfield_data in data.values():
                    total_fields += 1
                    if subfield_data["identical"]:
                        identical_fields += 1
            else:
                total_fields += 1
                if data["identical"]:
                    identical_fields += 1

        # Count angle differences (critical!)
        for row_data in angle_comparison.values():
            for position_data in row_data.values():
                total_fields += 1
                if position_data["identical"]:
                    identical_fields += 1
                else:
                    critical_differences += 1

        # Count Prüfergebnis fields
        for field, data in ergebnis_comparison.items():
            if field == "dummypruefung":
                for subfield_data in data.values():
                    total_fields += 1
                    if subfield_data["identical"]:
                        identical_fields += 1
            else:
                total_fields += 1
                if data["identical"]:
                    identical_fields += 1

        metadata_similarity = (identical_fields / total_fields * 100.0) if total_fields > 0 else 0.0

        return {
            "metadata_similarity": round(metadata_similarity, 1),
            "total_fields_compared": total_fields,
            "identical_fields": identical_fields,
            "different_fields": total_fields - identical_fields,
            "critical_differences": critical_differences,
            "simple_fields": simple_fields_comparison,
            "pruefling": pruefling_comparison,
            "lehnen_winkel": angle_comparison,
            "pruefergebnis": ergebnis_comparison
        }

    except Exception as exc:
        logger.exception("Failed to compare Kielt Page 2 metadata: %s", exc)
        return {"error": str(exc)}


def _build_multilingual_summary(
    engine_label: str,
    filename: str,
    report_type_label: str,
    total_tests: int,
    passed_tests: int,
    failed_tests: int,
    failure_details,
):
    total = int(total_tests or 0)
    passed = int(passed_tests or 0)
    failed = int(failed_tests or 0)
    success_rate = (passed / total * 100.0) if total else 0.0
    alignment_key = _derive_alignment_key(total, passed, failed)

    summaries = {}
    for language, config in LANGUAGE_TEMPLATES.items():
        labels = dict(config.get("labels", {}))
        if total == 0:
            summary_text = config["no_tests"].format(
                engine=engine_label,
                filename=filename,
                report_type=report_type_label,
            )
            conditions_text = config["no_tests_conditions"]
            improvements_text = config["no_tests_improvements"]
        else:
            summary_text = config["summary"].format(
                engine=engine_label,
                filename=filename,
                report_type=report_type_label,
                total=total,
                passed=passed,
                failed=failed,
                success_rate=f"{success_rate:.1f}",
            )
            alignment_word = config["alignment_words"].get(
                alignment_key, config["alignment_words"]["unknown"]
            )
            conditions_text = config["conditions"].format(alignment=alignment_word)

            if failure_details:
                improvement_lines = []
                for detail in failure_details:
                    test_name = detail.get("test_name") or config["unknown_test_name"]
                    suggested_fix = (detail.get("suggested_fix") or "").strip()
                    failure_reason = (detail.get("failure_reason") or "").strip()
                    if not failure_reason:
                        failure_reason = config["default_reason"]
                    if suggested_fix:
                        improvement_lines.append(
                            config["failure_with_fix"].format(
                                test=test_name,
                                fix=suggested_fix,
                                reason=failure_reason,
                            )
                        )
                    else:
                        improvement_lines.append(
                            config["failure_without_fix"].format(
                                test=test_name,
                                reason=failure_reason,
                            )
                        )
                improvements_text = (
                    config["improvements_intro"] + " " + " ".join(improvement_lines)
                )
            else:
                improvements_text = config["improvements_success"]

        summaries[language] = {
            "summary": summary_text,
            "conditions": conditions_text,
            "improvements": improvements_text,
            "labels": labels,
        }

    return summaries


@bp.route('/upload', methods=['POST'])
def upload_report():
    """PDF yükle ve analiz et"""
    import logging
    logger = logging.getLogger(__name__)

    logger.info("="*70)
    logger.info("UPLOAD ENDPOINT CALLED")
    logger.info("="*70)
    logger.info(f"Request method: {request.method}")
    logger.info(f"Request files: {request.files}")
    logger.info(f"Request form: {request.form}")

    # Dosya kontrolü
    if 'file' not in request.files:
        logger.error("'file' key not found in request.files")
        logger.error(f"Available keys: {list(request.files.keys())}")
        return jsonify({
            'error': 'Dosya bulunamadı',
            'detail': 'Request içinde "file" key\'i yok'
        }), 400

    file = request.files['file']

    # Dosya adı kontrolü
    if file.filename == '':
        logger.error("Empty filename")
        return jsonify({'error': 'Dosya seçilmedi'}), 400

    logger.info(f"Dosya alındı: {file.filename}")

    # PDF kontrolü
    if not file.filename.lower().endswith('.pdf'):
        logger.error(f"Invalid file type: {file.filename}")
        return jsonify({'error': 'Sadece PDF dosyaları desteklenir'}), 400

    engine_key, engine_label = _normalise_engine(request.form.get("engine"))

    try:
        # Dosyayı kaydet
        filename = secure_filename(file.filename)

        if report_exists_with_filename(filename):
            logger.warning("Duplicate upload attempt detected for %s", filename)
            return jsonify({"error": "Bu rapor daha önce arşivlendi."}), 409

        # Uploads klasörü yoksa oluştur
        uploads_dir = 'uploads'
        if not os.path.exists(uploads_dir):
            os.makedirs(uploads_dir)
            logger.info(f"Uploads klasörü oluşturuldu: {uploads_dir}")

        # Benzersiz dosya adı
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_filename = f"{timestamp}_{filename}"
        pdf_path = os.path.join(uploads_dir, unique_filename)

        file.save(pdf_path)
        logger.info(f"Dosya kaydedildi: {pdf_path}")

        # Analiz başlat
        logger.info("PDF analizi başlatılıyor...")
        with ai_analyzer.temporary_provider(engine_key):
            analysis_result = analyze_pdf_comprehensive(pdf_path)

        logger.info("Analiz tamamlandı, database'e kaydediliyor...")

        report_type_key = str(analysis_result.get("report_type", "unknown") or "unknown").strip().lower()
        report_type_label = (
            analysis_result.get("report_type_label")
            or _resolve_report_type_label(report_type_key)
        )

        # Database'e kaydet
        report_id = insert_report(
            filename=filename,
            pdf_path=pdf_path,
            test_type=report_type_key,
            stored_filename=unique_filename,
        )

        # İstatistikleri kaydet
        update_report_stats(
            report_id,
            analysis_result['basic_stats']['total_tests'],
            analysis_result['basic_stats']['passed'],
            analysis_result['basic_stats']['failed']
        )

        # Kapsamlı analizi kaydet
        update_report_comprehensive_analysis(
            report_id,
            analysis_result['comprehensive_analysis'],
            analysis_result.get('structured_data'),
            analysis_result.get('tables')
        )

        # Test sonuçlarını kaydet
        for test in analysis_result['basic_stats']['tests']:
            insert_test_result(
                report_id,
                test['name'],
                test['status'],
                test.get('error_message'),
                test.get('failure_reason'),
                test.get('suggested_fix'),
                test.get('ai_provider', 'rule-based')
            )

        logger.info(f"Rapor kaydedildi: ID={report_id}")
        logger.info("="*70)

        return jsonify({
            'success': True,
            'report_id': report_id,
            'filename': filename,
            'basic_stats': analysis_result['basic_stats'],
            'analysis_engine': engine_label,
            'analysis_engine_key': engine_key,
            'report_type': report_type_key,
            'report_type_label': report_type_label,
            'message': 'PDF başarıyla yüklendi ve analiz edildi'
        }), 200

    except Exception as e:
        logger.error(f"Upload hatası: {e}", exc_info=True)
        return jsonify({
            'error': 'Yükleme başarısız oldu',
            'detail': str(e)
        }), 500


@reports_bp.route("/reports", methods=["GET"])
def list_reports():
    sort_by = request.args.get("sortBy", "date")
    order = request.args.get("order", "desc")
    reports = database.get_all_reports(sort_by=sort_by, order=order)
    for report in reports:
        report["test_type_label"] = _resolve_report_type_label(report.get("test_type"))
    return jsonify({"reports": reports})


@reports_bp.route("/reports/<int:report_id>", methods=["GET"])
def get_report(report_id: int):
    """Rapor detayını getir"""

    import logging

    logger = logging.getLogger(__name__)

    try:
        report = database.get_report_by_id(report_id)

        if not report:
            return _json_error("Report not found.", 404)

        tests = database.get_test_results(report_id) or []

        detailed_analysis = {
            "test_conditions": report.get("test_conditions_summary", ""),
            "graphs": report.get("graphs_description", ""),
            "results": report.get("detailed_results", ""),
            "improvements": report.get("improvement_suggestions", ""),
        }

        logger.info("Rapor %s getiriliyor:", report_id)
        logger.info("  Test conditions: %s karakter", len(detailed_analysis["test_conditions"]))
        logger.info("  Graphs: %s karakter", len(detailed_analysis["graphs"]))

        response = {
            "report": {
                "id": report.get("id"),
                "filename": report.get("filename"),
                "upload_date": report.get("upload_date"),
                "total_tests": report.get("total_tests", 0),
                "passed_tests": report.get("passed_tests", 0),
                "failed_tests": report.get("failed_tests", 0),
                "tests": tests,
            },
            "detailed_analysis": detailed_analysis,
        }

        return jsonify(response)

    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Rapor getirme hatası: %s", exc, exc_info=True)
        return _json_error(str(exc), 500)


@reports_bp.route("/reports/<int:report_id>/detailed", methods=["GET"])
def get_detailed_report(report_id: int):
    """Return the comprehensive AI-backed analysis for a report."""

    report = database.get_report_by_id(report_id)
    if not report:
        return _json_error("Report not found.", 404)

    detailed_analysis = {
        "test_conditions": (report.get("test_conditions_summary") or ""),
        "graphs": (report.get("graphs_description") or ""),
        "results": (report.get("detailed_results") or ""),
        "improvements": (report.get("improvement_suggestions") or ""),
        "analysis_language": report.get("analysis_language", "tr"),
    }

    return jsonify(
        {
            "report_id": report_id,
            "filename": report.get("filename"),
            "upload_date": report.get("upload_date"),
            "basic_stats": {
                "total": report.get("total_tests", 0),
                "passed": report.get("passed_tests", 0),
                "failed": report.get("failed_tests", 0),
            },
            "detailed_analysis": detailed_analysis,
            "structured_data": report.get("structured_data"),
            "table_count": report.get("table_count", 0),
        }
    )


@reports_bp.route("/reports/<int:report_id>/download", methods=["GET"])
def download_report_file(report_id: int):
    report = database.get_report_by_id(report_id)
    if not report:
        return _json_error("Report not found.", 404)

    pdf_path = Path(report.get("pdf_path") or "")
    if not pdf_path.exists():
        return _json_error("PDF file is not available on the server.", 404)

    return send_file(
        pdf_path,
        mimetype="application/pdf",
        as_attachment=False,
        download_name=report.get("filename") or pdf_path.name,
    )


@reports_bp.route("/reports/compare", methods=["POST"])
def compare_reports():
    payload = request.get_json(silent=True) or {}
    report_ids = payload.get("report_ids")

    if not isinstance(report_ids, list):
        return _json_error("Karşılaştırma için rapor kimliklerini içeren bir liste gönderin.", 400)

    if len(report_ids) != 2:
        return _json_error("Karşılaştırma işlemi için tam olarak iki rapor seçmelisiniz.", 400)

    try:
        first_id, second_id = (int(report_ids[0]), int(report_ids[1]))
    except (TypeError, ValueError):
        return _json_error("Geçersiz rapor kimliği gönderildi.", 400)

    if first_id == second_id:
        return _json_error("Karşılaştırma için farklı iki rapor seçmelisiniz.", 400)

    first_report = database.get_report_by_id(first_id)
    second_report = database.get_report_by_id(second_id)

    if not first_report or not second_report:
        return _json_error("Seçilen raporlardan biri bulunamadı.", 404)

    first_path = Path(first_report.get("pdf_path") or "")
    second_path = Path(second_report.get("pdf_path") or "")

    if not first_path.exists() or not second_path.exists():
        return _json_error("Karşılaştırma için PDF dosyalarından biri bulunamadı.", 404)

    try:
        first_extraction = extract_text_from_pdf(first_path)
        second_extraction = extract_text_from_pdf(second_path)
        first_text = (
            first_extraction.get("structured_text")
            or first_extraction.get("text")
            or ""
        )
        second_text = (
            second_extraction.get("structured_text")
            or second_extraction.get("text")
            or ""
        )
    except FileNotFoundError:
        return _json_error("Karşılaştırma için PDF dosyalarından biri bulunamadı.", 404)
    except Exception as exc:  # pragma: no cover - defensive
        return _json_error(f"PDF karşılaştırması yapılamadı: {exc}", 500)

    first_results = database.get_test_results(first_id)
    second_results = database.get_test_results(second_id)
    structured_differences = _collect_test_differences(first_results, second_results)
    localized_difference_summary = _build_localized_comparison_summary(
        first_report.get("filename") or f"report-{first_id}.pdf",
        second_report.get("filename") or f"report-{second_id}.pdf",
        structured_differences,
    )

    similarity_ratio = difflib.SequenceMatcher(None, first_text, second_text).ratio() * 100.0

    def _normalise_lines(raw_text: str):
        return [line.strip() for line in raw_text.splitlines() if line and line.strip()]

    first_lines = _normalise_lines(first_text)
    second_lines = _normalise_lines(second_text)

    def _collect_unique(source_lines, target_lines):
        target_set = set(target_lines)
        uniques = []
        seen = set()
        for line in source_lines:
            if line in target_set or line in seen or len(line) < 4:
                continue
            uniques.append(line)
            seen.add(line)
            if len(uniques) >= 5:
                break
        return uniques

    unique_first = _collect_unique(first_lines, second_lines)
    unique_second = _collect_unique(second_lines, first_lines)

    diff_lines = list(
        difflib.unified_diff(
            first_text.splitlines(),
            second_text.splitlines(),
            fromfile=first_report.get("filename") or f"report-{first_id}.pdf",
            tofile=second_report.get("filename") or f"report-{second_id}.pdf",
            lineterm="",
        )
    )

    max_diff_lines = 120
    if len(diff_lines) > max_diff_lines:
        remaining = len(diff_lines) - max_diff_lines
        diff_lines = diff_lines[:max_diff_lines]
        diff_lines.append(f"... ({remaining} satır daha)")

    if similarity_ratio >= 85:
        verdict = "Raporlar büyük ölçüde aynı içerikte."
    elif similarity_ratio >= 60:
        verdict = "Raporlar benzer ancak dikkate değer farklılıklar mevcut."
    else:
        verdict = "Raporlar arasında belirgin içerik farkı var."

    if structured_differences:
        verdict += f" Karşılaştırmada {len(structured_differences)} test sonucunda ayrışma bulundu."
    else:
        verdict += " Test sonuçları arasında fark tespit edilmedi."

    response_payload = {
        "summary": (
            f"{first_report.get('filename')} ile {second_report.get('filename')} arasındaki benzerlik oranı "
            f"%{similarity_ratio:.1f}. {verdict}"
        ),
        "similarity": round(similarity_ratio, 2),
        "first_report": {
            "id": first_id,
            "filename": first_report.get("filename"),
            "upload_date": first_report.get("upload_date"),
            "test_type": _resolve_report_type_label(first_report.get("test_type")),
        },
        "second_report": {
            "id": second_id,
            "filename": second_report.get("filename"),
            "upload_date": second_report.get("upload_date"),
            "test_type": _resolve_report_type_label(second_report.get("test_type")),
        },
        "difference_highlights": diff_lines,
        "unique_to_first": unique_first,
        "unique_to_second": unique_second,
        "test_differences": structured_differences,
        "difference_summary": localized_difference_summary,
    }

    # Check if both reports are Kielt R80 reports
    first_test_type = first_report.get("test_type", "").lower()
    second_test_type = second_report.get("test_type", "").lower()

    if first_test_type == "r80" and second_test_type == "r80":
        page2_comparison = _compare_kielt_page2_metadata(first_path, second_path)
        response_payload["page_2_comparison"] = page2_comparison

    return jsonify(response_payload)


@reports_bp.route("/reports/<int:report_id>/tables", methods=["GET"])
def get_report_tables(report_id: int):
    report = database.get_report_by_id(report_id)
    if not report:
        return _json_error("Report not found.", 404)

    pdf_path = Path(report.get("pdf_path") or "")
    if not pdf_path.exists():
        return _json_error("PDF file is not available on the server.", 404)

    try:
        extraction = extract_text_from_pdf(pdf_path)
    except Exception as exc:  # pragma: no cover - defensive
        return _json_error(f"Tablo verileri alınamadı: {exc}", 500)

    tables = extraction.get("tables") or []

    return jsonify(
        {
            "report_id": report_id,
            "table_count": len(tables),
            "tables": tables,
        }
    )


@reports_bp.route("/reports/<int:report_id>/failures", methods=["GET"])
def get_failures(report_id: int):
    report = database.get_report_by_id(report_id)
    if not report:
        return _json_error("Report not found.", 404)

    failures = database.get_failed_tests(report_id)
    return jsonify({"report": report, "failures": failures})


@reports_bp.route("/reports/<int:report_id>", methods=["DELETE"])
def delete_report(report_id: int):
    pdf_path = database.delete_report(report_id)
    if pdf_path is None:
        return _json_error("Report not found.", 404)

    try:
        Path(pdf_path).unlink(missing_ok=True)
    except OSError:
        pass

    return jsonify({"message": "Report deleted successfully."})


@reports_bp.route("/ai-status", methods=["GET"])
def get_ai_status():
    """AI provider durumunu döndür."""
    provider = (os.getenv("AI_PROVIDER", "none") or "none").strip().lower()
    if provider not in {"claude", "chatgpt", "both", "none"}:
        provider = "none"
    anthropic_key = (os.getenv("ANTHROPIC_API_KEY", "") or "").strip()
    openai_key = (os.getenv("OPENAI_API_KEY", "") or "").strip()

    claude_available = bool(anthropic_key)
    chatgpt_available = bool(openai_key)

    active = False
    if provider == "claude":
        active = claude_available
    elif provider == "chatgpt":
        active = chatgpt_available
    elif provider == "both":
        active = claude_available or chatgpt_available

    status = "active" if active else "inactive"

    return jsonify(
        {
            "provider": provider or "none",
            "claude_available": claude_available,
            "chatgpt_available": chatgpt_available,
            "status": status,
        }
    )


@reports_bp.route("/reset", methods=["POST"])
def reset_all_data():
    """Delete all stored reports, analyses and uploaded PDF files."""

    pdf_paths = database.clear_all_data()
    removed_files = 0

    for pdf_path in pdf_paths:
        try:
            Path(pdf_path).unlink(missing_ok=True)
            removed_files += 1
        except OSError:
            pass

    upload_folder = Path(current_app.config["UPLOAD_FOLDER"])
    if upload_folder.exists():
        for orphan in upload_folder.glob("**/*"):
            if orphan.is_file():
                try:
                    orphan.unlink(missing_ok=True)
                except OSError:
                    pass

    return jsonify(
        {
            "message": "Tüm raporlar ve test sonuçları sıfırlandı.",
            "deleted_reports": len(pdf_paths),
            "deleted_files": removed_files,
        }
    )


@reports_bp.route("/analyze-files", methods=["POST"])
def analyze_files_with_ai():
    """Analyse uploaded PDF files and return AI flavoured summaries."""

    files = request.files.getlist("files")
    if not files:
        return _json_error("Analiz için en az bir PDF dosyası gönderin.", 400)

    engine_key, engine_label = _normalise_engine(request.form.get("engine"))

    summaries = []
    processed_files = 0

    with ai_analyzer.temporary_provider(engine_key):
        for storage in files:
            if not storage or storage.filename == "":
                continue

            filename = storage.filename
            if not filename.lower().endswith(".pdf"):
                continue

            with NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                storage.save(temp_file.name)
                temp_path = Path(temp_file.name)

            try:
                extraction = extract_text_from_pdf(temp_path)
                raw_text = (
                    extraction.get("structured_text")
                    if isinstance(extraction, dict)
                    else ""
                ) or (
                    extraction.get("text")
                    if isinstance(extraction, dict)
                    else str(extraction)
                )
                raw_text = str(raw_text or "")
                parsed_results = parse_test_results(extraction)
                comprehensive_result = analyze_pdf_comprehensive(temp_path)
            except Exception as exc:  # pragma: no cover - defensive logging
                temp_path.unlink(missing_ok=True)
                return _json_error(f"PDF analizi başarısız oldu: {exc}", 500)
            finally:
                temp_path.unlink(missing_ok=True)

            inferred_report_key, inferred_report_label = infer_report_type(
                raw_text, filename
            )
            report_type_key = (
                str(comprehensive_result.get("report_type") or inferred_report_key)
                or "unknown"
            ).strip()
            report_type_key = report_type_key.lower() or "unknown"
            report_type_label = (
                comprehensive_result.get("report_type_label")
                or inferred_report_label
                or _resolve_report_type_label(report_type_key)
            )

            basic_stats = comprehensive_result.get("basic_stats") or {}
            structured_tests = basic_stats.get("tests") or []
            if structured_tests:
                parsed_results = structured_tests

            def _coerce_stat(value: object, default: int = 0) -> int:
                try:
                    return int(value)  # type: ignore[arg-type]
                except (TypeError, ValueError):
                    return default

            total_tests = _coerce_stat(
                basic_stats.get("total_tests"), len(parsed_results)
            )
            passed_tests = _coerce_stat(basic_stats.get("passed"), 0)
            failed_tests = _coerce_stat(basic_stats.get("failed"), 0)

            if total_tests == 0 and parsed_results:
                total_tests = len(parsed_results)
            if passed_tests == 0 and total_tests and not structured_tests:
                passed_tests = sum(1 for result in parsed_results if result.get("status") == "PASS")
            if failed_tests == 0 and total_tests:
                failed_tests = total_tests - passed_tests

            processed_files += 1
            alignment_key = _derive_alignment_key(total_tests, passed_tests, failed_tests)
            success_rate = (passed_tests / total_tests * 100.0) if total_tests else 0.0
            success_rate = round(success_rate, 2)

            failure_details = [
                {
                    "test_name": result.get("test_name", "Bilinmeyen Test"),
                    "failure_reason": result.get("failure_reason", ""),
                    "suggested_fix": result.get("suggested_fix", ""),
                }
                for result in parsed_results
                if result.get("status") == "FAIL"
            ]

            measurement_params = comprehensive_result.get("measurement_params")
            comprehensive_analysis = (
                comprehensive_result.get("comprehensive_analysis") or {}
            )
            measurement_analysis_payload = build_measurement_analysis(
                measurement_params,
                report_id=filename,
                test_conditions=comprehensive_analysis.get("test_conditions", ""),
            )
            measurement_summary = {
                "report_id": measurement_analysis_payload.get("report_id", filename),
                "measured_values": measurement_analysis_payload.get(
                    "measured_values", {}
                ),
                "overall_summary": measurement_analysis_payload.get(
                    "overall_summary", {}
                ),
                "test_conditions_summary": measurement_analysis_payload.get(
                    "test_conditions_summary", ""
                ),
                "data_source": measurement_analysis_payload.get("data_source"),
            }

            # Generate structured page-by-page analysis
            structured_page_analysis = None
            try:
                # Build PDF data structure for formatter
                pdf_data_for_formatter = {
                    "filename": filename,
                    "structured_data": comprehensive_result.get("structured_data", {}),
                    "comprehensive_analysis": comprehensive_analysis,
                }
                structured_page_analysis = format_kielt_report_analysis(
                    pdf_data=pdf_data_for_formatter,
                    measurement_params=measurement_params
                )
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.warning("Structured page analysis generation failed: %s", exc)

            fallback_localized = _build_multilingual_summary(
                engine_label,
                filename,
                report_type_label,
                total_tests,
                passed_tests,
                failed_tests,
                failure_details,
            )

            try:
                ai_summary_payload = ai_analyzer.generate_report_summary(
                    filename=filename,
                    report_type=report_type_label,
                    total_tests=total_tests,
                    passed_tests=passed_tests,
                    failed_tests=failed_tests,
                    raw_text=raw_text,
                    failure_details=failure_details,
                    structured_data=comprehensive_analysis,
                    fallback_data=measurement_analysis_payload,
                )
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.warning("AI özet oluşturma başarısız: %s", exc)
                ai_summary_payload = {"error": str(exc)}

            raw_ai_summary = ""
            ai_summary_mode = "structured"
            if isinstance(ai_summary_payload, dict):
                raw_ai_summary = str(
                    ai_summary_payload.get("raw_text")
                    or ai_summary_payload.get("raw")
                    or ai_summary_payload.get("_raw_response_text")
                    or ""
                ).strip()
                if ai_summary_payload.get("mode") == "plain-text" or ai_summary_payload.get("error"):
                    ai_summary_mode = "plain-text"

            localized_summaries = _merge_localized_summaries(
                fallback_localized,
                (ai_summary_payload or {}).get("localized_summaries") if ai_summary_payload else None,
                translator=ai_analyzer,
            )

            fallback_sections = _build_structured_sections_from_text(
                raw_text,
                total_tests,
                passed_tests,
                failed_tests,
                failure_details,
                report_type_label,
            )
            structured_sections = _merge_structured_sections(
                fallback_sections,
                (ai_summary_payload or {}).get("sections") if ai_summary_payload else None,
                translator=ai_analyzer,
            )

            fallback_highlights = _build_highlights_from_data(
                total_tests,
                passed_tests,
                failed_tests,
                failure_details,
                report_type_label,
            )
            analysis_highlights = _merge_highlights(
                fallback_highlights,
                (ai_summary_payload or {}).get("highlights") if ai_summary_payload else None,
            )

            base_summary = localized_summaries["tr"]["summary"]
            conditions_text = localized_summaries["tr"].get("conditions", "")
            improvements_text = localized_summaries["tr"].get("improvements", "")

            summaries.append(
                {
                    "filename": filename,
                    "total_tests": total_tests,
                    "passed_tests": passed_tests,
                    "failed_tests": failed_tests,
                    "engine": engine_label,
                    "engine_key": engine_key,
                    "summary": base_summary,
                    "condition_evaluation": conditions_text,
                    "improvement_overview": improvements_text,
                    "localized_summaries": localized_summaries,
                    "report_type": report_type_key,
                    "report_type_label": report_type_label,
                    "alignment": alignment_key,
                    "success_rate": success_rate,
                    "failures": failure_details,
                    "structured_sections": structured_sections,
                    "highlights": analysis_highlights,
                    "ai_raw_summary": raw_ai_summary,
                    "ai_summary_mode": ai_summary_mode,
                    "measurement_analysis": measurement_summary,
                    "structured_page_analysis": structured_page_analysis,
                }
            )

    if processed_files == 0:
        return _json_error("Analiz için geçerli PDF dosyası bulunamadı.", 400)

    return jsonify(
        {
            "engine": engine_label,
            "engine_key": engine_key,
            "summaries": summaries,
            "message": (
                f"{processed_files} dosya {engine_label} ile analiz edildi. "
                "Türkçe, İngilizce ve Almanca özetler hazırlandı."
            ),
        }
    )


@reports_bp.route("/analyze-archived", methods=["POST"])
def analyze_archived_reports():
    """Re-analyze archived reports by their IDs with glob pattern fallback."""

    data = request.get_json(silent=True) or {}
    report_ids = data.get("report_ids", [])

    if not report_ids or not isinstance(report_ids, list):
        return _json_error("Analiz için en az bir rapor ID'si gönderin.", 400)

    engine_key, engine_label = _normalise_engine(data.get("engine"))

    summaries = []
    processed_files = 0
    uploads_base = Path("uploads")

    with ai_analyzer.temporary_provider(engine_key):
        for report_id in report_ids:
            # Get report from database
            report = database.get_report_by_id(report_id)
            if not report:
                logger.warning(f"Report ID {report_id} not found in database")
                continue

            filename = report.get("filename", f"report-{report_id}.pdf")
            stored_filename = report.get("stored_filename")

            # Try to find the PDF file
            pdf_path = None

            # Method 1: Use stored_filename if available
            if stored_filename:
                candidate = uploads_base / stored_filename
                if candidate.exists():
                    pdf_path = candidate
                    logger.info(f"Found PDF using stored_filename: {pdf_path}")

            # Method 2: Try pdf_path from database
            if not pdf_path:
                db_pdf_path = report.get("pdf_path")
                if db_pdf_path:
                    candidate = Path(db_pdf_path)
                    if candidate.exists():
                        pdf_path = candidate
                        logger.info(f"Found PDF using pdf_path: {pdf_path}")

            # Method 3: Glob pattern fallback - find files matching *_filename pattern
            if not pdf_path:
                pattern = f"*_{filename}"
                matches = list(uploads_base.glob(pattern))
                if matches:
                    # Use the most recent match
                    pdf_path = sorted(matches, key=lambda p: p.stat().st_mtime)[-1]
                    logger.info(f"Found PDF using glob pattern: {pdf_path}")

            if not pdf_path or not pdf_path.exists():
                logger.error(f"PDF file not found for report ID {report_id}, filename: {filename}")
                continue

            try:
                extraction = extract_text_from_pdf(pdf_path)
                raw_text = (
                    extraction.get("structured_text")
                    if isinstance(extraction, dict)
                    else ""
                ) or (
                    extraction.get("text")
                    if isinstance(extraction, dict)
                    else str(extraction)
                )
                raw_text = str(raw_text or "")
                parsed_results = parse_test_results(extraction)
                comprehensive_result = analyze_pdf_comprehensive(pdf_path)
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.error(f"PDF analizi başarısız oldu (ID: {report_id}): {exc}")
                continue

            inferred_report_key, inferred_report_label = infer_report_type(
                raw_text, filename
            )
            report_type_key = (
                str(comprehensive_result.get("report_type") or inferred_report_key)
                or "unknown"
            ).strip()
            report_type_key = report_type_key.lower() or "unknown"
            report_type_label = (
                comprehensive_result.get("report_type_label")
                or inferred_report_label
                or _resolve_report_type_label(report_type_key)
            )

            basic_stats = comprehensive_result.get("basic_stats") or {}
            structured_tests = basic_stats.get("tests") or []
            if structured_tests:
                parsed_results = structured_tests

            def _coerce_stat(value: object, default: int = 0) -> int:
                try:
                    return int(value)  # type: ignore[arg-type]
                except (TypeError, ValueError):
                    return default

            total_tests = _coerce_stat(
                basic_stats.get("total_tests"), len(parsed_results)
            )
            passed_tests = _coerce_stat(basic_stats.get("passed"), 0)
            failed_tests = _coerce_stat(basic_stats.get("failed"), 0)

            if total_tests == 0 and parsed_results:
                total_tests = len(parsed_results)
            if passed_tests == 0 and total_tests and not structured_tests:
                passed_tests = sum(1 for result in parsed_results if result.get("status") == "PASS")
            if failed_tests == 0 and total_tests:
                failed_tests = total_tests - passed_tests

            processed_files += 1
            alignment_key = _derive_alignment_key(total_tests, passed_tests, failed_tests)
            success_rate = (passed_tests / total_tests * 100.0) if total_tests else 0.0
            success_rate = round(success_rate, 2)

            failure_details = [
                {
                    "test_name": result.get("test_name", "Bilinmeyen Test"),
                    "failure_reason": result.get("failure_reason", ""),
                    "suggested_fix": result.get("suggested_fix", ""),
                }
                for result in parsed_results
                if result.get("status") == "FAIL"
            ]

            measurement_params = comprehensive_result.get("measurement_params")
            comprehensive_analysis = (
                comprehensive_result.get("comprehensive_analysis") or {}
            )
            measurement_analysis_payload = build_measurement_analysis(
                measurement_params,
                report_id=filename,
                test_conditions=comprehensive_analysis.get("test_conditions", ""),
            )
            measurement_summary = {
                "report_id": measurement_analysis_payload.get("report_id", filename),
                "measured_values": measurement_analysis_payload.get(
                    "measured_values", {}
                ),
                "overall_summary": measurement_analysis_payload.get(
                    "overall_summary", {}
                ),
                "test_conditions_summary": measurement_analysis_payload.get(
                    "test_conditions_summary", ""
                ),
                "data_source": measurement_analysis_payload.get("data_source"),
            }

            # Generate structured page-by-page analysis
            structured_page_analysis = None
            try:
                pdf_data_for_formatter = {
                    "filename": filename,
                    "structured_data": comprehensive_result.get("structured_data", {}),
                    "comprehensive_analysis": comprehensive_analysis,
                }
                structured_page_analysis = format_kielt_report_analysis(
                    pdf_data=pdf_data_for_formatter,
                    measurement_params=measurement_params
                )
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.warning("Structured page analysis generation failed: %s", exc)

            fallback_localized = _build_multilingual_summary(
                engine_label,
                filename,
                report_type_label,
                total_tests,
                passed_tests,
                failed_tests,
                failure_details,
            )

            try:
                ai_summary_payload = ai_analyzer.generate_report_summary(
                    filename=filename,
                    report_type=report_type_label,
                    total_tests=total_tests,
                    passed_tests=passed_tests,
                    failed_tests=failed_tests,
                    raw_text=raw_text,
                    failure_details=failure_details,
                    structured_data=comprehensive_analysis,
                    fallback_data=measurement_analysis_payload,
                )
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.warning("AI özet oluşturma başarısız: %s", exc)
                ai_summary_payload = {"error": str(exc)}

            raw_ai_summary = ""
            ai_summary_mode = "structured"
            if isinstance(ai_summary_payload, dict):
                raw_ai_summary = str(
                    ai_summary_payload.get("raw_text")
                    or ai_summary_payload.get("raw")
                    or ai_summary_payload.get("_raw_response_text")
                    or ""
                ).strip()
                if ai_summary_payload.get("mode") == "plain-text" or ai_summary_payload.get("error"):
                    ai_summary_mode = "plain-text"

            localized_summaries = _merge_localized_summaries(
                fallback_localized,
                (ai_summary_payload or {}).get("localized_summaries") if ai_summary_payload else None,
                translator=ai_analyzer,
            )

            fallback_sections = _build_structured_sections_from_text(
                raw_text,
                total_tests,
                passed_tests,
                failed_tests,
                failure_details,
                report_type_label,
            )
            structured_sections = _merge_structured_sections(
                fallback_sections,
                (ai_summary_payload or {}).get("sections") if ai_summary_payload else None,
                translator=ai_analyzer,
            )

            fallback_highlights = _build_highlights_from_data(
                total_tests,
                passed_tests,
                failed_tests,
                failure_details,
                report_type_label,
            )
            analysis_highlights = _merge_highlights(
                fallback_highlights,
                (ai_summary_payload or {}).get("highlights") if ai_summary_payload else None,
            )

            base_summary = localized_summaries["tr"]["summary"]
            conditions_text = localized_summaries["tr"].get("conditions", "")
            improvements_text = localized_summaries["tr"].get("improvements", "")

            summaries.append(
                {
                    "filename": filename,
                    "total_tests": total_tests,
                    "passed_tests": passed_tests,
                    "failed_tests": failed_tests,
                    "engine": engine_label,
                    "engine_key": engine_key,
                    "summary": base_summary,
                    "condition_evaluation": conditions_text,
                    "improvement_overview": improvements_text,
                    "localized_summaries": localized_summaries,
                    "report_type": report_type_key,
                    "report_type_label": report_type_label,
                    "alignment": alignment_key,
                    "success_rate": success_rate,
                    "failures": failure_details,
                    "structured_sections": structured_sections,
                    "highlights": analysis_highlights,
                    "ai_raw_summary": raw_ai_summary,
                    "ai_summary_mode": ai_summary_mode,
                    "measurement_analysis": measurement_summary,
                    "structured_page_analysis": structured_page_analysis,
                }
            )

    if processed_files == 0:
        return _json_error("Analiz için geçerli PDF dosyası bulunamadı.", 404)

    return jsonify(
        {
            "engine": engine_label,
            "engine_key": engine_key,
            "summaries": summaries,
            "message": (
                f"{processed_files} arşivlenmiş dosya {engine_label} ile yeniden analiz edildi. "
                "Türkçe, İngilizce ve Almanca özetler hazırlandı."
            ),
        }
    )
