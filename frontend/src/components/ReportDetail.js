import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { getReportById } from "../api";

function ReportDetail() {
  const { id } = useParams();
  const [report, setReport] = useState(null);
  const [detailedAnalysis, setDetailedAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const displayValue = (value) => {
    if (value === null || value === undefined) {
      return "N/A";
    }
    if (typeof value === "string") {
      const trimmed = value.trim();
      return trimmed || "N/A";
    }
    return String(value);
  };

  const renderPruefling = (pruefling) => {
    if (!pruefling || typeof pruefling !== "object") {
      return <p>N/A</p>;
    }

    const baseFields = [
      ["Bezeichnung", pruefling.bezeichnung],
      ["Hersteller", pruefling.hersteller],
      ["Typ", pruefling.typ],
      ["Seriennummer", pruefling.seriennummer],
      ["Baujahr", pruefling.baujahr],
      ["Gewicht", pruefling.gewicht],
    ];

    const mountSections = [
      { key: "hinten_montiert", label: "Hinten montiert" },
      { key: "vorne_montiert", label: "Vorne montiert" },
    ];

    const hasMountData = (data) =>
      data &&
      typeof data === "object" &&
      Object.values(data).some((value) => {
        if (value === null || value === undefined) {
          return false;
        }
        if (typeof value === "string") {
          return Boolean(value.trim());
        }
        return true;
      });

    return (
      <div>
        <ul>
          {baseFields.map(([label, value]) => (
            <li key={label}>
              <strong>{label}:</strong> {displayValue(value)}
            </li>
          ))}
        </ul>
        {mountSections.map(({ key, label }) => {
          const mountData = pruefling[key];
          if (!hasMountData(mountData)) {
            return null;
          }

          return (
            <div key={key} className="nested-section">
              <h5>{label}</h5>
              <ul>
                {Object.entries(mountData).map(([subKey, subValue]) => (
                  <li key={subKey}>
                    <strong>{subKey.replace(/_/g, " ")}:</strong> {displayValue(subValue)}
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>
    );
  };

  const renderPruefergebnis = (pruefergebnis) => {
    if (!pruefergebnis || typeof pruefergebnis !== "object") {
      return <p>N/A</p>;
    }

    const statusColor = (value) => {
      if (!value || typeof value !== "string") {
        return "inherit";
      }
      const lowered = value.toLowerCase();
      if (lowered.includes("n.i.o") || lowered.includes("nio")) {
        return "#dc2626";
      }
      if (lowered.includes("i.o")) {
        return "#16a34a";
      }
      return "inherit";
    };

    const rows = [
      { label: "Ergebnis", value: pruefergebnis.ergebnis },
      { label: "Freigabe", value: pruefergebnis.freigabe },
      { label: "Prüfer", value: pruefergebnis.pruefer },
      { label: "Datum", value: pruefergebnis.datum },
    ];

    const dummy = pruefergebnis.dummypruefung;
    const hasDummy =
      dummy &&
      typeof dummy === "object" &&
      Object.values(dummy).some((value) => (typeof value === "string" ? value.trim() : value));

    return (
      <div>
        <ul>
          {rows.map(({ label, value }) => (
            <li key={label}>
              <strong>{label}:</strong>{" "}
              <span style={{ color: statusColor(value) }}>{displayValue(value)}</span>
            </li>
          ))}
        </ul>
        {hasDummy && (
          <div className="nested-section">
            <h5>Dummyprüfung</h5>
            <ul>
              {Object.entries(dummy).map(([subKey, subValue]) => (
                <li key={subKey}>
                  <strong>{subKey.replace(/_/g, " ")}:</strong> {displayValue(subValue)}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    );
  };

  const renderLehnenWinkel = (lehnenTable) => {
    if (!lehnenTable || typeof lehnenTable !== "object") {
      return <p>N/A</p>;
    }

    const positions = [
      { key: "hinten_links", label: "Hinten Links" },
      { key: "hinten_rechts", label: "Hinten Rechts" },
      { key: "vorne_links", label: "Vorne Links" },
      { key: "vorne_rechts", label: "Vorne Rechts" },
    ];

    const vorher = (lehnenTable.vorher || {});
    const nachher = (lehnenTable.nachher || {});

    const formatAngle = (value) => {
      if (value === null || value === undefined) {
        return "N/A";
      }
      if (typeof value === "number") {
        return `${value.toFixed(1)}°`;
      }
      return `${value}°`;
    };

    const deltaValue = (before, after) => {
      if (typeof before !== "number" || typeof after !== "number") {
        return "N/A";
      }
      const delta = after - before;
      return `${delta.toFixed(1)}°`;
    };

    return (
      <table className="angles-table">
        <thead>
          <tr>
            <th>Position</th>
            <th>Vorher</th>
            <th>Nachher</th>
            <th>Δ</th>
          </tr>
        </thead>
        <tbody>
          {positions.map(({ key, label }) => (
            <tr key={key}>
              <td>{label}</td>
              <td>{formatAngle(vorher[key])}</td>
              <td>{formatAngle(nachher[key])}</td>
              <td>{deltaValue(vorher[key], nachher[key])}</td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  };

  useEffect(() => {
    const fetchData = async () => {
      try {
        const reportData = await getReportById(id);
        setReport(reportData.report);
        setDetailedAnalysis(reportData.detailed_analysis);
      } catch (err) {
        console.error("Hata:", err);
        setError("Rapor detayları alınamadı.");
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [id]);

  if (loading) {
    return <div>Yükleniyor...</div>;
  }

  if (error) {
    return <div className="error-text">{error}</div>;
  }

  if (!report) {
    return <div>Rapor bulunamadı.</div>;
  }

  const page2MetadataRaw = report.structured_data?.page_2_metadata;
  const page2Metadata =
    page2MetadataRaw && typeof page2MetadataRaw === "object" ? page2MetadataRaw : {};
  const prueflingData =
    page2Metadata.pruefling && typeof page2Metadata.pruefling === "object"
      ? page2Metadata.pruefling
      : null;
  const pruefergebnisData =
    page2Metadata.pruefergebnis && typeof page2Metadata.pruefergebnis === "object"
      ? page2Metadata.pruefergebnis
      : null;
  const lehnenWinkelData =
    page2Metadata.lehnen_winkel_table && typeof page2Metadata.lehnen_winkel_table === "object"
      ? page2Metadata.lehnen_winkel_table
      : null;

  return (
    <div className="report-detail">
      <div className="summary-card">
        <h2>{report.filename}</h2>
        <p>Tarih: {new Date(report.upload_date).toLocaleString("tr-TR")}</p>
        <p>
          Toplam: {report.total_tests}, Başarılı: {report.passed_tests}, Başarısız: {report.failed_tests}
        </p>
      </div>

      {detailedAnalysis?.test_conditions && (
        <div className="analysis-card">
          <h3>📋 Test Koşulları</h3>
          <p className="ai-summary">{detailedAnalysis.test_conditions}</p>
          {detailedAnalysis.test_conditions.length < 50 && (
            <small style={{ color: "#999" }}>
              ⚠️ Analiz eksik - backend log'larını kontrol edin
            </small>
          )}
        </div>
      )}

      {detailedAnalysis?.graphs && (
        <div className="analysis-card">
          <h3>📊 Grafik ve Ölçüm Verileri</h3>
          <p className="ai-summary">{detailedAnalysis.graphs}</p>
          {detailedAnalysis.graphs.includes("bulunamadı") && (
            <small style={{ color: "#f59e0b" }}>
              ⚠️ Grafik verisi parse edilemedi
            </small>
          )}
        </div>
      )}

      <div className="tests-section">
        <h3>Test Sonuçları</h3>
        {report.tests && report.tests.length > 0 ? (
          report.tests.map((test, idx) => (
            <div key={idx} className={`test-item ${test.status.toLowerCase()}`}>
              <strong>{test.name || test.test_name || `Test ${idx + 1}`}</strong>
              <span className={`badge-${test.status.toLowerCase()}`}>
                {test.status === "PASS" ? "✓ Başarılı" : "✗ Başarısız"}
              </span>
              {test.status === "FAIL" && (
                <div className="test-details">
                  <p>
                    <em>Neden:</em> {test.failure_reason || test.error_message || "Belirtilmedi"}
                  </p>
                  <p>
                    <em>Öneri:</em> {test.suggested_fix || "Öneri sağlanmadı"}
                  </p>
                </div>
              )}
            </div>
          ))
        ) : (
          <p>Test kaydı bulunamadı.</p>
        )}
      </div>

      <div className="page-2-metadata">
        <h3>Page 2 Metadata</h3>

        <div className="detail-section">
          <h4>Customer Information</h4>
          <p>
            <strong>Auftraggeber:</strong> {displayValue(page2Metadata.auftraggeber)}
          </p>
        </div>

        <div className="detail-section">
          <h4>Test Participants</h4>
          <p>
            <strong>Anwesende:</strong> {displayValue(page2Metadata.anwesende)}
          </p>
        </div>

        <div className="detail-section">
          <h4>Test Conditions</h4>
          <ul>
            {[
              ["Versuchsbedingungen", page2Metadata.versuchsbedingungen],
              ["Justierung/Kontrolle", page2Metadata.justierung_kontrolle],
              ["Schlittenverzögerung", page2Metadata.schlittenverzoegerung],
              ["Examiner", page2Metadata.examiner],
              ["Testfahrzeug", page2Metadata.testfahrzeug],
            ].map(([label, value]) => (
              <li key={label}>
                <strong>{label}:</strong> {displayValue(value)}
              </li>
            ))}
          </ul>
        </div>

        <div className="detail-section">
          <h4>Test Sample</h4>
          {renderPruefling(prueflingData)}
        </div>

        <div className="detail-section">
          <h4>Test Results</h4>
          {renderPruefergebnis(pruefergebnisData)}
        </div>

        <div className="detail-section">
          <h4>Backrest Angles</h4>
          {renderLehnenWinkel(lehnenWinkelData)}
        </div>
      </div>
    </div>
  );
}

export default ReportDetail;
