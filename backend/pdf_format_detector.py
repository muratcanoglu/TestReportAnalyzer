# -*- coding: utf-8 -*-
import logging
import re
import unicodedata
from collections import OrderedDict
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)


def detect_pdf_format(text):
    """PDF formatını tespit et"""
    text_lower = (text or "").lower()

    if any(
        keyword in text_lower
        for keyword in [
            "nosab 16140",
            "tüv rheinland",
            "tuv rheinland",
            "kielt",
            "prüfbericht",
            "justierung/kontrolle",
        ]
    ):
        return "kielt_format"

    if "junit" in text_lower:
        return "junit_format"

    return "generic"


def parse_kielt_format(text):
    """
    Kielt/TÜV formatındaki PDF'i parse et - GERÇEK FORMAT

    Bu formatta:
    - "Test Koşulları" başlığı altında tüm bilgiler
    - "Justierung/Kontrolle" altında ölçüm değerleri
    - "Schlittenverzögerung" ayrı bölüm
    - "Belastungswerte" başlığı YOK (veriler doğrudan var)
    """
    sections = {}

    # 1. Test Koşulları - Ana bilgiler
    test_cond_pattern = (
        r"(?:Test\s*(?:Koşulları|Conditions|bedingungen))[:\s]*(.+?)(?=Schlittenverzögerung|Fotodokumentation|Prüfbericht\s+kielt|$)"
    )
    test_cond_match = re.search(test_cond_pattern, text, re.IGNORECASE | re.DOTALL)

    if test_cond_match:
        content = test_cond_match.group(1).strip()
        sections["test_conditions"] = content[:1500]
        logger.info("Test koşulları bulundu: %s karakter", len(content))

    # 2. Justierung/Kontrolle bölümü - Ölçüm değerleri burada
    justierung_pattern = r"Justierung/Kontrolle\s*:(.+?)(?=Software|Ingenieurbüro|Schlittenverzögerung|===|$)"
    justierung_match = re.search(justierung_pattern, text, re.IGNORECASE | re.DOTALL)

    if justierung_match:
        content = justierung_match.group(1).strip()
        sections["load_values"] = content
        sections["measurement_data"] = content
        logger.info("Ölçüm verileri bulundu: %s karakter", len(content))

    # 3. Schlittenverzögerung - Kızak yavaşlaması
    sled_pattern = r"Schlittenverzögerung:(.+?)(?=Fotodokumentation|Prüfbericht\s+kielt|===|$)"
    sled_match = re.search(sled_pattern, text, re.IGNORECASE | re.DOTALL)

    if sled_match:
        content = sled_match.group(1).strip()
        sections["sled_deceleration"] = content[:1000]
        logger.info("Schlittenverzögerung bulundu: %s karakter", len(content))

    # 4. Fotodokumentation
    photo_pattern = r"Fotodokumentation:(.+?)(?=Prüfbericht\s+kielt|Bearbeiter|$)"
    photo_match = re.search(photo_pattern, text, re.IGNORECASE | re.DOTALL)

    if photo_match:
        content = photo_match.group(1).strip()
        sections["photo_docs"] = content[:500]

    # 5. TABLO bölümlerini topla
    table_sections = []
    table_pattern = r"===\s*SAYFA\s*\d+\s*-\s*TABLO\s*\d+\s*===(.{0,100})"
    for match in re.finditer(table_pattern, text, re.IGNORECASE):
        table_sections.append(match.group(0))

    if table_sections:
        sections["tables_text"] = "\n".join(table_sections)

    return sections


_MEASUREMENT_HEADER_KEYWORDS = {
    "messgröße",
    "messgroesse",
    "measurement",
    "ölçüm",
    "olcum",
    "parametre",
    "parameter",
    "prüfpunkt",
    "prufpunkt",
    "testpunkt",
    "test point",
}

_UNIT_HEADER_KEYWORDS = {"einheit", "unit", "birim"}

