import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { getReportById } from "../api";

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

const normalizeAngle = (value) => {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }

  if (typeof value === "string") {
    const cleaned = value.replace("°", "").replace(",", ".").trim();
    const parsed = Number.parseFloat(cleaned);
    return Number.isFinite(parsed) ? parsed : null;
  }

  return null;
};

const LEGACY_POSITION_MAP = {
  rear: [
    { key: "hinten_links", label: "Hinten Links" },
    { key: "hinten_rechts", label: "Hinten Rechts" },
  ],
  front: [
    { key: "vorne_links", label: "Vorne Links" },
    { key: "vorne_rechts", label: "Vorne Rechts" },
  ],
};

const normalizeLegacyLehnenData = (legacyTable) => {
  if (!legacyTable || typeof legacyTable !== "object") {
    return null;
  }

  const before = typeof legacyTable.vorher === "object" ? legacyTable.vorher : {};
  const after = typeof legacyTable.nachher === "object" ? legacyTable.nachher : {};

  return Object.entries(LEGACY_POSITION_MAP).reduce(
    (acc, [groupKey, positions]) => {
      acc[groupKey] = positions
        .map(({ key, label }) => {
          const beforeAngle = before[key];
          const afterAngle = after[key];
          if (
            (beforeAngle === null || beforeAngle === undefined) &&
            (afterAngle === null || afterAngle === undefined)
          ) {
            return null;
          }
          return {
            seat: label,
            before: beforeAngle,
            after: afterAngle,
          };
        })
        .filter(Boolean);
      return acc;
    },
    { rear: [], front: [] },
  );
};

