import React, { useMemo, useState } from "react";
import { analyzeReportsWithAI, uploadReport } from "../api";
import { resolveEngineLabel } from "../utils/analysisUtils";
import { normaliseFilenameForComparison } from "../utils/fileUtils";

const UploadForm = ({
  analysisEngine = "chatgpt",
  onUploadSuccess,
  onAnalysisComplete,
  isProcessing = false,
  onProcessingStart,
  onProcessingEnd,
  existingReports = [],
}) => {
  const [selectedFile, setSelectedFile] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const [error, setError] = useState(null);
  const [statusMessage, setStatusMessage] = useState(null);
  const [analysisMessage, setAnalysisMessage] = useState(null);
  const [localProcessing, setLocalProcessing] = useState(false);

  const engineLabel = useMemo(
    () => resolveEngineLabel(analysisEngine),
    [analysisEngine]
  );

  const existingFilenames = useMemo(() => {
    return new Set(
      existingReports
        .map((report) => normaliseFilenameForComparison(report?.filename))
        .filter(Boolean)
    );
  }, [existingReports]);

  const isBusy = isProcessing || localProcessing;

  const resetMessages = () => {
    setError(null);
    setStatusMessage(null);
    setAnalysisMessage(null);
  };

  const handleFileSelect = (event) => {
    const file = event.target.files?.[0] ?? null;
    resetMessages();

    if (file && file.type === "application/pdf") {
      const normalizedName = normaliseFilenameForComparison(file.name);
      if (normalizedName && existingFilenames.has(normalizedName)) {
        setError("Bu rapor daha önce arşivlendi.");
        setSelectedFile(null);
        return;
      }
      setSelectedFile(file);
    } else {
      setError("Lütfen sadece PDF dosyası seçin");
      setSelectedFile(null);
    }
  };

  const handleDrag = (event) => {
    event.preventDefault();
    event.stopPropagation();

    if (event.type === "dragenter" || event.type === "dragover") {
      setDragActive(true);
    } else if (event.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (event) => {
    event.preventDefault();
    event.stopPropagation();
    setDragActive(false);
    resetMessages();

    const file = event.dataTransfer?.files?.[0] ?? null;
    if (!file) {
      return;
    }

    if (file.type === "application/pdf") {
      const normalizedName = normaliseFilenameForComparison(file.name);
      if (normalizedName && existingFilenames.has(normalizedName)) {
        setError("Bu rapor daha önce arşivlendi.");
        setSelectedFile(null);
        return;
      }
      setSelectedFile(file);
    } else {
      setError("Lütfen sadece PDF dosyası yükleyin");
    }
  };

  const handleSubmit = async (event) => {
    event.preventDefault();

    if (!selectedFile) {
      setError("Lütfen önce bir PDF dosyası seçin");
      return;
    }

    if (isBusy) {
      return;
    }

    const normalizedName = normaliseFilenameForComparison(selectedFile.name);
    if (normalizedName && existingFilenames.has(normalizedName)) {
      setError("Bu rapor daha önce arşivlendi.");
      return;
    }

    resetMessages();
    setLocalProcessing(true);
    onProcessingStart?.();

    try {
      const uploadResponse = await uploadReport(selectedFile, analysisEngine);
      setStatusMessage(
        `${selectedFile.name} başarıyla yüklendi. ${engineLabel} ile analiz başlatılıyor.`
      );
      onUploadSuccess?.(uploadResponse);

      try {
        const analysisResult = await analyzeReportsWithAI(
          [selectedFile],
          analysisEngine
        );
        const message =
          analysisResult?.message ||
          `${engineLabel} analizi başarıyla tamamlandı.`;
        setAnalysisMessage(message);
        onAnalysisComplete?.(analysisResult, {
          engineKey: analysisEngine,
          source: "home",
        });
        setSelectedFile(null);
      } catch (analysisError) {
        const message =
          analysisError?.response?.data?.error ||
          analysisError?.message ||
          "AI analizi sırasında bir sorun oluştu. Lütfen tekrar deneyin.";
        setError(message);
      }
    } catch (uploadError) {
      const message =
        uploadError?.response?.data?.error ||
        uploadError?.message ||
        "Yükleme işlemi başarısız oldu. Lütfen tekrar deneyin.";
      setError(message);
    } finally {
      setLocalProcessing(false);
      onProcessingEnd?.();
    }
  };

  const busyLabel = isBusy
    ? `${engineLabel} Analizi Yapılıyor...`
    : "PDF Yükle ve AI ile Analiz Et";

  return (
    <div className="upload-form">
      <h2>PDF Test Raporunu Yükle ve Analiz Et</h2>

      <form onSubmit={handleSubmit}>
        <div
          className={`drop-zone ${dragActive ? "active" : ""} ${
            selectedFile ? "has-file" : ""
          }`}
          onDragEnter={handleDrag}
          onDragOver={handleDrag}
          onDragLeave={handleDrag}
          onDrop={handleDrop}
        >
          {selectedFile ? (
            <div className="selected-file">
              <p>📄 {selectedFile.name}</p>
              <p className="file-size">
                {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
              </p>
              <button
                type="button"
                onClick={() => setSelectedFile(null)}
                className="remove-btn"
                disabled={isBusy}
              >
                ✕ Kaldır
              </button>
            </div>
          ) : (
            <div className="drop-zone-placeholder">
              <p>📂 PDF Test Raporlarını Sürükleyip Bırakabilirsiniz</p>
              <p className="or-text">veya</p>
              <label htmlFor="file-input" className="file-select-btn">
                Dosya Seç
              </label>
              <input
                id="file-input"
                type="file"
                accept=".pdf,application/pdf"
                onChange={handleFileSelect}
                disabled={isBusy}
                style={{ display: "none" }}
              />
              <p className="hint-text">Sadece PDF formatı desteklenir</p>
            </div>
          )}
        </div>

        {statusMessage && (
          <div className="alert alert-success" role="status">
            {statusMessage}
          </div>
        )}

        {analysisMessage && (
          <div className="alert alert-info" role="status">
            {analysisMessage}
          </div>
        )}

        {error && <div className="error-message">⚠️ {error}</div>}

        <button type="submit" disabled={!selectedFile || isBusy} className="submit-btn">
          {busyLabel}
        </button>
        <p className="muted-text">
          Seçilen analiz motoru: <strong>{engineLabel}</strong>
        </p>
      </form>
    </div>
  );
};

export default UploadForm;
