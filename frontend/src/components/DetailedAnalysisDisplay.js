import React from "react";
import "../styles/DetailedAnalysisDisplay.css";

/**
 * DetailedAnalysisDisplay Component
 *
 * Displays structured page-by-page analysis for ECE-R80 test reports
 * following the CODEX_INSTRUCTIONS.md specification.
 */
const DetailedAnalysisDisplay = ({ analysis, filename }) => {
  if (!analysis) {
    return (
      <div className="detailed-analysis-card">
        <div className="alert alert-info">
          Yapılandırılmış sayfa analizi mevcut değil.
        </div>
      </div>
    );
  }

  const {
    page_1_cover,
    page_2_conditions,
    page_3_measurements,
    page_4_sled,
    pages_5_6_photos,
    overall_summary
  } = analysis;

  return (
    <div className="detailed-analysis-card">
      <div className="detailed-analysis-header">
        <h3>📋 Yapılandırılmış Rapor Analizi</h3>
        {filename && <p className="detailed-analysis-filename">{filename}</p>}
      </div>

      {/* Overall Summary Section */}
      {overall_summary && (
        <div className="page-section overall-summary-section">
          <div className="overall-summary-header">
            <h4>🎯 Genel Özet</h4>
            <span className={`overall-status-badge ${overall_summary.overall_status === 'ALL TESTS PASSED' ? 'status-pass' : 'status-fail'}`}>
              {overall_summary.overall_status}
            </span>
          </div>
          <div className="overall-summary-stats">
            <div className="stat-item">
              <span className="stat-label">Toplam Test:</span>
              <span className="stat-value">{overall_summary.total_tests}</span>
            </div>
            <div className="stat-item stat-pass">
              <span className="stat-label">Başarılı:</span>
              <span className="stat-value">{overall_summary.passed_tests}</span>
            </div>
            <div className="stat-item stat-fail">
              <span className="stat-label">Başarısız:</span>
              <span className="stat-value">{overall_summary.failed_tests}</span>
            </div>
            <div className="stat-item">
              <span className="stat-label">Başarı Oranı:</span>
              <span className="stat-value">{overall_summary.success_rate}</span>
            </div>
          </div>
        </div>
      )}

      {/* Page 1: Cover Page */}
      {page_1_cover && (
        <div className="page-section">
          <h4>📄 Sayfa 1 - Kapak Sayfası</h4>
          <div className="page-content">
            <div className="info-grid">
              <div className="info-item">
                <span className="info-label">✓ Rapor Başlığı:</span>
                <span className="info-value">{page_1_cover.report_title}</span>
              </div>
              <div className="info-item">
                <span className="info-label">✓ Test Türü:</span>
                <span className="info-value">{page_1_cover.test_type}</span>
              </div>
              <div className="info-item">
                <span className="info-label">✓ Tam Test Türü:</span>
                <span className="info-value">{page_1_cover.test_type_full}</span>
              </div>
              <div className="info-item">
                <span className="info-label">✓ Rapor ID:</span>
                <span className="info-value highlight-value">{page_1_cover.report_id}</span>
              </div>
            </div>

            {page_1_cover.report_id_breakdown && (
              <div className="report-id-breakdown">
                <h5>Rapor ID Ayrıntıları:</h5>
                <ul className="breakdown-list">
                  <li><strong>Şirket:</strong> {page_1_cover.report_id_breakdown.company}</li>
                  <li><strong>Tip:</strong> {page_1_cover.report_id_breakdown.type}</li>
                  <li><strong>Yıl:</strong> {page_1_cover.report_id_breakdown.year}</li>
                  <li><strong>Test Numarası:</strong> {page_1_cover.report_id_breakdown.test_number}</li>
                  <li><strong>Açıklama:</strong> {page_1_cover.report_id_breakdown.description}</li>
                </ul>
              </div>
            )}

            <div className="info-grid">
              {page_1_cover.prepared_by && page_1_cover.prepared_by !== "N/A" && (
                <div className="info-item">
                  <span className="info-label">✓ Hazırlayan:</span>
                  <span className="info-value">{page_1_cover.prepared_by}</span>
                </div>
              )}
              {page_1_cover.commissioned_by && page_1_cover.commissioned_by !== "N/A" && (
                <div className="info-item">
                  <span className="info-label">✓ Sipariş Eden:</span>
                  <span className="info-value">{page_1_cover.commissioned_by}</span>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Page 2: Test Conditions */}
      {page_2_conditions && (
        <div className="page-section">
          <h4>📄 Sayfa 2 - Test Koşulları ve Metadata</h4>
          <div className="page-content">
            <div className="info-grid">
              {page_2_conditions.client && page_2_conditions.client !== "N/A" && (
                <div className="info-item">
                  <span className="info-label">✓ Müşteri (Auftraggeber):</span>
                  <span className="info-value">{page_2_conditions.client}</span>
                </div>
              )}
              {page_2_conditions.participants && page_2_conditions.participants !== "N/A" && (
                <div className="info-item">
                  <span className="info-label">✓ Katılımcılar (Anwesende):</span>
                  <span className="info-value">{page_2_conditions.participants}</span>
                </div>
              )}
              {page_2_conditions.consultant && page_2_conditions.consultant !== "N/A" && (
                <div className="info-item">
                  <span className="info-label">✓ Danışman (Sachverständiger):</span>
                  <span className="info-value">{page_2_conditions.consultant}</span>
                </div>
              )}
              <div className="info-item">
                <span className="info-label">✓ Dosya (Datei):</span>
                <span className="info-value">{page_2_conditions.file}</span>
              </div>
            </div>

            {page_2_conditions.test_conditions && (
              <div className="test-conditions-section">
                <h5>Test Koşulları (Versuchsbedingungen):</h5>
                <div className="info-grid">
                  <div className="info-item">
                    <span className="info-label">Standart:</span>
                    <span className="info-value">{page_2_conditions.test_conditions.standard}</span>
                  </div>
                  <div className="info-item">
                    <span className="info-label">Tip:</span>
                    <span className="info-value">{page_2_conditions.test_conditions.type}</span>
                  </div>
                  {page_2_conditions.test_conditions.equipment && page_2_conditions.test_conditions.equipment !== "N/A" && (
                    <div className="info-item">
                      <span className="info-label">Ekipman:</span>
                      <span className="info-value">{page_2_conditions.test_conditions.equipment}</span>
                    </div>
                  )}
                  {page_2_conditions.test_conditions.control && page_2_conditions.test_conditions.control !== "N/A" && (
                    <div className="info-item">
                      <span className="info-label">Kontrol:</span>
                      <span className="info-value">{page_2_conditions.test_conditions.control}</span>
                    </div>
                  )}
                </div>
              </div>
            )}

            <div className="info-grid">
              {page_2_conditions.test_product && page_2_conditions.test_product !== "N/A" && (
                <div className="info-item">
                  <span className="info-label">✓ Test Ürünü (Prüfling):</span>
                  <span className="info-value">{page_2_conditions.test_product}</span>
                </div>
              )}
              {page_2_conditions.test_product_name &&
                page_2_conditions.test_product_name !== "N/A" && (
                  <div className="info-item">
                    <span className="info-label">✓ Bezeichnung (Seri Adı):</span>
                    <span className="info-value">{page_2_conditions.test_product_name}</span>
                  </div>
                )}
              {page_2_conditions.test_result_summary && page_2_conditions.test_result_summary !== "N/A" && (
                <div className="info-item">
                  <span className="info-label">✓ Test Sonuç Özeti (Prüfergebnis):</span>
                  <span className="info-value">{page_2_conditions.test_result_summary}</span>
                </div>
              )}
              {page_2_conditions.test_result_details?.sharp_edges && (
                <div className="info-item">
                  <span className="info-label">✓ Kriterium “scharfe Kanten”:</span>
                  <span className="info-value">{page_2_conditions.test_result_details.sharp_edges}</span>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Page 3: Measurement Values */}
      {page_3_measurements && (
        <div className="page-section measurements-section">
          <h4>📊 Sayfa 3 - Ölçüm Değerleri (KRİTİK!)</h4>
          <div className="page-content">

            {/* Left Dummy */}
            {page_3_measurements.left_dummy && (
              <div className="dummy-section">
                <h5>📊 {page_3_measurements.left_dummy.title}</h5>
                <div className="measurements-grid">
                  {Object.entries(page_3_measurements.left_dummy).map(([key, data]) => {
                    if (key === "title" || !data || typeof data !== "object") return null;

                    return (
                      <div key={`left-${key}`} className="measurement-item">
                        <div className="measurement-header">
                          <strong>{data.description || key}</strong>
                          <span className={`measurement-status status-${data.status?.toLowerCase() || 'unknown'}`}>
                            {data.status === "PASS" ? "✅ PASS" : data.status === "FAIL" ? "❌ FAIL" : "❓ UNKNOWN"}
                          </span>
                        </div>
                        <div className="measurement-details">
                          <div className="measurement-row">
                            <span className="measurement-label">Değer:</span>
                            <span className="measurement-value highlight-value">
                              {data.value} {data.unit || ""}
                            </span>
                          </div>
                          <div className="measurement-row">
                            <span className="measurement-label">Sınır:</span>
                            <span className="measurement-value">
                              {data.limit} {data.unit || ""}
                            </span>
                          </div>
                          {data.time_range && data.time_range !== "N/A" && (
                            <div className="measurement-row">
                              <span className="measurement-label">Zaman Aralığı:</span>
                              <span className="measurement-value">{data.time_range}</span>
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Right Dummy */}
            {page_3_measurements.right_dummy && (
              <div className="dummy-section">
                <h5>📊 {page_3_measurements.right_dummy.title}</h5>
                <div className="measurements-grid">
                  {Object.entries(page_3_measurements.right_dummy).map(([key, data]) => {
                    if (key === "title" || !data || typeof data !== "object") return null;

                    return (
                      <div key={`right-${key}`} className="measurement-item">
                        <div className="measurement-header">
                          <strong>{data.description || key}</strong>
                          <span className={`measurement-status status-${data.status?.toLowerCase() || 'unknown'}`}>
                            {data.status === "PASS" ? "✅ PASS" : data.status === "FAIL" ? "❌ FAIL" : "❓ UNKNOWN"}
                          </span>
                        </div>
                        <div className="measurement-details">
                          <div className="measurement-row">
                            <span className="measurement-label">Değer:</span>
                            <span className="measurement-value highlight-value">
                              {data.value} {data.unit || ""}
                            </span>
                          </div>
                          <div className="measurement-row">
                            <span className="measurement-label">Sınır:</span>
                            <span className="measurement-value">
                              {data.limit} {data.unit || ""}
                            </span>
                          </div>
                          {data.time_range && data.time_range !== "N/A" && (
                            <div className="measurement-row">
                              <span className="measurement-label">Zaman Aralığı:</span>
                              <span className="measurement-value">{data.time_range}</span>
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Page 4: Sled Deceleration */}
      {page_4_sled && (
        <div className="page-section">
          <h4>📄 Sayfa 4 - Kızak Verileri (Sled Deceleration)</h4>
          <div className="page-content">
            <div className="info-grid">
              {page_4_sled.examiner && (
                <div className="info-item">
                  <span className="info-label">✓ İnceleyici (Examiner):</span>
                  <span className="info-value">{page_4_sled.examiner}</span>
                </div>
              )}
              {page_4_sled.test_conditions && (
                <div className="info-item">
                  <span className="info-label">✓ Test Koşulları:</span>
                  <span className="info-value">{page_4_sled.test_conditions}</span>
                </div>
              )}
              {page_4_sled.date && page_4_sled.date !== "N/A" && (
                <div className="info-item">
                  <span className="info-label">✓ Tarih:</span>
                  <span className="info-value">{page_4_sled.date}</span>
                </div>
              )}
              {page_4_sled.test_vehicle && page_4_sled.test_vehicle !== "N/A" && (
                <div className="info-item">
                  <span className="info-label">✓ Test Aracı:</span>
                  <span className="info-value">{page_4_sled.test_vehicle}</span>
                </div>
              )}
              {page_4_sled.test_seat && page_4_sled.test_seat !== "N/A" && (
                <div className="info-item">
                  <span className="info-label">✓ Test Koltuğu:</span>
                  <span className="info-value">{page_4_sled.test_seat}</span>
                </div>
              )}
              {page_4_sled.seat_belt && (
                <div className="info-item">
                  <span className="info-label">✓ Emniyet Kemeri:</span>
                  <span className="info-value">{page_4_sled.seat_belt}</span>
                </div>
              )}
              {page_4_sled.occupant && (
                <div className="info-item">
                  <span className="info-label">✓ Yolcu:</span>
                  <span className="info-value">{page_4_sled.occupant}</span>
                </div>
              )}
              {page_4_sled.sled_velocity && (
                <div className="info-item">
                  <span className="info-label">✓ Kızak Hızı:</span>
                  <span className="info-value highlight-value">{page_4_sled.sled_velocity}</span>
                </div>
              )}
            </div>
            {page_4_sled.graph_description && (
              <div className="graph-description">
                <p>✓ Grafik: {page_4_sled.graph_description}</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Pages 5-6: Photo Documentation */}
      {pages_5_6_photos && (
        <div className="page-section">
          <h4>📷 Sayfa 5-6 - Fotoğraf Dokümantasyonu</h4>
          <div className="page-content">
            <div className="photo-documentation">
              <div className="photo-info">
                <span className="photo-label">✓ Test öncesi:</span>
                <span className="photo-value">{pages_5_6_photos.pre_test}</span>
              </div>
              <div className="photo-info">
                <span className="photo-label">✓ Test sonrası:</span>
                <span className="photo-value">{pages_5_6_photos.post_test}</span>
              </div>
              <div className="photo-info">
                <span className="photo-label">✓ Toplam:</span>
                <span className="photo-value highlight-value">{pages_5_6_photos.total} fotoğraf</span>
              </div>
              {pages_5_6_photos.description && (
                <div className="photo-description">
                  <p>{pages_5_6_photos.description}</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default DetailedAnalysisDisplay;