_VALUE_HEADER_KEYWORDS = {
    "messwert",
    "wert",
    "werte",
    "value",
    "ergebnis",
    "result",
    "test",
    "messung",
}

_LIMIT_HEADER_KEYWORDS = {"grenzwert", "limit", "soll"}

_MEASUREMENT_NAME_MAP: Dict[str, Tuple[str, str]] = {
    "a kopf uber 3 ms": ("Baş ivmesi (a Kopf über 3 ms)", "g"),
    "thac": ("Göğüs ivmesi (ThAC)", "g"),
    "fac right f": ("Sağ femur kuvveti (FAC right)", "kN"),
    "fac left f": ("Sol femur kuvveti (FAC left)", "kN"),
    "hac": ("HAC (Head Acceleration Criterion)", ""),
}

_NUMBER_PATTERN = re.compile(r"[-+]?[0-9][0-9.,]*")


def normalize_decimal(value: object) -> Optional[float]:
    """Convert localized decimal strings into floats.

    Handles values such as ``58,15``, ``1.234,56`` or ``1,234.56`` while
    logging failures for debugging.
    """

    if value is None:
        return None

    text = str(value).strip().replace("\xa0", "")
    if not text:
        return None

    sign = 1
    if text[0] in "+-":
        if text[0] == "-":
            sign = -1
        text = text[1:]

    digits_only = text.replace(" ", "")
    if not digits_only or not re.fullmatch(r"[0-9.,]+", digits_only):
        logger.warning("normalize_decimal: non-numeric input skipped: %r", value)
        return None

    comma_pos = digits_only.rfind(",")
    dot_pos = digits_only.rfind(".")

    normalized = digits_only
    if comma_pos != -1 and dot_pos != -1:
        if comma_pos > dot_pos:
            normalized = digits_only.replace(".", "").replace(",", ".")
        else:
            normalized = digits_only.replace(",", "")
    elif comma_pos != -1:
        fractional_digits = len(digits_only) - comma_pos - 1
        if digits_only.count(",") == 1 and 0 < fractional_digits <= 2:
            normalized = digits_only.replace(",", ".")
        else:
            normalized = digits_only.replace(",", "")
    elif dot_pos != -1:
        normalized = digits_only

    if sign == -1:
        normalized = f"-{normalized}"

    try:
        return float(normalized)
    except ValueError:
        logger.warning(
            "normalize_decimal: unable to parse %r (normalized=%s)", value, normalized
        )
        return None


