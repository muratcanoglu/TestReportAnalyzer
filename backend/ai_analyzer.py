# -*- coding: utf-8 -*-
"""AI destekli test hatası analizi yardımcı sınıfı."""

import json
import logging
import os
import re
import textwrap
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from anthropic import Anthropic
from openai import OpenAI
from dotenv import load_dotenv

try:  # pragma: no cover - allow running as script
    from .structured_data_parser import format_structured_data_for_ai
except ImportError:  # pragma: no cover
    from structured_data_parser import format_structured_data_for_ai  # type: ignore

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

logger = logging.getLogger(__name__)


DEFAULT_SUMMARY_LABELS: Dict[str, Dict[str, str]] = {
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

SECTION_LANGUAGE_STRINGS: Dict[str, Dict[str, str]] = {
    "tr": {
        "no_test_conditions": "Test koşullarına ilişkin belirgin bilgi bulunamadı.",
        "no_graphs": "Grafikler hakkında açık bilgi yok.",
        "no_results": "Test sonuçları metin içerisinde tespit edilemedi.",
        "no_detailed": "Detaylı teknik veri bölümü bulunamadı.",
        "conditions_intro": "Metinden çıkarılan test koşulları:",
        "graphs_intro": "Grafiklere ilişkin öne çıkan noktalar:",
        "results_intro": "Test sonuçlarının özet tablosu:",
        "appendix": "Ek teknik veriler:",
        "improvements_intro": "Önerilen geliştirme maddeleri:",
        "improvements_fail": (
            "Belirlenen riskleri gidermek için test parametrelerini, ölçüm cihazlarını ve standart referanslarını gözden geçirin."
        ),
        "improvements_success": "Test sonuçları olumlu; mevcut validasyon sürecini koruyabilirsiniz.",
        "table_header_index": "#",
        "table_header_detail": "Detay",
    },
    "en": {
        "no_test_conditions": "No explicit test condition details were detected.",
        "no_graphs": "There is no explicit information about charts or graphs.",
        "no_results": "Detailed test results were not identified in the document.",
        "no_detailed": "No additional technical data section was detected.",
        "conditions_intro": "Extracted test condition highlights:",
        "graphs_intro": "Key points related to charts/figures:",
        "results_intro": "Summary table of the reported test outcomes:",
        "appendix": "Additional technical observations:",
        "improvements_intro": "Recommended improvement actions:",
        "improvements_fail": (
            "Review acceptance criteria, instrumentation and repeat the tests focusing on the flagged measurements."
        ),
        "improvements_success": "All findings look positive; keep the current validation workflow stable.",
        "table_header_index": "#",
        "table_header_detail": "Detail",
    },
    "de": {
        "no_test_conditions": "Es konnten keine eindeutigen Prüfbedingungen erkannt werden.",
        "no_graphs": "Im Bericht wurden keine klaren Angaben zu Diagrammen gefunden.",
        "no_results": "Ausführliche Testergebnisse wurden nicht identifiziert.",
        "no_detailed": "Es wurde kein Abschnitt mit zusätzlichen technischen Daten gefunden.",
        "conditions_intro": "Hervorhebungen zu den Prüfbedingungen:",
        "graphs_intro": "Wesentliche Hinweise zu Diagrammen/Grafiken:",
        "results_intro": "Zusammenfassung der berichteten Testergebnisse:",
        "appendix": "Zusätzliche technische Beobachtungen:",
        "improvements_intro": "Empfohlene Verbesserungsmaßnahmen:",
        "improvements_fail": (
            "Überprüfen Sie Grenzwerte, Messaufbauten und wiederholen Sie die Tests mit Fokus auf die auffälligen Messwerte."
        ),
        "improvements_success": "Die Ergebnisse wirken positiv; halten Sie den aktuellen Prüfablauf bei.",
        "table_header_index": "#",
        "table_header_detail": "Detail",
    },
}


class AIAnalyzer:
    """Test başarısızlıklarını AI veya kural tabanlı yöntemlerle analiz eder."""

    def __init__(self) -> None:
        self.provider = "none"
        self.anthropic_key = ""
        self.openai_key = ""
        self.claude_model = "claude-3-5-sonnet-20240620"
        self.openai_model = "gpt-4o-mini"
        self.max_tokens = 1200
        self.timeout = 60
        self.claude_client = None
        self.openai_client = None
        self._claude_client_key = None
        self._openai_client_key = None
        self._forced_provider: Optional[str] = None
        self._translation_cache: Dict[
            Tuple[str, str, Tuple[str, ...]], Dict[str, str]
        ] = {}
        self._refresh_configuration()

    @staticmethod
    def _normalise_provider_value(provider: Optional[str]) -> str:
        value = (provider or "none").strip().lower()
        if value not in {"claude", "chatgpt", "both", "none"}:
            return "none"
        return value

    def _refresh_configuration(self) -> None:
        """Ortam değişkenlerini okuyup gerekli istemcileri güncelle."""
        env_provider = os.getenv("AI_PROVIDER", self.provider) or "none"
        provider_value = self._normalise_provider_value(env_provider)
        if self._forced_provider is not None:
            provider_value = self._normalise_provider_value(self._forced_provider)
        self.provider = provider_value
        self.anthropic_key = (os.getenv("ANTHROPIC_API_KEY", "") or "").strip()
        self.openai_key = (os.getenv("OPENAI_API_KEY", "") or "").strip()
        claude_model = os.getenv("AI_ANTHROPIC_MODEL") or os.getenv(
            "AI_MODEL_CLAUDE", self.claude_model
        )
        openai_model = os.getenv("AI_OPENAI_MODEL") or os.getenv(
            "AI_MODEL_OPENAI", self.openai_model
        )
        self.claude_model = claude_model or self.claude_model
        self.openai_model = openai_model or self.openai_model

        try:
            self.max_tokens = int(os.getenv("AI_MAX_TOKENS", str(self.max_tokens)) or self.max_tokens)
        except ValueError:
            self.max_tokens = 1200

        try:
            self.timeout = int(
                os.getenv("AI_TIMEOUT_S")
                or os.getenv("AI_TIMEOUT")
                or str(self.timeout)
            )
        except ValueError:
            self.timeout = 60

        if self.anthropic_key:
            if self.anthropic_key != self._claude_client_key:
                try:
                    self.claude_client = Anthropic(api_key=self.anthropic_key)
                    self._claude_client_key = self.anthropic_key
                except Exception as exc:  # pragma: no cover - yalnızca hata kaydı
                    print(f"[AIAnalyzer] Claude istemcisi oluşturulamadı: {exc}")
                    self.claude_client = None
                    self._claude_client_key = None
        else:
            self.claude_client = None
            self._claude_client_key = None

        if self.openai_key:
            if self.openai_key != self._openai_client_key:
                try:
                    self.openai_client = OpenAI(api_key=self.openai_key)
                    self._openai_client_key = self.openai_key
                except Exception as exc:  # pragma: no cover - yalnızca hata kaydı
                    print(f"[AIAnalyzer] OpenAI istemcisi oluşturulamadı: {exc}")
                    self.openai_client = None
                    self._openai_client_key = None
        else:
            self.openai_client = None
            self._openai_client_key = None

    def analyze_failure_with_ai(self, test_name: str, error_message: str, test_context: str = "") -> Dict[str, str]:
        """Sağlanan AI sağlayıcısına göre analiz yap."""
        self._refresh_configuration()
        prompt = self._create_analysis_prompt(test_name, error_message, test_context)

        provider = self.provider or "none"
        provider = provider.lower()

        if provider == "none":
            return self._rule_based_analysis(error_message)

        if provider == "claude":
            return self._analyze_with_claude(prompt, error_message)

        if provider == "chatgpt":
            return self._analyze_with_chatgpt(prompt, error_message)

        if provider == "both":
            claude_result = self._analyze_with_claude(prompt, error_message)
            if claude_result.get("ai_provider") == "claude":
                return claude_result
            return self._analyze_with_chatgpt(prompt, error_message)

        # Bilinmeyen provider durumunda kural tabanlı analize dön
        return self._rule_based_analysis(error_message)

    def _create_analysis_prompt(self, test_name: str, error_message: str, test_context: str) -> str:
        """AI modelinden yapılandırılmış bir JSON çıktısı isteyen Türkçe prompt hazırla."""
        context_section = ""
        if test_context.strip():
            context_section = f"\nTest bağlamı:\n{test_context.strip()}"

        prompt = (
            "Aşağıdaki test başarısızlığını analiz et ve nedenini açıkla. "
            "Yanıtta yalnızca JSON formatı döndür."
            f"\n\nTest adı: {test_name}\nHata mesajı: {error_message}{context_section}\n"
            "\nLütfen şu JSON formatında ve Türkçe yanıt ver:\n"
            "{\n"
            "  \"failure_reason\": \"<kısa açıklama>\",\n"
            "  \"suggested_fix\": \"<önerilen çözüm>\"\n"
            "}"
        )
        return prompt

    def _analyze_with_claude(self, prompt: str, error_message: str) -> Dict[str, str]:
        """Claude API çağrısı yap ve sonucu JSON olarak işle."""
        if not self.claude_client:
            return self._rule_based_analysis(error_message)

        try:
            data = self._request_json_from_claude(prompt, max_tokens=self.max_tokens)
            failure_reason = data.get("failure_reason", "").strip()
            suggested_fix = data.get("suggested_fix", "").strip()
            if not failure_reason or not suggested_fix:
                raise ValueError("Claude yanıtı eksik alan içeriyor")
            return {
                "failure_reason": failure_reason,
                "suggested_fix": suggested_fix,
                "ai_provider": "claude",
            }
        except Exception as exc:  # pragma: no cover - API hataları kullanıcıya gösterilmez
            print(f"[AIAnalyzer] Claude analizi başarısız: {exc}")
            return self._rule_based_analysis(error_message)

    def _analyze_with_chatgpt(self, prompt: str, error_message: str) -> Dict[str, str]:
        """OpenAI Chat Completions API çağrısı yap."""
        if not self.openai_client:
            return self._rule_based_analysis(error_message)

        try:
            data = self._request_json_from_chatgpt(prompt, max_tokens=self.max_tokens)
            failure_reason = data.get("failure_reason", "").strip()
            suggested_fix = data.get("suggested_fix", "").strip()
            if not failure_reason or not suggested_fix:
                raise ValueError("ChatGPT yanıtı eksik alan içeriyor")
            return {
                "failure_reason": failure_reason,
                "suggested_fix": suggested_fix,
                "ai_provider": "chatgpt",
            }
        except Exception as exc:  # pragma: no cover - API hataları kullanıcıya gösterilmez
            print(f"[AIAnalyzer] ChatGPT analizi başarısız: {exc}")
            return self._rule_based_analysis(error_message)

    def _request_json_from_claude(self, prompt: str, max_tokens: Optional[int] = None) -> Dict:
        """Claude API'sinden JSON içerik döndür."""
        if not self.claude_client:
            raise ValueError("Claude client not configured")

        client = self.claude_client
        if hasattr(client, "with_options"):
            client = client.with_options(timeout=self.timeout)

        response = client.messages.create(
            model=self.claude_model,
            max_tokens=max_tokens or self.max_tokens,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )

        content = ""
        if getattr(response, "content", None):
            content = "".join(
                getattr(block, "text", "") for block in response.content if getattr(block, "text", "")
            )

        if not content:
            raise ValueError("Claude yanıtı boş döndü")

        return json.loads(content)

    def _request_json_from_chatgpt(self, prompt: str, max_tokens: Optional[int] = None) -> Dict:
        """OpenAI Chat Completions API çağrısından JSON yanıtı döndür."""
        if not self.openai_client:
            raise ValueError("ChatGPT client not configured")

        client = self.openai_client
        if hasattr(client, "with_options"):
            client = client.with_options(timeout=self.timeout)

        response = client.chat.completions.create(
            model=self.openai_model,
            messages=[
                {
                    "role": "system",
                    "content": "Sen uzman bir test analisti olarak Türkçe konuşuyorsun. Yanıtı JSON formatında üret.",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_tokens or self.max_tokens,
            temperature=0,
        )

        content = response.choices[0].message.content if response.choices else ""
        if not content:
            raise ValueError("ChatGPT yanıtı boş döndü")

        return json.loads(content)

    def request_text_completion(self, prompt: str, *, max_tokens: Optional[int] = None) -> Optional[str]:
        """Return a plain-text completion using the configured AI provider if possible."""

        self._refresh_configuration()
        provider = (self.provider or "none").lower()
        if provider == "none":
            return None

        candidates: List[str]
        if provider == "both":
            candidates = ["claude", "chatgpt"]
        else:
            candidates = [provider]

        for candidate in candidates:
            try:
                if candidate == "claude":
                    if not self.claude_client:
                        continue
                    client = self.claude_client
                    if hasattr(client, "with_options"):
                        client = client.with_options(timeout=self.timeout)
                    response = client.messages.create(
                        model=self.claude_model,
                        max_tokens=max_tokens or self.max_tokens,
                        temperature=0,
                        messages=[{"role": "user", "content": prompt}],
                    )
                    text = ""
                    if getattr(response, "content", None):
                        text = "".join(
                            getattr(block, "text", "")
                            for block in response.content
                            if getattr(block, "text", "")
                        )
                else:
                    if not self.openai_client:
                        continue
                    client = self.openai_client
                    if hasattr(client, "with_options"):
                        client = client.with_options(timeout=self.timeout)
                    response = client.chat.completions.create(
                        model=self.openai_model,
                        messages=[
                            {
                                "role": "system",
                                "content": (
                                    "You are an expert automotive test analyst. "
                                    "Respond concisely in the same language as the user."
                                ),
                            },
                            {"role": "user", "content": prompt},
                        ],
                        max_tokens=max_tokens or self.max_tokens,
                        temperature=0,
                    )
                    text = response.choices[0].message.content if response.choices else ""

                if text and text.strip():
                    return text.strip()
            except Exception as exc:  # pragma: no cover - API errors should not crash the app
                print(f"[AIAnalyzer] {candidate} section analysis failed: {exc}")
                continue

        return None

    @contextmanager
    def temporary_provider(self, provider: Optional[str]):
        """Context manager to temporarily override the active AI provider."""

        previous = self._forced_provider
        try:
            self._forced_provider = provider
            self._refresh_configuration()
            yield
        finally:
            self._forced_provider = previous
            self._refresh_configuration()

    def _prepare_report_excerpt(self, text: str, limit: int = 12000) -> str:
        """PDF metninden özet çıkar ve uzunluğu sınırla."""
        cleaned = re.sub(r"\s+", " ", text.strip())
        if len(cleaned) <= limit:
            return cleaned

        # Metnin başından, ortasından ve sonundan örnekler alarak bağlamı koru
        segment_length = max(limit // 3, 1000)
        head = cleaned[:segment_length]
        tail = cleaned[-segment_length:]
        midpoint = len(cleaned) // 2
        middle_start = max(midpoint - segment_length // 2, 0)
        middle_end = middle_start + segment_length
        middle = cleaned[middle_start:middle_end]

        return "\n…\n".join([head.strip(), middle.strip(), tail.strip()])

    def _create_report_summary_prompt(
        self,
        *,
        filename: str,
        report_type: str,
        total_tests: int,
        passed_tests: int,
        failed_tests: int,
        excerpt: str,
        failure_details: Sequence[Dict[str, str]],
    ) -> str:
        """Raporun tamamını özetleyecek çok dilli JSON yanıtı iste."""

        failure_lines: List[str] = []
        for failure in failure_details:
            test_name = failure.get("test_name", "Bilinmeyen Test")
            reason = failure.get("failure_reason") or failure.get("error_message") or ""
            suggestion = failure.get("suggested_fix") or ""
            joined = f"{test_name}: {reason}".strip()
            if suggestion:
                joined += f" | Öneri: {suggestion}"
            failure_lines.append(joined)

        failure_block = "\n".join(failure_lines) if failure_lines else "(başarısız test bulunmuyor)"

        prompt = f"""
PDF test raporunu analiz eden uzman bir mühendis olarak hareket et. Rapor dosya adı: {filename}. Test türü: {report_type}.
Toplam test sayısı: {total_tests}. Başarılı test sayısı: {passed_tests}. Başarısız test sayısı: {failed_tests}.
Başarısız testlerin özet listesi:
{failure_block}

Rapor metninden çıkarılmış içerik (görsel ve tablo açıklamaları dahil olabilir):
"""

        prompt += excerpt
        prompt += """

GÖREV:
- Metni dikkatlice incele; grafikler, ölçüm koşulları, kullanılan standartlar, sonuçlar ve uzman yorumları gibi öğeleri ayrıntılı biçimde değerlendir.
- Yanıtı mutlaka geçerli JSON formatında ver.
- Her dil için summary/conditions/improvements alanlarına ek olarak "labels" nesnesi üret ve bu nesnede ilgili başlıkları (ör. "Test Koşulları", "Test Conditions", "Testbedingungen") o dilde ver.
- "sections" alanında grafikler, test kurulumları, ölçüm sonuçları ve yorumlara dair teknik özeti ayrıntılı doldur.
- Aşağıdaki yapıyı kullan:
{
  "localized_summaries": {
    "tr": {"summary": "...", "conditions": "...", "improvements": "...", "labels": {"summary": "Genel Özet", "conditions": "Test Koşulları", "improvements": "İyileştirme Önerileri"}},
    "en": {"summary": "...", "conditions": "...", "improvements": "...", "labels": {"summary": "Summary", "conditions": "Test Conditions", "improvements": "Improvement Suggestions"}},
    "de": {"summary": "...", "conditions": "...", "improvements": "...", "labels": {"summary": "Zusammenfassung", "conditions": "Testbedingungen", "improvements": "Verbesserungsvorschläge"}}
  },
  "sections": {
    "graphs": "Grafik ve görsel anlatımların özeti",
    "conditions": "Test kurulumları ve çevresel koşullar",
    "results": "Önemli ölçüm sonuçları",
    "comments": "Uzman görüşü veya değerlendirilen yorumlar"
  },
  "highlights": ["En fazla 5 kısa maddelik önemli bulgular listesi"]
}

Tüm metinleri ilgili dilde üret. JSON dışında açıklama yapma.
"""

        return textwrap.dedent(prompt).strip()

    def _create_translation_prompt(
        self,
        *,
        text: str,
        source_language: str,
        target_languages: Sequence[str],
    ) -> str:
        language_names = {"tr": "Turkish", "en": "English", "de": "German"}
        source_label = language_names.get(source_language, source_language or "original language")
        targets_description = ", ".join(
            f"{language_names.get(lang, lang)} ({lang})" for lang in target_languages
        )
        key_list = ", ".join(f'"{lang}"' for lang in target_languages)
        example_lines: List[str] = []
        for index, lang in enumerate(target_languages):
            suffix = "," if index < len(target_languages) - 1 else ""
            example_lines.append(f'                "{lang}": "..."{suffix}')
        example_block = "\n".join(example_lines) if example_lines else '                "tr": "..."'
        template = """
            Sen teknik test raporları için uzman bir çevirmen olarak görev yapıyorsun.
            Verilen metin {source_label} dilindedir. Bu metni {targets_description} dillerine çevir.
            Yanıtını mutlaka geçerli JSON formatında ver ve ek açıklama ekleme.
            JSON çıktısında yalnızca translations anahtarını ve şu alt anahtarları kullan: {key_list}.
            Örnek yapı:
            {{
              "translations": {{
{example_block}
              }}
            }}

            Çevrilecek metin aşağıda verilmiştir:
            ---
            {text}
            ---
        """
        prompt = textwrap.dedent(template).strip().format(
            source_label=source_label,
            targets_description=targets_description,
            key_list=key_list,
            example_block=example_block,
            text=text,
        )
        return prompt

    def _parse_translation_response(
        self, payload: Dict, target_languages: Sequence[str]
    ) -> Dict[str, str]:
        translations = payload.get("translations") if isinstance(payload, dict) else {}
        normalised: Dict[str, str] = {}
        if isinstance(translations, dict):
            for language in target_languages:
                value = translations.get(language, "") if language in translations else ""
                value_str = str(value).strip()
                if value_str:
                    normalised[language] = value_str
        else:
            for language in target_languages:
                value = payload.get(language, "") if isinstance(payload, dict) else ""
                value_str = str(value).strip()
                if value_str:
                    normalised[language] = value_str
        return normalised

    def translate_texts(
        self,
        text: str,
        *,
        source_language: Optional[str] = None,
        target_languages: Sequence[str] = (),
    ) -> Dict[str, str]:
        cleaned_text = (text or "").strip()
        if not cleaned_text:
            return {}

        targets = tuple(sorted({str(lang).strip().lower() for lang in target_languages if str(lang).strip()}))
        if not targets:
            return {}

        source_key = (source_language or "").strip().lower()
        cache_key = (source_key, cleaned_text, targets)
        if cache_key in self._translation_cache:
            return dict(self._translation_cache[cache_key])

        self._refresh_configuration()
        provider = (self.provider or "none").lower()
        if provider == "none":
            return {}

        prompt = self._create_translation_prompt(
            text=cleaned_text, source_language=source_key or "", target_languages=targets
        )
        candidates: List[str]
        if provider == "both":
            candidates = ["claude", "chatgpt"]
        else:
            candidates = [provider]

        max_tokens = min(self.max_tokens * 2, 1200)
        for candidate in candidates:
            try:
                if candidate == "claude":
                    data = self._request_json_from_claude(prompt, max_tokens=max_tokens)
                else:
                    data = self._request_json_from_chatgpt(prompt, max_tokens=max_tokens)
                if not isinstance(data, dict):
                    continue
                translations = self._parse_translation_response(data, targets)
                if translations:
                    self._translation_cache[cache_key] = dict(translations)
                    return translations
            except Exception as exc:  # pragma: no cover - API hataları kullanıcıya gösterilmez
                print(f"[AIAnalyzer] {candidate} çeviri isteği başarısız: {exc}")
                continue

        return {}

    def _normalise_summary_response(self, payload: Dict) -> Dict[str, object]:
        """AI yanıtını öngörülen anahtarlara göre düzenle."""

        localized = payload.get("localized_summaries") or payload.get("localized") or payload.get("languages") or {}
        sections = payload.get("sections") or payload.get("structured_sections") or {}
        highlights = payload.get("highlights") or payload.get("key_findings") or []

        normalised_localized = {}
        for language in ("tr", "en", "de"):
            entry = localized.get(language, {}) if isinstance(localized, dict) else {}
            raw_labels = entry.get("labels") if isinstance(entry, dict) else {}
            defaults = DEFAULT_SUMMARY_LABELS.get(language, {})
            labels = {}
            for key in ("summary", "conditions", "improvements", "technical", "highlights", "failures"):
                value = ""
                if isinstance(raw_labels, dict):
                    value = str(raw_labels.get(key, "")).strip()
                default_value = str(defaults.get(key, "")).strip()
                labels[key] = value or default_value

            normalised_localized[language] = {
                "summary": (entry.get("summary") or "").strip(),
                "conditions": (entry.get("conditions") or "").strip(),
                "improvements": (entry.get("improvements") or "").strip(),
                "labels": labels,
            }

        normalised_sections = {}
        if isinstance(sections, dict):
            for key in ("graphs", "conditions", "results", "comments"):
                value = sections.get(key, "")
                if isinstance(value, list):
                    value = " ".join(str(item).strip() for item in value if str(item).strip())
                normalised_sections[key] = str(value).strip()

        normalised_highlights: List[str] = []
        if isinstance(highlights, (list, tuple)):
            for item in highlights:
                text = str(item).strip()
                if text:
                    normalised_highlights.append(text)

        return {
            "localized_summaries": normalised_localized,
            "sections": normalised_sections,
            "highlights": normalised_highlights,
        }

    def generate_report_summary(
        self,
        *,
        filename: str,
        report_type: str,
        total_tests: int,
        passed_tests: int,
        failed_tests: int,
        raw_text: str,
        failure_details: Sequence[Dict[str, str]],
    ) -> Optional[Dict[str, object]]:
        """PDF metnini detaylı şekilde inceleyen bir özet üret."""

        self._refresh_configuration()
        provider = (self.provider or "none").lower()
        if provider == "none":
            return None

        excerpt = self._prepare_report_excerpt(raw_text)
        prompt = self._create_report_summary_prompt(
            filename=filename,
            report_type=report_type,
            total_tests=total_tests,
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            excerpt=excerpt,
            failure_details=failure_details,
        )

        providers: List[str]
        if provider == "both":
            providers = ["claude", "chatgpt"]
        else:
            providers = [provider]

        for candidate in providers:
            try:
                if candidate == "claude":
                    data = self._request_json_from_claude(prompt, max_tokens=min(self.max_tokens * 2, 1500))
                else:
                    data = self._request_json_from_chatgpt(prompt, max_tokens=min(self.max_tokens * 2, 1500))
                if not isinstance(data, dict):
                    continue
                return self._normalise_summary_response(data)
            except Exception as exc:  # pragma: no cover - ağ hataları raporlanmaz
                print(f"[AIAnalyzer] Rapor özeti üretilemedi ({candidate}): {exc}")

        return None

    def _rule_based_analysis(self, error_message: str) -> Dict[str, str]:
        """Basit kural tabanlı analizle fallback sonucu döndür."""
        message = (error_message or "").lower()

        if "timeout" in message:
            return {
                "failure_reason": "Test zaman aşımına uğradı",
                "suggested_fix": "Zaman aşımı limitini artırın veya performans darboğazlarını araştırın.",
                "ai_provider": "rule-based",
            }
        if "connection" in message or "network" in message:
            return {
                "failure_reason": "Bağlantı veya ağ hatası",
                "suggested_fix": "Servislerin ve ağ bağlantısının çalıştığını doğrulayın.",
                "ai_provider": "rule-based",
            }
        if "null" in message or "none" in message:
            return {
                "failure_reason": "Boş/None değer kullanımı",
                "suggested_fix": "Null kontrolleri ekleyin ve gerekli verilerin sağlandığından emin olun.",
                "ai_provider": "rule-based",
            }
        if "permission" in message:
            return {
                "failure_reason": "Yetki hatası",
                "suggested_fix": "Kullanıcı veya servis hesabına gerekli izinleri tanımlayın.",
                "ai_provider": "rule-based",
            }
        if "authentication" in message or "auth" in message:
            return {
                "failure_reason": "Kimlik doğrulama başarısız",
                "suggested_fix": "Kimlik doğrulama bilgilerini ve token geçerliliğini kontrol edin.",
                "ai_provider": "rule-based",
            }
        if "assertion" in message:
            return {
                "failure_reason": "Beklenen koşul sağlanamadı",
                "suggested_fix": "Testteki beklenen değerleri veya uygulama mantığını gözden geçirin.",
                "ai_provider": "rule-based",
            }

        return {
            "failure_reason": "Hata mesajını inceleyerek detaylı kök neden analizi yapın.",
            "suggested_fix": "İlgili log kayıtlarını ve stack trace'i kontrol edin.",
            "ai_provider": "rule-based",
        }


# Dosyanın sonunda singleton instance oluştur
ai_analyzer = AIAnalyzer()


def _normalise_language(language: str) -> str:
    language = (language or "").strip().lower()
    if language in SECTION_LANGUAGE_STRINGS:
        return language
    return "tr"


def _ensure_text_string(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8", errors="ignore")
        except Exception:  # pragma: no cover - defensive decode
            return value.decode("latin-1", errors="ignore")
    return str(value)


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _summarise_sentences(text: str, max_sentences: int = 3, max_chars: int = 600) -> str:
    cleaned = _clean_text(text)
    if not cleaned:
        return ""
    sentences = re.split(r"(?<=[.!?])\s+", cleaned)
    if not sentences:
        summary = cleaned[:max_chars]
    else:
        summary = " ".join(sentences[:max_sentences])
    if len(summary) > max_chars:
        summary = summary[:max_chars].rstrip() + "..."
    return summary


def _extract_list_items(text: str) -> List[str]:
    items: List[str] = []
    for line in (text or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        stripped = re.sub(r"^[\-•*·●◦0-9\)\(\.\s]+", "", stripped).strip()
        if len(stripped) < 3:
            continue
        items.append(stripped)
    return items


def _format_prompt(template: str, text: str) -> str:
    return textwrap.dedent(template).strip().format(text=text.strip())


def _request_section_analysis(prompt: str, max_tokens: int = 700) -> Optional[str]:
    return ai_analyzer.request_text_completion(prompt, max_tokens=max_tokens)


def _no_data_message(section: str, language: str) -> str:
    language = _normalise_language(language)
    defaults = SECTION_LANGUAGE_STRINGS.get(language, {})
    key_map = {
        "test_conditions": "no_test_conditions",
        "graphs": "no_graphs",
        "results": "no_results",
        "detailed_data": "no_detailed",
    }
    return defaults.get(key_map.get(section, ""), "") or ""


TEST_CONDITION_PROMPTS = {
    "tr": """
Aşağıdaki test koşulları metnini analiz et ve şu bilgileri Türkçe ver:

1. Hangi test standardı kullanılmış? (örn: UN-R80, ECE-R)
2. Test edilen cihaz/araç nedir?
3. Test ortamı ve koşulları nelerdir?
4. Ölçüm yöntemleri nelerdir?

Kısa ve öz, maksimum 200 kelime.

{text}
""",
    "en": """
Analyse the following test conditions in English and answer:
1. Which standards are referenced (e.g. UN-R80, ECE-R)?
2. Which device or system was evaluated?
3. What are the environmental or laboratory conditions?
4. Which measurement methods or instruments were used?

Respond in at most 200 words.

{text}
""",
    "de": """
Analysiere die folgenden Prüfbedingungen auf Deutsch:
1. Welche Normen werden erwähnt (z. B. UN-R80, ECE-R)?
2. Welches Gerät oder System wurde geprüft?
3. Welche Umgebungs- oder Laborbedingungen liegen vor?
4. Welche Messmethoden oder Instrumente wurden verwendet?

Antwort in höchstens 200 Wörtern.

{text}
""",
}


GRAPH_PROMPTS = {
    "tr": """
Bu metin grafikler veya diyagramlardan bahsediyor mu?

Eğer bahsediyorsa:
- Her grafiğin konusunu belirt
- Grafikte ne tür veriler gösterilmiş?
- Grafikteki temel bulgu nedir?

Eğer bahsetmiyorsa: "Grafikler hakkında açık bilgi yok" de.

Maksimum 150 kelime, Türkçe.

{text}
""",
    "en": """
Review the section and summarise any references to charts or figures.
If charts exist, describe their focus, displayed metrics and main insights.
If not, state that there is no explicit chart information.
Answer in English, maximum 150 words.

{text}
""",
    "de": """
Untersuche den Abschnitt auf Hinweise zu Diagrammen oder Abbildungen.
Wenn vorhanden, beschreibe Thema, dargestellte Messgrößen und zentrale Aussage.
Falls nicht vorhanden, erwähne ausdrücklich, dass keine Diagramminformation vorliegt.
Antwort auf Deutsch, maximal 150 Wörter.

{text}
""",
}


RESULT_PROMPTS = {
    "tr": """
Test sonuçlarını detaylı analiz et:
1. Kaç test yapılmış?
2. Her testin amacı nedir?
3. Ölçülen değerler ve birimler nelerdir?
4. Başarı/başarısızlık kriterleri nelerdir?
5. Genel değerlendirme

Tablo formatında düzenle, Türkçe, maksimum 300 kelime.

{text}
""",
    "en": """
Provide a detailed analysis of the test results in English:
1. How many tests are listed?
2. What is the purpose of each test?
3. Which measurements and units are mentioned?
4. What are the pass/fail criteria?
5. Give an overall assessment.

Format the answer as a table, maximum 300 words.

{text}
""",
    "de": """
Analysiere die Testergebnisse im Detail:
1. Wie viele Tests werden genannt?
2. Welches Ziel verfolgt jeder Test?
3. Welche Messwerte und Einheiten werden erwähnt?
4. Welche Kriterien entscheiden über Bestehen/Nichtbestehen?
5. Gesamteinschätzung

Stelle die Antwort als Tabelle dar, maximal 300 Wörter, auf Deutsch.

{text}
""",
}


DETAILED_DATA_PROMPTS = {
    "tr": """
Bu bölümdeki teknik verileri analiz et. Önemli ölçümler, değerler ve gözlemleri maddeler halinde özetle.
Türkçe ve 200 kelimeyi geçmesin.

{text}
""",
    "en": """
Summarise the technical data in bullet points. Highlight critical measurements, values and observations.
Reply in English, no more than 200 words.

{text}
""",
    "de": """
Fasse die technischen Daten stichpunktartig zusammen. Hebe wichtige Messungen, Werte und Beobachtungen hervor.
Antwort auf Deutsch, maximal 200 Wörter.

{text}
""",
}


def analyze_test_conditions(
    text: str,
    structured_data: Optional[Dict[str, object]] = None,
    format_type: str = "generic",
    language: str = "tr",
) -> str:
    """Test koşulları analizi - Format-aware"""

    raw_text = (text or "").strip()
    structured_snippet = ""

    if structured_data:
        try:
            structured_snippet = format_structured_data_for_ai(structured_data) or ""
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("structured_data format error: %s", exc)

    combined_text = raw_text
    if structured_snippet and structured_snippet not in combined_text:
        combined_text = f"{raw_text}\n\n{structured_snippet}".strip()

    if not combined_text or len(combined_text) < 30:
        return "Test koşulları hakkında yeterli bilgi yok."

    if format_type == "kielt_format":
        prompt = f"""Bu TÜV test raporunun koşullarını ÖZ OL (Türkçe, maks. 100 kelime):

{combined_text[:1200]}

Sadece şunları yaz:
- Test standardı (UN-R veya ECE-R)
- Hangi araç test edildi?
- Test tarihi
- Kullanılan ölçüm sistemi

ÖRNEK:
"UN-R80 standardına göre 11.02.2022 tarihinde MAN LE kamyonunda koltuk testi yapılmıştır. KIEL INTERLINE R LE koltuğu test edilmiş, MINIdau ölçüm sistemi kullanılmıştır."

SADECE ÖZETİ YAZ, uzun açıklama yapma!
"""
    else:
        prompt = f"""Test koşullarını özetle (Türkçe, maks. 100 kelime):

{combined_text[:1200]}

Test standardı, test edilen cihaz, tarih ve ölçüm yöntemini belirt.
"""

    logger.info("AI'ya test koşulları gönderiliyor (format: %s)", format_type)

    analyzer = ai_analyzer
    analyzer._refresh_configuration()
    provider = (analyzer.provider or "none").lower()

    try:
        if provider == "none":
            return _extract_basic_info(combined_text)

        if provider in {"claude", "both"} and analyzer.claude_client:
            try:
                result = _call_claude_for_analysis(prompt)
                if result and len(result) > 40:
                    return result
            except Exception as exc:
                logger.error("Claude API hatası: %s", exc, exc_info=True)
                if provider == "claude":
                    return _extract_basic_info(combined_text)

        if provider in {"chatgpt", "both"} and analyzer.openai_client:
            try:
                result = _call_openai_for_analysis(prompt)
                if result and len(result) > 40:
                    return result
            except Exception as exc:
                logger.error("OpenAI API hatası: %s", exc, exc_info=True)
                if provider == "chatgpt":
                    return _extract_basic_info(combined_text)

        return _extract_basic_info(combined_text)

    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Test koşulları analiz hatası: %s", exc)
        return _extract_basic_info(combined_text)


def analyze_graphs(
    text: str,
    tables: Optional[Sequence[Dict[str, object]]] = None,
    measurement_params: Optional[Sequence[Dict[str, object]]] = None,
    language: str = "tr",
) -> str:
    """Grafik analizi - GERÇEK FORMATA GÖRE"""

    from pdf_format_detector import format_measurement_params_for_ai

    analyzer = ai_analyzer
    analyzer._refresh_configuration()

    text = _ensure_text_string(text)
    measurement_params = list(measurement_params or [])

    if measurement_params:
        logger.info("Measurement params bulundu: %s grup", len(measurement_params))

        formatted_params = format_measurement_params_for_ai(measurement_params)

        prompt = f"""Bu test raporundaki ölçüm verilerini özetle (Türkçe, maks. 120 kelime):

{formatted_params}

{text[:500] if text else ''}

GÖREVİN:
Her parametreyi listele: isim, değer, birim.

ÖRNEK YANIT:
"Baş ivmesi 58.15 g ve 64.72 g olarak ölçülmüştür.
Göğüs ivmesi (ThAC) 18.4 g ve 18.27 g seviyesindedir.
Sağ femur kuvveti 4.40 kN, sol femur kuvveti 4.82 kN'dur."

SADECE ÖZETİ YAZ!
"""

        logger.info("AI'ya measurement params gönderiliyor...")

        try:
            provider = (analyzer.provider or "none").lower()

            if provider != "none":
                if provider in {"claude", "both"} and analyzer.claude_client:
                    result = _call_claude_for_analysis(prompt)
                    if result and len(result) > 50:
                        logger.info("Claude yanıtı alındı: %s karakter", len(result))
                        return result

                if provider in {"chatgpt", "both"} and analyzer.openai_client:
                    result = _call_openai_for_analysis(prompt)
                    if result and len(result) > 50:
                        logger.info("OpenAI yanıtı alındı: %s karakter", len(result))
                        return result

            return _format_params_fallback(measurement_params)

        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("AI hatası: %s", exc)
            return _format_params_fallback(measurement_params)

    elif text and len(text) > 100:
        logger.warning("Measurement params yok, text analiz ediliyor")
        return "Ölçüm verileri parse edildi ancak detaylı değerler çıkarılamadı. PDF formatını kontrol edin."

    else:
        logger.warning("Grafik analizi için veri yok")
        return "Grafik veya ölçüm verisi bulunamadı."


def _format_params_fallback(params: Sequence[Dict[str, object]]) -> str:
    """Fallback: Parametreleri basit formatta göster"""

    if not params:
        return "Ölçüm parametreleri tespit edilemedi."

    lines: List[str] = []
    for param in params:
        name = param.get("name", "Parametre")
        unit = param.get("unit", "")
        values = list(param.get("values") or [])[:3]
        values_str = ", ".join(str(v) for v in values)
        if unit:
            lines.append(f"{name}: {values_str} {unit}")
        else:
            lines.append(f"{name}: {values_str}")

    return "Tespit edilen ölçümler:\n" + "\n".join(lines)


def _call_claude_for_analysis(prompt: str) -> str:
    """Call Claude for a plain-text analysis response."""

    analyzer = ai_analyzer
    client = analyzer.claude_client
    if not client:
        raise RuntimeError("Claude client is not configured")

    try:
        if hasattr(client, "with_options"):
            client = client.with_options(timeout=analyzer.timeout)
        message = client.messages.create(
            model=analyzer.claude_model,
            max_tokens=analyzer.max_tokens,
            messages=[{"role": "user", "content": prompt}],
            timeout=analyzer.timeout,
        )

        response_text = ""
        if getattr(message, "content", None):
            response_text = "".join(
                getattr(block, "text", "") for block in message.content if getattr(block, "text", "")
            )
        response_text = (response_text or "").strip()
        logger.info("Claude yanıtı alındı: %s karakter", len(response_text))
        return response_text

    except Exception as exc:
        logger.error("Claude API hatası: %s", exc)
        raise


def _call_openai_for_analysis(prompt: str) -> str:
    """Call OpenAI for a plain-text analysis response."""

    analyzer = ai_analyzer
    client = analyzer.openai_client
    if not client:
        raise RuntimeError("OpenAI client is not configured")

    try:
        if hasattr(client, "with_options"):
            client = client.with_options(timeout=analyzer.timeout)
        response = client.chat.completions.create(
            model=analyzer.openai_model,
            messages=[
                {
                    "role": "system",
                    "content": "Sen test raporu analiz uzmanısın. Kısa ve öz analizler yaparsın.",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=analyzer.max_tokens,
            timeout=analyzer.timeout,
            temperature=0.3,
        )

        result = response.choices[0].message.content.strip() if response.choices else ""
        logger.info("OpenAI yanıtı alındı: %s karakter", len(result))
        return result

    except Exception as exc:
        logger.error("OpenAI API hatası: %s", exc)
        raise


def _extract_basic_info(text: str) -> str:
    """Fallback: extract key information with regex."""

    info: List[str] = []
    text = text or ""

    standard = re.search(r"(?:UN-R|ECE-R)\s*\d+", text)
    if standard:
        info.append(f"Test standardı: {standard.group()}")

    date = re.search(r"\d{2}\.\d{2}\.\d{4}", text)
    if date:
        info.append(f"Test tarihi: {date.group()}")

    vehicle = re.search(r"(?:Test\s*vehicle|Fahrzeug):\s*([^\n]{10,50})", text, re.IGNORECASE)
    if vehicle:
        info.append(f"Test aracı: {vehicle.group(1).strip()}")

    if info:
        return " ".join(info)

    return "Test koşulları parse edildi ancak detay çıkarılamadı."


def _extract_graph_info_enhanced(
    content: str,
    measurement_params: Sequence[Dict[str, object]] | None,
) -> str:
    """Gelişmiş fallback - measurement params kullan"""

    measurement_params = list(measurement_params or [])
    if measurement_params:
        parts: List[str] = []
        parts.append(f"{len(measurement_params)} ölçüm parametresi tespit edildi:")
        for param in measurement_params[:5]:
            name = param.get("name", "Parametre")
            unit = param.get("unit", "")
            values = param.get("values") or []
            values_preview = ", ".join(str(v) for v in values[:3])
            if unit:
                parts.append(f"- {name}: {values_preview} {unit}")
            else:
                parts.append(f"- {name}: {values_preview}")
        return " ".join(parts)

    tables_found = re.findall(r"=== SAYFA \d+ - TABLO \d+ ===", content or "")
    if tables_found:
        return f"{len(tables_found)} tablo bölümü bulundu, parametreler çıkarılamadı."

    return "Ölçüm verileri parse edildi ancak detay çıkarılamadı."


def analyze_results(text: str, language: str = "tr") -> str:
    language = _normalise_language(language)
    cleaned = (text or "").strip()
    if not cleaned:
        return _no_data_message("results", language)

    prompt = _format_prompt(RESULT_PROMPTS.get(language, RESULT_PROMPTS["tr"]), cleaned)
    response = _request_section_analysis(prompt, max_tokens=750)
    if response:
        return response.strip()

    defaults = SECTION_LANGUAGE_STRINGS[language]
    rows = _extract_list_items(cleaned)
    if not rows:
        rows = re.split(r"(?<=[.!?])\s+", cleaned)
    rows = [row.strip() for row in rows if row.strip()]
    if not rows:
        return defaults["no_results"]

    header_index = defaults["table_header_index"]
    header_detail = defaults["table_header_detail"]
    table_lines = [defaults["results_intro"], f"| {header_index} | {header_detail} |", "| --- | --- |"]
    for idx, row in enumerate(rows[:6], start=1):
        table_lines.append(f"| {idx} | {row} |")
    return "\n".join(table_lines)


def analyze_detailed_data(text: str, language: str = "tr") -> str:
    language = _normalise_language(language)
    cleaned = (text or "").strip()
    if not cleaned:
        return _no_data_message("detailed_data", language)

    prompt = _format_prompt(DETAILED_DATA_PROMPTS.get(language, DETAILED_DATA_PROMPTS["tr"]), cleaned)
    response = _request_section_analysis(prompt, max_tokens=650)
    if response:
        return response.strip()

    items = _extract_list_items(cleaned)
    if not items:
        summary = _summarise_sentences(cleaned, max_sentences=4, max_chars=800)
        if not summary:
            return _no_data_message("detailed_data", language)
        items = [summary]
    items = items[:7]
    lines = [f"- {item}" for item in items]
    return "\n".join(lines)


def _contains_failure_indicators(*texts: str) -> bool:
    haystack = " ".join(texts).lower()
    return bool(re.search(r"\b(fail|failed|failure|error|başarısız|kaldı|fehl|abweichung)\b", haystack))


def generate_comprehensive_report(
    sections_analysis: Dict[str, str],
    *,
    language: str = "tr",
    header: str = "",
) -> Dict[str, str]:
    language = _normalise_language(language)
    defaults = SECTION_LANGUAGE_STRINGS[language]

    summary_source = sections_analysis.get("summary") or header or sections_analysis.get("results") or ""
    summary = _summarise_sentences(summary_source, max_sentences=3, max_chars=600)

    test_conditions = sections_analysis.get("test_conditions", "").strip()
    graphs = sections_analysis.get("graphs", "").strip()
    results_section = sections_analysis.get("results", "").strip()
    detailed_data = sections_analysis.get("detailed_data", "").strip()

    combined_results = results_section
    detailed_summary = detailed_data or ""

    if detailed_data:
        appendix_heading = defaults["appendix"]
        if combined_results:
            combined_results = f"{combined_results}\n\n{appendix_heading}\n{detailed_data}"
        else:
            combined_results = f"{appendix_heading}\n{detailed_data}"

    if not combined_results:
        combined_results = defaults["no_results"]

    improvements: str
    if _contains_failure_indicators(results_section, detailed_data):
        improvement_items = _extract_list_items(detailed_data)[:3]
        if not improvement_items:
            improvement_items = _extract_list_items(results_section)[:3]
        if improvement_items:
            lines = [defaults["improvements_intro"]]
            lines.extend(f"- {item}" for item in improvement_items)
            improvements = "\n".join(lines)
        else:
            improvements = defaults["improvements_fail"]
    else:
        improvements = defaults["improvements_success"]

    return {
        "summary": summary,
        "test_conditions": test_conditions or defaults["no_test_conditions"],
        "graphs": graphs or defaults["no_graphs"],
        "results": combined_results,
        "detailed_data": detailed_summary or defaults["no_detailed"],
        "improvements": improvements,
        "analysis_language": language,
    }
