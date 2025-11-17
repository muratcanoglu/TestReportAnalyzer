export const LANGUAGE_LABELS = {
  tr: "Türkçe",
  en: "English",
  de: "Deutsch",
};

export const SUMMARY_SECTION_LABELS = {
  tr: {
    summary: "Genel Özet",
    conditions: "Test Koşulları",
    improvements: "İyileştirme Önerileri",
    highlights: "Öne Çıkan Bulgular",
    technical: "Teknik Analiz Detayları",
    failures: "Kritik Testler",
  },
  en: {
    summary: "Summary",
    conditions: "Test Conditions",
    improvements: "Improvement Suggestions",
    highlights: "Key Highlights",
    technical: "Technical Analysis Details",
    failures: "Critical Tests",
  },
  de: {
    summary: "Zusammenfassung",
    conditions: "Testbedingungen",
    improvements: "Verbesserungsvorschläge",
    highlights: "Wesentliche Erkenntnisse",
    technical: "Technische Analyse",
    failures: "Kritische Tests",
  },
};

export const STRUCTURED_SECTION_LABELS = {
  tr: {
    graphs: "Grafikler",
    conditions: "Test Koşulları",
    results: "Sonuçlar",
    comments: "Uzman Notları",
  },
  en: {
    graphs: "Graphs",
    conditions: "Test Conditions",
    results: "Results",
    comments: "Expert Notes",
  },
  de: {
    graphs: "Diagramme",
    conditions: "Testbedingungen",
    results: "Ergebnisse",
    comments: "Expertenhinweise",
  },
};

export const COMPARISON_SECTION_LABELS = {
  tr: { overview: "Karşılaştırma Özeti", details: "Teknik Farklar" },
  en: { overview: "Comparison Overview", details: "Technical Differences" },
  de: { overview: "Vergleichsübersicht", details: "Technische Unterschiede" },
};

export const COMPARISON_EMPTY_MESSAGES = {
  tr: "Farklılık bulunamadı.",
  en: "No differing points were identified.",
  de: "Es wurden keine Unterschiede festgestellt.",
};

export const resolveEngineLabel = (engineKey) => {
  if (!engineKey) {
    return "ChatGPT";
  }

  const normalized = engineKey.toString().toLowerCase();

  if (normalized.includes("claude")) {
    return "Claude";
  }

  if (normalized.includes("gpt")) {
    return "ChatGPT";
  }

  return engineKey;
};

export const createAnalysisEntry = (result, context = {}) => {
  if (!result) {
    return null;
  }

  // Check for backend errors
  if (result.error) {
    console.error("AI Analysis Error:", result.error);
    return {
      id: Date.now(),
      timestamp: new Date().toISOString(),
      engine: context.engineKey || "unknown",
      error: result.error,
      summary: "Analiz başarısız oldu. Lütfen tekrar deneyin.",
      details: result.raw_response || "Detay bulunamadı",
    };
  }

  // Validate required fields
  if (!result.overall_summary || !result.measured_values) {
    console.warn("Incomplete AI response:", result);
    return {
      id: Date.now(),
      timestamp: new Date().toISOString(),
      engine: context.engineKey || "unknown",
      summary: result.summary || "Analiz tamamlandı ancak bazı veriler eksik",
      details: JSON.stringify(result, null, 2),
    };
  }

  // Normal processing...
  return {
    id: Date.now(),
    timestamp: new Date().toISOString(),
    engine: context.engineKey || "unknown",
    summary: result.overall_summary?.success_rate
      ? `${result.overall_summary.passed}/${result.overall_summary.total_tests} test başarılı (${result.overall_summary.success_rate})`
      : result.summary || "Analiz tamamlandı",
    details: result,
  };
};

export const formatAnalysisTimestamp = (timestamp) => {
  if (!timestamp) {
    return "";
  }

  const date = typeof timestamp === "string" ? new Date(timestamp) : timestamp;

  if (Number.isNaN(date.getTime())) {
    return "";
  }

  return date.toLocaleString("tr-TR", {
    dateStyle: "short",
    timeStyle: "short",
  });
};