const renderLehnenWinkel = (lehnenData) => {
  if (!lehnenData || typeof lehnenData !== "object") {
    return <p>N/A</p>;
  }

  const structuredData =
    lehnenData.vorher || lehnenData.nachher
      ? normalizeLegacyLehnenData(lehnenData) || {}
      : lehnenData;

  const seatGroups = [
    { key: "rear", label: "Hintensitze" },
    { key: "front", label: "Vordersitze" },
  ];

  const hasRows = seatGroups.some(({ key }) =>
    Array.isArray(structuredData?.[key]) && structuredData[key].length > 0,
  );

  if (!hasRows) {
    return <p>N/A</p>;
  }

  const formatAngle = (value) => {
    const normalized = normalizeAngle(value);
    if (normalized === null) {
      return "N/A";
    }
    return `${normalized.toFixed(1)}°`;
  };

  const buildDelta = (entry) => {
    if (typeof entry?.delta === "number" && Number.isFinite(entry.delta)) {
      return entry.delta;
    }
    const before = normalizeAngle(entry?.before);
    const after = normalizeAngle(entry?.after);
    if (before === null || after === null) {
      return null;
    }
    return after - before;
  };

  const deltaClassName = (delta) => {
    if (delta === null) {
      return "";
    }
    if (delta > 0) {
      return "delta-positive";
    }
    if (delta < 0) {
      return "delta-negative";
    }
    return "delta-neutral";
  };

  const renderSeatGroup = (groupKey, label) => {
    const entries = Array.isArray(structuredData?.[groupKey]) ? structuredData?.[groupKey] ?? [] : [];
    if (entries.length === 0) {
      return null;
    }

    return (
      <div key={groupKey} className="angles-group">
        <h5>{label}</h5>
        <table className="angles-table">
          <thead>
            <tr>
              <th>Sitzposition</th>
              <th>Vorher</th>
              <th>Nachher</th>
              <th>Δ</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((entry, idx) => {
              const delta = buildDelta(entry);
              const formattedDelta =
                delta === null ? "N/A" : `${delta > 0 ? "+" : ""}${delta.toFixed(1)}°`;
              return (
                <tr key={`${groupKey}-${entry?.seat || entry?.position || idx}`}>
                  <td>{entry?.seat || entry?.position || `Position ${idx + 1}`}</td>
                  <td>{formatAngle(entry?.before)}</td>
                  <td>{formatAngle(entry?.after)}</td>
                  <td className={deltaClassName(delta)}>{formattedDelta}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    );
  };

  return <div className="lehnen-winkel-groups">{seatGroups.map(({ key, label }) => renderSeatGroup(key, label))}</div>;
};

function ReportDetail() {
  const { id } = useParams();
  const [report, setReport] = useState(null);
  const [detailedAnalysis, setDetailedAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

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
    page2MetadataRaw && typeof page2MetadataRaw === "object" && !Array.isArray(page2MetadataRaw)
      ? page2MetadataRaw
      : null;
  const disallowedStatuses = new Set(["parser_not_available", "no_data_extracted", "error"]);
  const page2Status = page2Metadata?.status;
  const metadataKeys = page2Metadata ? Object.keys(page2Metadata) : [];
  const nonStatusKeys = metadataKeys.filter((key) => key !== "status");
  const hasNonEmptyData = nonStatusKeys.some((key) => {
    const value = page2Metadata?.[key];
    if (value === null || value === undefined) {
      return false;
    }
    if (typeof value === "string") {
      return Boolean(value.trim());
    }
    if (typeof value === "object") {
      return Object.keys(value).length > 0;
    }
    return true;
  });
  const normalizedStatus =
    typeof page2Status === "string" ? page2Status.toLowerCase() : page2Status;
  const shouldRenderPage2 =
    !!page2Metadata && hasNonEmptyData && !disallowedStatuses.has(normalizedStatus);

  const prueflingData =
    shouldRenderPage2 && page2Metadata?.pruefling && typeof page2Metadata.pruefling === "object"
      ? page2Metadata.pruefling
      : null;
  const pruefergebnisData =
    shouldRenderPage2 && page2Metadata?.pruefergebnis && typeof page2Metadata.pruefergebnis === "object"
      ? page2Metadata.pruefergebnis
      : null;
  const lehnenWinkelData = (() => {
    if (!shouldRenderPage2) {
      return null;
    }
    if (page2Metadata?.lehnen_winkel && typeof page2Metadata.lehnen_winkel === "object") {
      return page2Metadata.lehnen_winkel;
    }
    if (
      page2Metadata?.lehnen_winkel_table &&
      typeof page2Metadata.lehnen_winkel_table === "object"
    ) {
      return page2Metadata.lehnen_winkel_table;
    }
    return null;
  })();

  const prueflingSection = renderPruefling(prueflingData);
  const pruefergebnisSection = renderPruefergebnis(pruefergebnisData);
  const lehnenWinkelSection = renderLehnenWinkel(lehnenWinkelData);

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

      {shouldRenderPage2 && (
        <div className="page-2-metadata">
          <h3>Page 2 Metadata</h3>

          <div className="detail-section">
            <h4>Customer Information</h4>
            <p>
              <strong>Auftraggeber:</strong> {displayValue(page2Metadata?.auftraggeber)}
            </p>
          </div>

          <div className="detail-section">
            <h4>Test Participants</h4>
            <p>
              <strong>Anwesende:</strong> {displayValue(page2Metadata?.anwesende)}
            </p>
          </div>

          <div className="detail-section">
            <h4>Test Conditions</h4>
            <ul>
              {[
                ["Versuchsbedingungen", page2Metadata?.versuchsbedingungen],
                ["Justierung/Kontrolle", page2Metadata?.justierung_kontrolle],
                ["Schlittenverzögerung", page2Metadata?.schlittenverzoegerung],
                ["Examiner", page2Metadata?.examiner],
                ["Testfahrzeug", page2Metadata?.testfahrzeug],
              ].map(([label, value]) => (
                <li key={label}>
                  <strong>{label}:</strong> {displayValue(value)}
                </li>
              ))}
            </ul>
          </div>

          <div className="detail-section">
            <h4>Test Sample</h4>
            {prueflingSection}
          </div>

          <div className="detail-section">
            <h4>Test Results</h4>
            {pruefergebnisSection}
          </div>

          <div className="detail-section">
            <h4>Backrest Angles</h4>
            {lehnenWinkelSection}
          </div>
        </div>
      )}
    </div>
  );
}

export default ReportDetail;
