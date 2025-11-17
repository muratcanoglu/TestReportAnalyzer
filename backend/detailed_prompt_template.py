# -*- coding: utf-8 -*-
"""Prompt builder for detailed ECE-R80 PDF analyses."""
from __future__ import annotations

import json
import textwrap
from typing import Any, Dict, Optional


def format_structured_metadata(structured_metadata: Optional[Dict[str, Any]]) -> str:
    """Return a human-readable snapshot of parsed metadata for the prompt."""

    if not structured_metadata:
        return "Yapılandırılmış metadata bulunamadı."

    data = structured_metadata
    if not isinstance(data, dict):
        if isinstance(data, str):
            try:
                loaded = json.loads(data)
            except json.JSONDecodeError:
                loaded = {"raw": data}
            if isinstance(loaded, dict):
                data = loaded
            else:
                data = {"raw": data}
        else:
            data = {"value": data}

    try:
        return json.dumps(data, ensure_ascii=False, indent=2)
    except TypeError:
        return str(data)


def build_detailed_analysis_prompt(
    pdf_text: str,
    structured_metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """Assemble a detailed instruction set for AI-driven PDF analysis."""

    metadata_section = format_structured_metadata(structured_metadata)
    prompt = f"""
    Sen bir ECE-R80 Darbe Testi uzmanısın. Almanca veya İngilizce yazılmış test raporlarını okuyacak, bulguları Türkçe olarak açıklayacak ve test sonuçlarını yapılandırılmış veri halinde özetleyeceksin.

    # Görev
    - PDF test raporunu sayfa sayfa incele ve tüm kritik alanları doldur.
    - Grafiklerdeki sayısal değerleri ve PASS/FAIL durumlarını açıkla.
    - Raporun tamamını değerlendirip toplam test sayısı, başarılı/başarısız adetlerini ve başarı oranını hesapla.

    # Sayfa Bazlı Analiz
    ## Sayfa 1 (Prüfbericht)
    - Rapor kimliğini ("kieltXX_YY" formatı) belirt.
    - Test türü, test tarihi, düzenleyen (Bearbeiter) ve müşteri/firma bilgilerini çıkar.

    ## Sayfa 2 (Detaylı Bilgiler)
    - Auftraggeber (müşteri), Anwesende (katılımcılar) ve Versuchsbedingungen (test koşulları) maddelerini açıkla.
    - Kullanılan ekipmanları, test ürünü (Prüfling) özelliklerini ve Prüfergebnis bölümündeki i.O./n.i.O. durumlarını listele.
    - Lehnen-Winkel tablosundaki Vorher/Nachher açılarını ve hangi koltuk konumuna ait olduklarını yaz.

    ## Sayfa 3 (Dummy Belastung - Manken Yükleri)
    - Grafiklerdeki sol ve sağ manken ölçümlerini ayrıştır.
    - HAC sınırı 500 g, ThAC sınırı 30 g, FAC sınırı 10 kN'dir. Ölçülen her değer için PASS/FAIL durumunu belirle.
    - Sol ve sağ manken için HAC, ThAC, FAC değerlerini, zaman bilgileri varsa grafikten yorumlayarak raporla.
    - Grafik eğrilerinin genel formunu, pik değerlerini ve sınırlarla ilişkisini anlatan kısa bir özet üret.

    ## Sayfa 4 (Schlittenverzögerung)
    - Kızak hızını (sled velocity) ve hızlanma/eğri karakteristiklerini açıkla.
    - Schlittenverzögerung grafiğini yorumlayıp kritik noktaları özetle.

    ## Sayfa 5-6 (Fotodokümantasyon)
    - Test öncesi, sırası ve sonrası fotoğraflarda neler gösterildiğini kısaca özetle.

    # Çıktı Formatı
    - SADECE JSON döndür.
    - Aşağıdaki şemayı doldur; bilgi yoksa null veya boş string kullan:
      {{
        "report_id": "...",
        "test_type": "...",
        "test_date": "...",
        "page_2_details": {{
          "auftraggeber": "...",
          "anwesende": "...",
          "versuchsbedingungen": "...",
          "equipment": "...",
          "pruefling": {{...}},
          "pruefergebnis": {{...}},
          "lehnen_winkel_table": {{...}}
        }},
        "page_3_dummy_loads": {{
          "measured_values": {{
            "left_dummy": {{
              "HAC": float,
              "HAC_status": "PASS"/"FAIL",
              "ThAC": float,
              "ThAC_status": "PASS"/"FAIL",
              "FAC": float,
              "FAC_status": "PASS"/"FAIL",
              "overall_result": "PASS"/"FAIL"
            }},
            "right_dummy": {{ ... aynı alanlar ... }}
          }},
          "graph_analysis": {{
            "head_acceleration": "...",
            "chest_acceleration": "...",
            "femur_load": "..."
          }}
        }},
        "page_4_sled": {{
          "sled_velocity": "...",
          "deceleration_analysis": "..."
        }},
        "photo_documentation": {{
          "pre_test": "...",
          "during_test": "...",
          "post_test": "..."
        }},
        "overall_summary": {{
          "total_tests": int,
          "passed": int,
          "failed": int,
          "success_rate": "X%"
        }}
      }}

    # Ek Veri (varsa Page-2 parser çıktısı)
    {metadata_section}

    # PDF'den çıkarılan ham metin
    {pdf_text}
    """
    return textwrap.dedent(prompt).strip()
