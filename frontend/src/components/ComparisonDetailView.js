import React from "react";
import "../styles/ComparisonDetail.css";

const ComparisonDetailView = ({ comparisonData }) => {
  if (!comparisonData) return null;

  const { page_2_comparison } = comparisonData;

  if (!page_2_comparison || page_2_comparison.error) {
    return null; // Page 2 comparison not available
  }

  const renderFieldComparison = (label, fieldData) => {
    if (!fieldData) return null;

    const { first, second, identical } = fieldData;
    const statusClass = identical ? "identical" : "different";

    return (
      <tr key={label} className={statusClass}>
        <td className="field-label">{label}</td>
        <td className="field-value">{first || "-"}</td>
        <td className="field-value">{second || "-"}</td>
        <td className="field-status">
          {identical ? "✓ Aynı" : "✗ Farklı"}
        </td>
      </tr>
    );
  };

  const renderAngleComparison = () => {
    const { lehnen_winkel } = page_2_comparison;
    if (!lehnen_winkel) return null;

    return (
      <div className="angle-comparison-section">
        <h4>Lehnen-Winkel Karşılaştırması (Kritik)</h4>

        {["vorher", "nachher"].map((row) => {
          const rowData = lehnen_winkel[row];
          if (!rowData) return null;

          return (
            <div key={row} className="angle-row">
              <h5>{row === "vorher" ? "Öncesi" : "Sonrası"}</h5>
              <table className="angle-table">
                <thead>
                  <tr>
                    <th>Pozisyon</th>
                    <th>Rapor 1</th>
                    <th>Rapor 2</th>
                    <th>Fark</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(rowData).map(([position, data]) => {
                    const positionLabel = {
                      hinten_links: "Arka Sol",
                      hinten_rechts: "Arka Sağ",
                      vorne_links: "Ön Sol",
                      vorne_rechts: "Ön Sağ"
                    }[position] || position;

                    const diffClass = data.identical ? "identical" : "different-critical";

                    return (
                      <tr key={position} className={diffClass}>
                        <td>{positionLabel}</td>
                        <td>{data.first !== null ? `${data.first}°` : "-"}</td>
                        <td>{data.second !== null ? `${data.second}°` : "-"}</td>
                        <td>
                          {data.difference !== null
                            ? `${data.difference.toFixed(2)}°`
                            : "-"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div className="comparison-detail-view">
      <div className="comparison-summary-stats">
        <div className="stat-card">
          <span className="stat-label">Metadata Benzerliği</span>
          <span className="stat-value">{page_2_comparison.metadata_similarity}%</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Karşılaştırılan Alan</span>
          <span className="stat-value">{page_2_comparison.total_fields_compared}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Farklı Alan</span>
          <span className="stat-value critical">{page_2_comparison.different_fields}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Kritik Farklar</span>
          <span className="stat-value critical">{page_2_comparison.critical_differences}</span>
        </div>
      </div>

      <div className="comparison-sections">
        <div className="comparison-section">
          <h3>Genel Bilgiler</h3>
          <table className="comparison-table">
            <thead>
              <tr>
                <th>Alan</th>
                <th>Rapor 1</th>
                <th>Rapor 2</th>
                <th>Durum</th>
              </tr>
            </thead>
            <tbody>
              {page_2_comparison.simple_fields && Object.entries(page_2_comparison.simple_fields).map(([field, data]) => {
                const fieldLabels = {
                  auftraggeber: "Müşteri",
                  anwesende: "Katılımcılar",
                  versuchsbedingungen: "Test Koşulları",
                  examiner: "Test Sorumlusu"
                };
                return renderFieldComparison(fieldLabels[field] || field, data);
              })}
            </tbody>
          </table>
        </div>

        {renderAngleComparison()}

        <div className="comparison-section">
          <h3>Prüfling (Test Edilen Ürün)</h3>
          <table className="comparison-table">
            <thead>
              <tr>
                <th>Alan</th>
                <th>Rapor 1</th>
                <th>Rapor 2</th>
                <th>Durum</th>
              </tr>
            </thead>
            <tbody>
              {page_2_comparison.pruefling && Object.entries(page_2_comparison.pruefling).map(([field, data]) => {
                if (field === "hinten_montiert" || field === "vorne_montiert") {
                  return null; // Handle separately if needed
                }
                const fieldLabels = {
                  bezeichnung: "Tanım",
                  hersteller: "Üretici",
                  typ: "Tip"
                };
                return renderFieldComparison(fieldLabels[field] || field, data);
              })}
            </tbody>
          </table>
        </div>

        <div className="comparison-section">
          <h3>Prüfergebnis (Test Sonucu)</h3>
          <table className="comparison-table">
            <thead>
              <tr>
                <th>Alan</th>
                <th>Rapor 1</th>
                <th>Rapor 2</th>
                <th>Durum</th>
              </tr>
            </thead>
            <tbody>
              {page_2_comparison.pruefergebnis && Object.entries(page_2_comparison.pruefergebnis).map(([field, data]) => {
                if (field === "dummypruefung") return null;
                const fieldLabels = {
                  ergebnis: "Sonuç",
                  freigabe: "Onay",
                  pruefer: "Test Uzmanı",
                  datum: "Tarih"
                };
                return renderFieldComparison(fieldLabels[field] || field, data);
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default ComparisonDetailView;