def extract_measurement_params(
    text: str,
    tables: Optional[List[Dict[str, object]]] = None,
):
    """
    GERÇEK formatına göre ölçüm parametrelerini çıkar

    Format:
        a Kopf über 3 ms [g] 58.15
        ThAC [g] 18.4
        FAC right F [kN] 4.40
    """
    params_map: "OrderedDict[Tuple[str, str], Dict[str, List[object]]]" = OrderedDict()

    def _add_param(name: str, unit: str, values: Iterable[str]) -> None:
        name = (name or "").strip()
        unit = (unit or "").strip()
        if not name:
            return
        values_list = [str(value).strip() for value in values if str(value).strip()]
        if not values_list:
            return

        key = (name, unit)
        if key not in params_map:
            params_map[key] = {"values": [], "raw_values": []}

        entry = params_map[key]
        for raw_value in values_list:
            normalized = normalize_decimal(raw_value)
            if normalized is None:
                continue
            if normalized not in entry["values"]:
                entry["values"].append(normalized)
                entry["raw_values"].append(raw_value)

    # Pattern 1: "a Kopf über 3 ms [g] 58.15"
    kopf_pattern = r"a\s+Kopf\s+über\s+3\s*ms\s*\[g\]\s*([\d,\.]+)"
    kopf_matches = re.findall(kopf_pattern, text, re.IGNORECASE)
    if kopf_matches:
        _add_param("Baş ivmesi (a Kopf über 3 ms)", "g", kopf_matches)
        logger.info("Kopf değerleri bulundu: %s", kopf_matches)

    # Pattern 2: "ThAC [g] 18.4"
    thac_pattern = r"ThAC\s*\[g\]\s*([\d,\.]+)"
    thac_matches = re.findall(thac_pattern, text, re.IGNORECASE)
    if thac_matches:
        _add_param("Göğüs ivmesi (ThAC)", "g", thac_matches)
        logger.info("ThAC değerleri bulundu: %s", thac_matches)

    # Pattern 3: "FAC right F [kN] 4.40"
    fac_right_pattern = r"FAC\s+right\s+F\s*\[kN\]\s*([\d,\.]+)"
    fac_right_matches = re.findall(fac_right_pattern, text, re.IGNORECASE)
    if fac_right_matches:
        _add_param("Sağ femur kuvveti (FAC right)", "kN", fac_right_matches)
        logger.info("FAC right değerleri bulundu: %s", fac_right_matches)

    # Pattern 4: "FAC left F [kN] 4.82"
    fac_left_pattern = r"FAC\s+left\s+F\s*\[kN\]\s*([\d,\.]+)"
    fac_left_matches = re.findall(fac_left_pattern, text, re.IGNORECASE)
    if fac_left_matches:
        _add_param("Sol femur kuvveti (FAC left)", "kN", fac_left_matches)
        logger.info("FAC left değerleri bulundu: %s", fac_left_matches)

    # Pattern 5: "HAC, [120.1, 146.05 ms] 161.18"
    hac_pattern = r"HAC,\s*\[[\d,\.]+,\s*[\d,\.]+\s*ms\]\s*([\d,\.]+)"
    hac_matches = re.findall(hac_pattern, text, re.IGNORECASE)
    if hac_matches:
        _add_param("HAC (Head Acceleration Criterion)", "", hac_matches)
        logger.info("HAC değerleri bulundu: %s", hac_matches)

    table_params = _extract_params_from_tables(tables or [])
    for param in table_params:
        _add_param(param["name"], param["unit"], param["values"])

    params = [
        {
            "name": name,
            "unit": unit,
            "values": entry["values"],
            "raw_values": entry["raw_values"],
        }
        for (name, unit), entry in params_map.items()
    ]

    logger.info("Toplam %s parametre grubu bulundu", len(params))
    return params


def _extract_params_from_tables(
    tables: Sequence[Dict[str, object]]
) -> List[Dict[str, object]]:
    params: List[Dict[str, object]] = []

    for table in tables:
        data = table.get("data") if isinstance(table, dict) else None
        if not data:
            continue

        cleaned_rows: List[List[str]] = []
        for row in data:
            if not row:
                continue
            cleaned_rows.append([_clean_cell(cell) for cell in row])

        if not cleaned_rows:
            continue

        header_info = _locate_header_row(cleaned_rows)
        if not header_info:
            continue

        header_index, header_row = header_info
        header_identifiers = [_normalize_identifier(cell) for cell in header_row]

        name_column = _find_column(header_identifiers, _MEASUREMENT_HEADER_KEYWORDS)
        unit_column = _find_column(header_identifiers, _UNIT_HEADER_KEYWORDS)

        if name_column is None and header_row:
            name_column = 0

        limit_columns = {
            idx
            for idx, cell in enumerate(header_identifiers)
            if any(keyword in cell for keyword in _LIMIT_HEADER_KEYWORDS)
        }

        value_columns = [
            idx
            for idx in range(len(header_row))
            if idx != name_column
            and idx != unit_column
            and idx not in limit_columns
        ]

        if not value_columns:
            value_columns = [
                idx
                for idx in range(len(header_row))
                if idx != name_column and idx != unit_column
            ]

        for row in cleaned_rows[header_index + 1 :]:
            if not row:
                continue

            raw_name = _get_cell(row, name_column) or row[0]
            name, name_unit = _split_name_and_unit(raw_name)
            if not name:
                continue

            unit = _clean_unit(_get_cell(row, unit_column))
            if not unit:
                unit = _clean_unit(name_unit)

            values: List[str] = []
            for column in value_columns:
                cell_value = _get_cell(row, column)
                if not cell_value:
                    continue
                for numeric in _extract_numeric_values(cell_value):
                    if numeric not in values:
                        values.append(numeric)

            if not values:
                continue

            localized_name, fallback_unit = _localise_measurement_name(name)
            unit = unit or fallback_unit

            params.append({"name": localized_name, "unit": unit, "values": values})

    return params


