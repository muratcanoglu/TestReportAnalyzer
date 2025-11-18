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

const coerceNumber = (value, fallback = 0) => {
  const numberValue = Number(value);
  return Number.isFinite(numberValue) ? numberValue : fallback;
};

const normaliseStringList = (value) => {
  if (Array.isArray(value)) {
    return value.map((item) => String(item ?? "").trim()).filter(Boolean);
  }

  if (typeof value === "string") {
    const trimmed = value.trim();
    return trimmed ? [trimmed] : [];
  }

  return [];
};

const normaliseFailureList = (value) => {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.map((failure) => ({
    test_name: failure?.test_name || "Bilinmeyen Test",
    failure_reason: failure?.failure_reason || "",
    suggested_fix: failure?.suggested_fix || "",
  }));
};

const extractSummariesFromResult = (result) => {
  if (!result) {
    return [];
  }

  if (Array.isArray(result.summaries)) {
    return result.summaries;
  }

  if (Array.isArray(result.summary)) {
    return result.summary;
  }

  if (result.summary && typeof result.summary === "object") {
    return [result.summary];
  }

  return [];
};

const normaliseSummaryPayload = (summary) => {
  if (!summary || typeof summary !== "object") {
    return null;
  }

  const measurementAnalysis = summary.measurement_analysis || {};
  const measurementOverall =
    measurementAnalysis.overall_summary || summary.overall_summary || {};
  const measuredValues =
    measurementAnalysis.measured_values || summary.measured_values || {};

  const totalTests = coerceNumber(
    summary.total_tests ?? measurementOverall.total_tests ?? 0,
    0
  );
  const passedTests = coerceNumber(
    summary.passed_tests ?? measurementOverall.passed ?? measurementOverall.passed_tests,
    0
  );
  const derivedFailed = Math.max(totalTests - passedTests, 0);
  const failedTests = coerceNumber(
    summary.failed_tests ?? measurementOverall.failed ?? measurementOverall.failed_tests,
    derivedFailed
  );
  const successRate =
    typeof summary.success_rate === "number"
      ? summary.success_rate
      : typeof measurementOverall.success_rate === "number"
      ? measurementOverall.success_rate
      : totalTests
      ? Number(((passedTests / totalTests) * 100).toFixed(2))
      : 0;

  const highlights = summary.highlights?.length
    ? summary.highlights
    : normaliseStringList(measurementOverall.highlights);

  return {
    ...summary,
    highlights,
    failures: normaliseFailureList(summary.failures),
    localized_summaries: summary.localized_summaries || {},
    structured_sections: summary.structured_sections || {},
    measured_values: measuredValues,
    overall_summary: {
      ...measurementOverall,
      total_tests: totalTests,
      passed: passedTests,
      failed: failedTests,
      success_rate: successRate,
    },
  };
};

const aggregateOverallSummary = (summaries) => {
  if (!summaries.length) {
    return {};
  }

  const totals = summaries.reduce(
    (acc, item) => {
      const stats = item.overall_summary || {};
      acc.total_tests += coerceNumber(stats.total_tests ?? item.total_tests, 0);
      acc.passed += coerceNumber(stats.passed ?? item.passed_tests, 0);
      acc.failed += coerceNumber(stats.failed ?? item.failed_tests, 0);
      return acc;
    },
    { total_tests: 0, passed: 0, failed: 0 }
  );

  const successRate = totals.total_tests
    ? Number(((totals.passed / totals.total_tests) * 100).toFixed(2))
    : 0;

  return { ...totals, success_rate: successRate };
};

const pickMeasuredValuesSnapshot = (summaries) => {
  for (const summary of summaries) {
    if (summary.measured_values && Object.keys(summary.measured_values).length > 0) {
      return summary.measured_values;
    }
  }
  return {};
};

export const createAnalysisEntry = (result, context = {}) => {
  if (!result) {
    return null;
  }

  if (result.error) {
    console.error("AI Analysis Error:", result.error);
    const engineKey = context.engineKey || result.engine_key || result.engine || "unknown";
    return {
      id: Date.now(),
      timestamp: new Date().toISOString(),
      engine: resolveEngineLabel(engineKey),
      engine_key: engineKey,
      error: result.error,
      summary: "Analiz başarısız oldu. Lütfen tekrar deneyin.",
      details: result.raw_response || "Detay bulunamadı",
      summaries: [],
    };
  }

  const extractedSummaries = extractSummariesFromResult(result)
    .map(normaliseSummaryPayload)
    .filter(Boolean);

  if (!extractedSummaries.length) {
    console.warn("AI response does not include summaries", result);
    return {
      id: Date.now(),
      timestamp: new Date().toISOString(),
      engine: resolveEngineLabel(context.engineKey || result.engine_key || result.engine),
      summary: "Analiz tamamlandı ancak özet oluşturulamadı",
      message: result.message || context.message || "",
      summaries: [],
      details: result,
    };
  }

  const engineKey = context.engineKey || result.engine_key || result.engine || "chatgpt";
  const engineLabel = resolveEngineLabel(engineKey);

  return {
    id: Date.now(),
    timestamp: new Date().toISOString(),
    engine: engineLabel,
    engine_key: engineKey,
    source: context.source || "",
    message: result.message || context.message || "",
    files_analyzed: extractedSummaries.length,
    summaries: extractedSummaries,
    overall_summary: aggregateOverallSummary(extractedSummaries),
    measured_values: pickMeasuredValuesSnapshot(extractedSummaries),
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
