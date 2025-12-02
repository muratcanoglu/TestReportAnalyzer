import React, { useMemo, useState } from "react";
import { runNaturalLanguageQuery } from "../api";
import { detectReportType, getReportSummary } from "../utils/reportUtils";

const NaturalLanguageQuery = ({ reports, analysisEngine }) => {
  const [query, setQuery] = useState("");
  const [queryResult, setQueryResult] = useState("");
  const [aiResult, setAiResult] = useState("");
  const [isProcessing, setIsProcessing] = useState(false);
  const [matchedReports, setMatchedReports] = useState([]);
  const [error, setError] = useState(null);

  const schemaSummaries = useMemo(
    () =>
      reports.map((report) => {
        const pdfType = detectReportType(report);
        const total = Number(report.total_tests ?? 0);
        const passed = Number(report.passed_tests ?? 0);
        const failed = Number(report.failed_tests ?? 0);
        const successRate = total > 0 ? Math.round((passed / total) * 100) : 0;
        return {
          id: report.id,
          fileName: report.filename,
          pdfType,
          summary: getReportSummary(report),
          insights:
            total === 0
              ? "Analiz verisi bulunmuyor"
              : `Başarı oranı %${successRate}. ${failed > 0 ? `${failed} başarısız test incelenmeli.` : "Tüm testler geçti."}`,
          rawMetrics: `${passed} PASS / ${failed} FAIL / ${total} TOPLAM`,
          modelUsed: analysisEngine === "claude" ? "Claude" : "ChatGPT",
          createdAt: new Date(report.upload_date).toLocaleString(),
        };
      }),
    [reports, analysisEngine]
  );

  const buildQuerySummary = (payload) => {
    if (!payload) {
      return "";
    }

    const overview = payload.overview || {};
    const totalReports = overview.total_reports ?? reports.length;
    const baseSummary = payload.message || "";
    const filterSummary = payload.filter_summary || "";

    return [
      baseSummary,
      filterSummary,
      `Toplam ${totalReports} rapor tarandı; ${overview.matched_reports || 0} rapor ve ${
        overview.matched_tests || 0
      } test eşleşti.`,
    ]
      .filter(Boolean)
      .join("\n");
  };

  const buildAiSummary = (payload) => {
    if (!payload) {
      return "";
    }

    const engineLabel = payload.engine || (analysisEngine === "claude" ? "Claude" : "ChatGPT");
    const languageLabel = (payload.language || "tr").toUpperCase();

    return [
      `Analiz Motoru: ${engineLabel}`,
      `Sorgu Dili: ${languageLabel}`,
      payload.query ? `Sorgu: "${payload.query}"` : "",
      payload.filter_summary || "",
    ]
      .filter(Boolean)
      .join("\n");
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!query.trim()) {
      return;
    }

    setIsProcessing(true);
    setError(null);
    setMatchedReports([]);
    setQueryResult("");
    setAiResult("");

    try {
      const response = await runNaturalLanguageQuery(query, analysisEngine);
      setQueryResult(buildQuerySummary(response));
      setAiResult(buildAiSummary(response));
      setMatchedReports(response.matches || []);
    } catch (err) {
      const serverError = err?.response?.data?.error || "Sorgu çalıştırılamadı. Lütfen tekrar deneyin.";
      setError(serverError);
      setQueryResult("");
      setAiResult("");
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="natural-language-section">
      <div className="query-left">
        <div className="card">
          <h2>Sorgu Editörü</h2>
          <form className="query-form" onSubmit={handleSubmit}>
            <textarea
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="PDF içeriğinde ne aramak istersiniz?"
              rows={6}
            />
            <button className="button button-primary" type="submit" disabled={isProcessing}>
              {isProcessing ? "Sorgulanıyor..." : "Sorgula"}
            </button>
          </form>
        </div>

        <div className="card">
          <h3>Sorgu Sonuçları</h3>
          <p className="muted-text">
            Rapor içerisinden doğrudan çekilen bulgular burada gösterilir.
          </p>
          <pre className="query-output">{queryResult || "Henüz bir sorgu çalıştırılmadı."}</pre>
        </div>

        <div className="card">
          <h3>AI Raporu</h3>
          <p className="muted-text">
            Yapay zekanın değerlendirmesi ve ek yorumları bu alanda yer alır.
          </p>
          <pre className="query-output">{aiResult || "AI değerlendirmesi hazır değil."}</pre>
        </div>

        <div className="card">
          <h3>Eşleşen Raporlar</h3>
          <p className="muted-text">
            Sorgudan etkilenen rapor ve testler filtrelere göre listelenir.
          </p>
          {error && <div className="alert alert-error">{error}</div>}
          {isProcessing ? (
            <p className="muted-text">Sorgu çalıştırılıyor, lütfen bekleyin...</p>
          ) : matchedReports.length === 0 ? (
            <p className="muted-text">Henüz eşleşme bulunamadı.</p>
          ) : (
            <div className="match-grid">
              {matchedReports.map((item) => (
                <div className="match-card" key={item.report_id}>
                  <div className="match-header">
                    <div>
                      <h4>{item.filename}</h4>
                      <p className="muted-text">
                        {item.test_type_label || "Bilinmeyen"} · {new Date(item.upload_date).toLocaleDateString()}
                      </p>
                    </div>
                    <span className="badge badge-info">ID: {item.report_id}</span>
                  </div>
                  <div className="match-meta">
                    <span>Toplam: {item.total_tests || 0}</span>
                    <span className="text-success">PASS: {item.passed_tests || 0}</span>
                    <span className="text-danger">FAIL: {item.failed_tests || 0}</span>
                  </div>
                  <div className="match-tests">
                    {(item.matched_tests || []).length === 0 ? (
                      <p className="muted-text">Bu raporda listelenecek test bulunamadı.</p>
                    ) : (
                      item.matched_tests.map((test) => (
                        <div className="match-test-row" key={test.id || test.test_name}>
                          <div>
                            <strong>{test.test_name || "Bilinmeyen Test"}</strong>
                            {test.failure_reason && (
                              <p className="muted-text">Sebep: {test.failure_reason}</p>
                            )}
                            {test.suggested_fix && (
                              <p className="muted-text">Öneri: {test.suggested_fix}</p>
                            )}
                          </div>
                          <span
                            className={`status-pill ${
                              (test.status || "").toLowerCase() === "fail" ? "status-pill-danger" : "status-pill-success"
                            }`}
                          >
                            {test.status || "Bilinmiyor"}
                          </span>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="schema-explorer card">
        <h2>🌍 Genel Özet</h2>
        <p className="muted-text">
          Raporlardan çıkarılan temel alanlara hızlı bir bakış.
        </p>
        {schemaSummaries.length === 0 ? (
          <p className="muted-text">Gösterilecek rapor bulunamadı.</p>
        ) : (
          <div className="schema-card-grid">
            {schemaSummaries.map((item) => (
              <div className="schema-card" key={item.id}>
                <span className="schema-type">{item.pdfType}</span>
                <div className="schema-field">
                  <strong>ID:</strong> {item.id}
                </div>
                <div className="schema-field">
                  <strong>File Name:</strong> {item.fileName}
                </div>
                <div className="schema-field">
                  <strong>PDF Type:</strong> {item.pdfType}
                </div>
                <div className="schema-field">
                  <strong>Summary:</strong> {item.summary}
                </div>
                <div className="schema-field">
                  <strong>Insights:</strong> {item.insights}
                </div>
                <div className="schema-field">
                  <strong>Raw Metrics:</strong> {item.rawMetrics}
                </div>
                <div className="schema-field">
                  <strong>Model Used:</strong> {item.modelUsed}
                </div>
                <div className="schema-field">
                  <strong>Created at:</strong> {item.createdAt}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default NaturalLanguageQuery;