def _clean_cell(cell: object) -> str:
    if cell is None:
        return ""
    return str(cell).strip()


def _normalize_identifier(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("ß", "ss")
    text = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return text.strip()


def _locate_header_row(rows: Sequence[Sequence[str]]) -> Optional[Tuple[int, List[str]]]:
    for index, row in enumerate(rows):
        identifiers = [_normalize_identifier(cell) for cell in row]
        if not any(identifiers):
            continue

        score = 0
        row_tokens = " ".join(identifiers)

        if any(keyword in row_tokens for keyword in _MEASUREMENT_HEADER_KEYWORDS):
            score += 1
        if any(keyword in row_tokens for keyword in _UNIT_HEADER_KEYWORDS):
            score += 1
        if any(keyword in row_tokens for keyword in _VALUE_HEADER_KEYWORDS):
            score += 1

        if score >= 2 or (score >= 1 and len(row) >= 3):
            return index, list(row)

    return None


def _find_column(identifiers: Sequence[str], keywords: Iterable[str]) -> Optional[int]:
    keyword_set = {keyword for keyword in keywords}
    for index, identifier in enumerate(identifiers):
        if any(keyword in identifier for keyword in keyword_set):
            return index
    return None


def _get_cell(row: Sequence[str], index: Optional[int]) -> str:
    if index is None:
        return ""
    if index >= len(row):
        return ""
    return row[index]


def _split_name_and_unit(text: str) -> Tuple[str, str]:
    pattern = re.compile(r"(.*?)[\[(]([^\]\)]+)[\])]\s*$")
    match = pattern.search(text)
    if match:
        name = match.group(1).strip()
        unit = match.group(2).strip()
        return name, unit
    return text.strip(), ""


def _clean_unit(unit: str) -> str:
    unit = (unit or "").strip()
    if unit.startswith("[") and unit.endswith("]"):
        unit = unit[1:-1].strip()
    return unit


def _extract_numeric_values(cell: str) -> List[str]:
    matches = _NUMBER_PATTERN.findall(cell.replace("\xa0", " "))
    values: List[str] = []
    for match in matches:
        cleaned = match.strip()
        if cleaned:
            values.append(cleaned)
    return values


def _localise_measurement_name(name: str) -> Tuple[str, str]:
    identifier = _normalize_identifier(name)
    mapped = _MEASUREMENT_NAME_MAP.get(identifier)
    if mapped:
        return mapped
    return name, ""


def _stringify_value(value: object) -> str:
    if isinstance(value, float):
        return format(value, "g")
    return str(value)


def format_measurement_params_for_ai(params):
    """
    Measurement params'ı AI için okunabilir formata çevir
    """
    if not params:
        return ""

    lines = ["=== ÖLÇÜM PARAMETRELERİ ===\n"]

    for param in params:
        name = param["name"]
        unit = param["unit"]
        values = param["values"]
        formatted_values = [_stringify_value(value) for value in values]

        if len(formatted_values) == 1:
            lines.append(f"• {name}: {formatted_values[0]} {unit}")
        elif len(formatted_values) == 2:
            lines.append(
                f"• {name}: {formatted_values[0]} {unit} ve {formatted_values[1]} {unit}"
            )
        else:
            values_str = ", ".join(formatted_values[:3])
            lines.append(f"• {name}: {values_str} {unit}")

    return "\n".join(lines)


__all__ = [
    "detect_pdf_format",
    "parse_kielt_format",
    "extract_measurement_params",
    "normalize_decimal",
    "format_measurement_params_for_ai",
]
