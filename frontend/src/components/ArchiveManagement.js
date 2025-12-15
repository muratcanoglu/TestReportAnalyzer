import React, { useCallback, useMemo, useState } from "react";
import {
  analyzeReportsWithAI,
  analyzeArchivedReports,
  compareReports,
  downloadReportFile,
  getReportDownloadUrl,
  uploadReport,
} from "../api";
import { resolveEngineLabel } from "../utils/analysisUtils";
import { detectReportType, getReportStatusLabel } from "../utils/reportUtils";
import AnalysisSummaryCard from "./AnalysisSummaryCard";
import { normaliseFilenameForComparison } from "../utils/fileUtils";
import ComparisonDetailView from "./ComparisonDetailView";

const deriveLaboratory = (filename = "", detectedType = "") => {
  const name = filename.toLowerCase();
  if (name.includes("concept")) {
    return "Concept Test Laboratuvarı";
  }
  if (name.includes("tse") || name.includes("türk")) {
    return "Türk Standartları Enstitüsü";
  }
  if (name.includes("gcs")) {
    return "GCS Test Laboratuvarı";
  }
  return detectedType === "R10 EMC Testi" ? "GCS Test Laboratuvarı" : "Concept Test Laboratuvarı";
};

const deriveModel = (filename = "") => {
  const name = filename.toLowerCase();
  if (name.includes("avance-x")) {
    return "Avance-X";
  }
  if (name.includes("interline")) {
    return "Interline";
  }
  if (name.includes("avance")) {
    return "Avance";
  }
  return "Avance";
};

const deriveStatusFilterValue = (statusLabel = "") => {
  if (statusLabel === "Başarılı" || statusLabel === "Başarısız") {
    return statusLabel;
  }
  if (statusLabel === "Belirsiz") {
    return "Belirsiz";
  }
  return "Belirsiz";
};

const MAX_MULTI_UPLOAD_FILES = 100;

const createFileLike = (blob, filename) => {
  const mimeType = blob?.type || "application/pdf";
  if (typeof File === "function") {
    return new File([blob], filename, { type: mimeType });
  }

  const fallback = new Blob([blob], { type: mimeType });
  try {
    Object.defineProperty(fallback, "name", {
      value: filename,
      configurable: true,
    });
  } catch (error) {
    // Ignore when defineProperty is not supported.
  }
  return fallback;
};

const ArchiveManagement = ({
  reports,
  analysisEngine = "chatgpt",
  analysisArchive = [],
  onRefresh,
  onAnalysisComplete,
}) => {
  const [filters, setFilters] = useState({
    startDate: "",
    endDate: "",
    testType: "",
    laboratory: "",
    model: "",
    status: "",
  });
  const [filteredReports, setFilteredReports] = useState([]);
  const [filtersApplied, setFiltersApplied] = useState(false);
  const [isArchiveCollapsed, setIsArchiveCollapsed] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [selectedArchiveIds, setSelectedArchiveIds] = useState([]);
  const [dragActive, setDragActive] = useState(false);
  const [multiUploadStatus, setMultiUploadStatus] = useState(null);
  const [isMultiUploading, setIsMultiUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState({ processed: 0, total: 0 });
  const [archiveActionFeedback, setArchiveActionFeedback] = useState(null);
  const [archiveComparisonResult, setArchiveComparisonResult] = useState(null);
  const [isArchiveProcessing, setIsArchiveProcessing] = useState(false);
  const [isArchiveComparing, setIsArchiveComparing] = useState(false);

  const existingFilenames = useMemo(() => {
    return new Set(
      reports
        .map((report) => normaliseFilenameForComparison(report?.filename))
        .filter(Boolean)
    );
  }, [reports]);

  const enrichedReports = useMemo(
    () =>
      reports.map((report) => {
        const detectedType = detectReportType(report);
        const displayTestType =
          report.test_standard?.trim() || report.test_type_label || detectedType;
        const laboratory = report.lab_name?.trim()
          ? report.lab_name
          : deriveLaboratory(report.filename ?? "", detectedType);
        const uploadDate = report.upload_date ? new Date(report.upload_date) : null;
        return {
          ...report,
          detectedType,
          displayTestType,
          uploadDate,
          laboratory,
          model: deriveModel(report.filename ?? ""),
          statusLabel: getReportStatusLabel(report),
        };
      }),
    [reports]
  );

  const reportsWithStatus = useMemo(
    () =>
      enrichedReports.map((report) => ({
        ...report,
        statusFilterValue: deriveStatusFilterValue(report.statusLabel),
      })),
    [enrichedReports]
  );

  const archiveSummary = useMemo(() => {
    const summary = {
      r10: 0,
      r80: 0,
      unknown: 0,
    };

    reportsWithStatus.forEach((report) => {
      if (report.detectedType === "R10 EMC Testi") {
        summary.r10 += 1;
      } else if (report.detectedType === "R80 Darbe Testi") {
        summary.r80 += 1;
      } else {
        summary.unknown += 1;
      }
    });

    return summary;
  }, [reportsWithStatus]);

  const sortedReports = useMemo(() => {
    return [...reportsWithStatus].sort(
      (a, b) => (b.uploadDate?.getTime() ?? 0) - (a.uploadDate?.getTime() ?? 0)
    );
  }, [reportsWithStatus]);

  const engineLabel = useMemo(() => resolveEngineLabel(analysisEngine), [analysisEngine]);

  const matchesDateRange = (report) => {
    if (!report.uploadDate) {
      return false;
    }

    if (filters.startDate) {
      const start = new Date(filters.startDate);
      if (report.uploadDate < start) {
        return false;
      }
    }

    if (filters.endDate) {
      const end = new Date(filters.endDate);
      end.setHours(23, 59, 59, 999);
      if (report.uploadDate > end) {
        return false;
      }
    }

    return true;
  };

  const applyFilters = () => {
    const results = reportsWithStatus.filter((report) => {
      if (filters.startDate || filters.endDate) {
        if (!matchesDateRange(report)) {
          return false;
        }
      }

      if (filters.testType && report.detectedType !== filters.testType) {
        return false;
      }

      if (filters.laboratory && report.laboratory !== filters.laboratory) {
        return false;
      }

      if (filters.model && report.model !== filters.model) {
        return false;
      }

      if (filters.status && report.statusFilterValue !== filters.status) {
        return false;
      }

      return true;
    });

    results.sort(
      (a, b) => (b.uploadDate?.getTime() ?? 0) - (a.uploadDate?.getTime() ?? 0)
    );

    setFilteredReports(results);
    setFiltersApplied(true);
  };

  const clearFilters = () => {
    setFilters({
      startDate: "",
      endDate: "",
      testType: "",
      laboratory: "",
      model: "",
      status: "",
    });
    setFilteredReports([]);
    setFiltersApplied(false);
  };

  const handleFilesAdded = useCallback(
    (fileList) => {
      const incomingFiles = Array.from(fileList ?? []);
      if (incomingFiles.length === 0) {
        return;
      }

      const pdfFiles = incomingFiles.filter(
        (file) => file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf")
      );

      if (pdfFiles.length === 0) {
        setMultiUploadStatus({ type: "error", message: "Lütfen sadece PDF dosyaları seçin." });
        return;
      }

      const availableSlots = MAX_MULTI_UPLOAD_FILES - selectedFiles.length;
      if (availableSlots <= 0) {
        setMultiUploadStatus({
          type: "warning",
          message: `En fazla ${MAX_MULTI_UPLOAD_FILES} adet PDF yükleyebilirsiniz.`,
        });
        return;
      }

      const limitedFiles = pdfFiles.slice(0, availableSlots);
      const existingNameSet = new Set(
        selectedFiles.map((file) => normaliseFilenameForComparison(file?.name)).filter(Boolean)
      );
      const acceptedFiles = [];
      let duplicateDetected = false;

      limitedFiles.forEach((file) => {
        const normalized = normaliseFilenameForComparison(file?.name);
        if (normalized && (existingFilenames.has(normalized) || existingNameSet.has(normalized))) {
          duplicateDetected = true;
          return;
        }
        existingNameSet.add(normalized);
        acceptedFiles.push(file);
      });

      if (acceptedFiles.length > 0) {
        setSelectedFiles([...selectedFiles, ...acceptedFiles]);
      }

      let status = null;
      if (duplicateDetected) {
        status = { type: "error", message: "Bu rapor daha önce arşivlendi." };
      } else if (pdfFiles.length > availableSlots) {
        status = {
          type: "warning",
          message: `En fazla ${MAX_MULTI_UPLOAD_FILES} adet PDF yükleyebilirsiniz.`,
        };
      } else if (acceptedFiles.length === 0) {
        status = { type: "warning", message: "Yeni PDF dosyası eklenemedi." };
      }

      setMultiUploadStatus(status);
    },
    [existingFilenames, selectedFiles]
  );

  const handleFileInputChange = useCallback(
    (event) => {
      handleFilesAdded(event.target.files);
      event.target.value = "";
    },
    [handleFilesAdded]
  );

  const handleDrag = useCallback((event) => {
    event.preventDefault();
    event.stopPropagation();

    if (event.type === "dragenter" || event.type === "dragover") {
      setDragActive(true);
    } else if (event.type === "dragleave") {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback(
    (event) => {
      event.preventDefault();
      event.stopPropagation();
      setDragActive(false);
      handleFilesAdded(event.dataTransfer?.files);
    },
    [handleFilesAdded]
  );

  const handleRemoveFile = useCallback((index) => {
    setSelectedFiles((previous) => previous.filter((_, idx) => idx !== index));
  }, []);

  const handleClearSelectedFiles = useCallback(() => {
    setSelectedFiles([]);
    setMultiUploadStatus(null);
  }, []);

  const handleBulkUpload = useCallback(async () => {
    if (selectedFiles.length === 0) {
      setMultiUploadStatus({ type: "error", message: "Lütfen en az bir PDF dosyası seçin." });
      return;
    }

    setIsMultiUploading(true);
    setUploadProgress({ processed: 0, total: selectedFiles.length });
    setMultiUploadStatus({
      type: "info",
      message: `${selectedFiles.length} rapor yükleniyor...`,
    });

    let successCount = 0;
    let failureCount = 0;
    let firstErrorMessage = "";

    for (let index = 0; index < selectedFiles.length; index += 1) {
      const file = selectedFiles[index];
      try {
        await uploadReport(file, analysisEngine);
        successCount += 1;
      } catch (error) {
        failureCount += 1;
        if (!firstErrorMessage) {
          firstErrorMessage =
            error?.response?.data?.error ||
            error?.message ||
            "Yükleme sırasında bir hata oluştu. Lütfen tekrar deneyin.";
        }
      } finally {
        setUploadProgress({ processed: index + 1, total: selectedFiles.length });
      }
    }

    setIsMultiUploading(false);
    setSelectedFiles([]);
    setUploadProgress({ processed: 0, total: 0 });

    if (failureCount > 0 && successCount > 0) {
      setMultiUploadStatus({
        type: "warning",
        message: `${successCount} rapor yüklendi, ${failureCount} rapor yüklenemedi. İlk hata: ${firstErrorMessage}`,
      });
    } else if (failureCount > 0) {
      setMultiUploadStatus({
        type: "error",
        message: `Raporlar yüklenemedi. İlk hata: ${firstErrorMessage}`,
      });
    } else {
      setMultiUploadStatus({
        type: "success",
        message: `${successCount} rapor başarıyla yüklendi.`,
      });
    }

    if (successCount > 0 && typeof onRefresh === "function") {
      try {
        await onRefresh();
      } catch (error) {
        setMultiUploadStatus({
          type: "warning",
          message: "Rapor listesi güncellenemedi, lütfen sayfayı yenileyin.",
        });
      }
    }
  }, [analysisEngine, onRefresh, selectedFiles]);

  const toggleArchiveSelection = useCallback((id) => {
    setSelectedArchiveIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  }, []);

  const handleCompareSelected = useCallback(async () => {
    if (selectedArchiveIds.length < 2) {
      setArchiveActionFeedback({
        type: "warning",
        message: "Karşılaştırma için en az iki rapor seçmelisiniz.",
      });
      return;
    }

    if (selectedArchiveIds.length > 2) {
      setArchiveActionFeedback({
        type: "warning",
        message: "En Fazla 2 Adet Test Raporunu Karşılaştırma Yapabilirsiniz!",
      });
      return;
    }

    setIsArchiveComparing(true);
    setArchiveActionFeedback({
      type: "info",
      message: "Seçilen raporlar karşılaştırılıyor...",
    });

    try {
      const response = await compareReports(selectedArchiveIds);
      setArchiveComparisonResult(response);
      setArchiveActionFeedback({
        type: "success",
        message: response?.summary || "Karşılaştırma tamamlandı.",
      });
    } catch (error) {
      const message =
        error?.response?.data?.error ||
        error?.message ||
        "Karşılaştırma sırasında bir sorun oluştu. Lütfen tekrar deneyin.";
      setArchiveActionFeedback({ type: "error", message });
      setArchiveComparisonResult(null);
    } finally {
      setIsArchiveComparing(false);
    }
  }, [selectedArchiveIds]);

  const handleAnalyzeSelected = useCallback(async () => {
    if (isArchiveProcessing) {
      return;
    }

    if (selectedArchiveIds.length === 0) {
      setArchiveActionFeedback({
        type: "warning",
        message: "Analize göndermek için rapor seçin.",
      });
      return;
    }

    if (selectedArchiveIds.length > 2) {
      setArchiveActionFeedback({
        type: "warning",
        message: "En Fazla 2 Adet Test Raporunu Analiz Edebilirsiniz!",
      });
      return;
    }

    setIsArchiveProcessing(true);
    setArchiveActionFeedback({
      type: "info",
      message: `${selectedArchiveIds.length} rapor ${engineLabel} ile yeniden analiz ediliyor...`,
    });

    try {
      const result = await analyzeArchivedReports(selectedArchiveIds, analysisEngine);
      const summaryCount = Array.isArray(result?.summaries)
        ? result.summaries.length
        : 0;

      onAnalysisComplete?.(result, { source: "archive", engineKey: analysisEngine });

      setArchiveActionFeedback({
        type: "success",
        message:
          result?.message ||
          (summaryCount
            ? `${summaryCount} özet başarıyla oluşturuldu.`
            : `${selectedArchiveIds.length} rapor başarıyla analiz edildi.`),
      });
      setSelectedArchiveIds([]);
    } catch (error) {
      const message =
        error?.response?.data?.error ||
        error?.message ||
        "Analiz sırasında bir sorun oluştu. Lütfen tekrar deneyin.";
      setArchiveActionFeedback({ type: "error", message });
    } finally {
      setIsArchiveProcessing(false);
    }
  }, [analysisEngine, engineLabel, isArchiveProcessing, onAnalysisComplete, selectedArchiveIds]);

  const handleViewSelected = useCallback(() => {
    if (selectedArchiveIds.length !== 1) {
      setArchiveActionFeedback({
        type: "warning",
        message: "Bir raporu görüntülemek için tek rapor seçin.",
      });
      return;
    }

    const [reportId] = selectedArchiveIds;
    const report = reports.find((item) => item.id === reportId);

    if (!report) {
      setArchiveActionFeedback({
        type: "error",
        message: "Seçilen rapor bulunamadı.",
      });
      return;
    }

    const pdfUrl = getReportDownloadUrl(reportId);
    window.open(pdfUrl, "_blank", "noopener,noreferrer");
    setArchiveActionFeedback({
      type: "info",
      message: "PDF raporu yeni sekmede açılıyor...",
    });
  }, [reports, selectedArchiveIds]);

  const hasFilters = Object.values(filters).some(Boolean);

  return (
    <div className="archive-section">
      <div className="two-column-grid">
        <div className="card archive-summary-card">
          <h2>Arşiv Özeti</h2>
          <p className="muted-text">
            {analysisEngine === "claude"
              ? "Veriler Claude analizi sonrasında güncellendi."
              : "Veriler ChatGPT analizi sonrasında güncellendi."}
          </p>
          <div className="archive-summary-grid">
            <div className="summary-item">
              <span className="summary-label">ECE R10 Test Sayısı</span>
              <span className="summary-value">{archiveSummary.r10}</span>
            </div>
            <div className="summary-item">
              <span className="summary-label">ECE R80 Test Sayısı</span>
              <span className="summary-value">{archiveSummary.r80}</span>
            </div>
            <div className="summary-item">
              <span className="summary-label">Bilinmeyen Test Sayısı</span>
              <span className="summary-value">{archiveSummary.unknown}</span>
            </div>
          </div>
        </div>

        <div className="card filters-card">
          <h2>
            <span className="card-title-icon" aria-hidden="true">
              📖
            </span>
            Filtreler
          </h2>
          <div className="filters-grid">
            <label className="filter-field">
              <span>Başlangıç Tarihi</span>
              <input
                type="date"
                value={filters.startDate}
                onChange={(event) => setFilters((prev) => ({ ...prev, startDate: event.target.value }))}
              />
            </label>
            <label className="filter-field">
              <span>Bitiş Tarihi</span>
              <input
                type="date"
                value={filters.endDate}
                onChange={(event) => setFilters((prev) => ({ ...prev, endDate: event.target.value }))}
              />
            </label>
            <label className="filter-field">
              <span>Test Tipi</span>
              <select
                value={filters.testType}
                onChange={(event) => setFilters((prev) => ({ ...prev, testType: event.target.value }))}
              >
                <option value="">Seçiniz</option>
                <option value="R10 EMC Testi">ECE R10 EMC Testi</option>
                <option value="R80 Darbe Testi">ECE R80 Darbe Testi</option>
              </select>
            </label>
            <label className="filter-field">
              <span>Labaratuvar</span>
              <select
                value={filters.laboratory}
                onChange={(event) => setFilters((prev) => ({ ...prev, laboratory: event.target.value }))}
              >
                <option value="">Seçiniz</option>
                <option value="GCS Test Laboratuvarı">GCS Test Laboratuvarı</option>
                <option value="Concept Test Laboratuvarı">Concept Test Laboratuvarı</option>
                <option value="Türk Standartları Enstitüsü">Türk Standartları Enstitüsü</option>
              </select>
            </label>
            <label className="filter-field">
              <span>Model</span>
              <select
                value={filters.model}
                onChange={(event) => setFilters((prev) => ({ ...prev, model: event.target.value }))}
              >
                <option value="">Seçiniz</option>
                <option value="Avance">Avance</option>
                <option value="Interline">Interline</option>
                <option value="Avance-X">Avance-X</option>
              </select>
            </label>
            <label className="filter-field">
              <span>Durum</span>
              <select
                value={filters.status}
                onChange={(event) => setFilters((prev) => ({ ...prev, status: event.target.value }))}
              >
                <option value="">Seçiniz</option>
                <option value="Başarılı">Başarılı</option>
                <option value="Başarısız">Başarısız</option>
                <option value="Belirsiz">Belirsiz</option>
                <option value="Kısmi Başarı">Kısmi Başarı</option>
                <option value="Analiz Bekleniyor">Analiz Bekleniyor</option>
              </select>
            </label>
          </div>
          <div className="filter-buttons">
            <button type="button" className="button" onClick={clearFilters} disabled={!hasFilters && !filtersApplied}>
              Temizle
            </button>
            <button type="button" className="button button-primary" onClick={applyFilters}>
              Uygula
            </button>
          </div>
        </div>
      </div>

      {filtersApplied && (
        <div className="card filter-results-card">
          <div className="card-header">
            <h2>Filtrelenen Raporlar</h2>
            <span className="badge">{filteredReports.length} kayıt</span>
          </div>
          {filteredReports.length === 0 ? (
            <p className="muted-text">Seçilen kriterlere uygun rapor bulunamadı.</p>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Yüklenen Rapor</th>
                  <th>Yükleme Tarihi</th>
                  <th>Yükleme Saati</th>
                  <th>Test Tipi</th>
                  <th>Labaratuvar</th>
                  <th>Durum</th>
                </tr>
              </thead>
              <tbody>
                {filteredReports.map((report) => (
                  <tr key={report.id}>
                    <td>{report.filename}</td>
                    <td>{report.uploadDate ? report.uploadDate.toLocaleDateString() : "-"}</td>
                    <td>
                      {report.uploadDate
                        ? report.uploadDate.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
                        : "-"}
                    </td>
                    <td>{report.displayTestType || report.detectedType}</td>
                    <td>{report.laboratory}</td>
                    <td>{report.statusLabel}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      <div className="archive-actions-grid">
        <div className="card multi-upload-card">
          <h2>Çoklu PDF Test Raporu Yükleme</h2>
          <p className="muted-text">Max. 100 adet pdf test raporu yükleyebilirsiniz!</p>

          <div
            className={`multi-upload-drop-zone ${dragActive ? "active" : ""} ${
              selectedFiles.length ? "has-files" : ""
            }`}
            onDragEnter={handleDrag}
            onDragOver={handleDrag}
            onDragLeave={handleDrag}
            onDrop={handleDrop}
          >
            {selectedFiles.length > 0 ? (
              <div className="multi-upload-file-list">
                <ul>
                  {selectedFiles.map((file, index) => (
                    <li key={`${file.name}-${index}`}>
                      <span className="file-name">📄 {file.name}</span>
                      <button
                        type="button"
                        className="remove-btn"
                        onClick={() => handleRemoveFile(index)}
                        disabled={isMultiUploading}
                      >
                        Kaldır
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              <div className="multi-upload-placeholder">
                <p>📂 PDF test raporlarını buraya sürükleyip bırakabilirsiniz</p>
                <p className="or-text">veya</p>
                <label htmlFor="multi-upload-input" className="file-select-btn">
                  Dosya Seç
                </label>
                <input
                  id="multi-upload-input"
                  type="file"
                  accept=".pdf,application/pdf"
                  multiple
                  onChange={handleFileInputChange}
                  disabled={isMultiUploading}
                  style={{ display: "none" }}
                />
              </div>
            )}
          </div>

          <div className="multi-upload-actions">
            <button
              type="button"
              className="button button-primary"
              onClick={handleBulkUpload}
              disabled={isMultiUploading || selectedFiles.length === 0}
            >
              {isMultiUploading
                ? `Yükleniyor (${uploadProgress.processed}/${uploadProgress.total})`
                : "Seçilen Raporları Yükle"}
            </button>
            <button
              type="button"
              className="button button-ghost"
              onClick={handleClearSelectedFiles}
              disabled={isMultiUploading || selectedFiles.length === 0}
            >
              Seçilenleri Temizle
            </button>
          </div>

          {multiUploadStatus && (
            <div className={`alert alert-${multiUploadStatus.type}`} role="status">
              {multiUploadStatus.message}
            </div>
          )}
        </div>
      </div>

      <div className="card report-archive-card">
          <h2>Rapor Arşivi</h2>
          {sortedReports.length === 0 ? (
            <p className="muted-text">Henüz rapor yüklenmedi.</p>
          ) : (
            <div className="table-wrapper">
              <table className="table archive-table">
                <thead>
                  <tr>
                    <th></th>
                    <th>Raporun Adı</th>
                    <th>Yüklenme Tarihi</th>
                    <th>Yüklenme Saati</th>
                    <th>Test Tipi</th>
                    <th>Laboratuvar</th>
                    <th>Model</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedReports.map((report) => (
                    <tr key={report.id}>
                      <td>
                        <input
                          type="checkbox"
                          checked={selectedArchiveIds.includes(report.id)}
                          onChange={() => toggleArchiveSelection(report.id)}
                        />
                      </td>
                      <td>{report.filename}</td>
                      <td>{report.uploadDate ? report.uploadDate.toLocaleDateString() : "-"}</td>
                      <td>
                        {report.uploadDate
                          ? report.uploadDate.toLocaleTimeString([], {
                              hour: "2-digit",
                              minute: "2-digit",
                            })
                          : "-"}
                      </td>
                      <td>{report.displayTestType || report.detectedType || "Bilinmeyen"}</td>
                      <td>{report.laboratory}</td>
                      <td>{report.model}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {sortedReports.length > 0 && (
            <div className="report-actions">
              <button
                className="button"
                type="button"
                onClick={handleCompareSelected}
                disabled={isArchiveComparing}
              >
                {isArchiveComparing ? "Karşılaştırılıyor..." : "Karşılaştır"}
              </button>
              <button
                className="button button-primary"
                type="button"
                onClick={handleAnalyzeSelected}
                disabled={isArchiveProcessing}
              >
                {isArchiveProcessing ? "Analiz Ediliyor..." : "Analize Gönder"}
              </button>
              <button className="button" type="button" onClick={handleViewSelected}>
                Görüntüle
              </button>
            </div>
          )}

          {archiveActionFeedback && (
            <div className={`alert alert-${archiveActionFeedback.type}`} role="status">
              {archiveActionFeedback.message}
            </div>
          )}

          {archiveComparisonResult && (
            <div className="card comparison-card">
              <div className="card-header">
                <div>
                  <h3>Karşılaştırma Sonucu</h3>
                  <p className="muted-text">
                    {archiveComparisonResult.first_report?.filename} ↔{" "}
                    {archiveComparisonResult.second_report?.filename}
                  </p>
                </div>
                {archiveComparisonResult.similarity !== undefined && (
                  <span className="badge badge-info">
                    Benzerlik %
                    {archiveComparisonResult.similarity?.toFixed?.(1) ??
                      archiveComparisonResult.similarity}
                  </span>
                )}
              </div>
              <p>
                {archiveComparisonResult.summary ||
                  "Karşılaştırma tamamlandı, detaylar rapor özetinde listelendi."}
              </p>

              <ComparisonDetailView comparisonData={archiveComparisonResult} />
            </div>
          )}
        </div>
      </div>

      <AnalysisSummaryCard
        analyses={analysisArchive}
        title="Analiz Arşivi"
        introText={
          analysisArchive.length > 0
            ? "Önceki AI analiz sonuçları arşivde saklanmaktadır."
            : "Arşivde gösterilecek analiz bulunmuyor."
        }
        emptyMessage="Arşivde gösterilecek analiz bulunmuyor."
        headerActions={
          <button
            type="button"
            className="button button-ghost analysis-summary-toggle"
            onClick={() => setIsArchiveCollapsed((prev) => !prev)}
          >
            {isArchiveCollapsed ? "Göster" : "Gizle"}
          </button>
        }
        collapsed={isArchiveCollapsed}
      />
    </div>
  );
};

export default ArchiveManagement;
