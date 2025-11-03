import React, { useState } from 'react';
import { uploadReport } from '../api';

function UploadForm({ onUploadComplete }) {
    const [selectedFile, setSelectedFile] = useState(null);
    const [uploading, setUploading] = useState(false);
    const [error, setError] = useState(null);
    const [dragActive, setDragActive] = useState(false);

    // Dosya seçme (input ile)
    const handleFileSelect = (e) => {
        console.log("=== FILE SELECT EVENT ===");
        console.log("Event:", e);
        console.log("Files:", e.target.files);

        const file = e.target.files[0];
        console.log("Selected file:", file);

        if (file && file.type === 'application/pdf') {
            console.log("✓ Valid PDF file");
            setSelectedFile(file);
            setError(null);
        } else {
            console.error("✗ Invalid file type");
            setError('Lütfen sadece PDF dosyası seçin');
            setSelectedFile(null);
        }

        console.log("State updated, selectedFile:", file);
    };

    // Drag & Drop events
    const handleDrag = (e) => {
        e.preventDefault();
        e.stopPropagation();
        
        if (e.type === 'dragenter' || e.type === 'dragover') {
            setDragActive(true);
        } else if (e.type === 'dragleave') {
            setDragActive(false);
        }
    };

    const handleDrop = (e) => {
        e.preventDefault();
        e.stopPropagation();
        setDragActive(false);

        console.log("=== DROP EVENT ===");
        console.log("DataTransfer files:", e.dataTransfer.files);

        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            const file = e.dataTransfer.files[0];
            console.log("Dropped file:", file);

            if (file.type === 'application/pdf') {
                console.log("✓ Valid PDF file");
                setSelectedFile(file);
                setError(null);
            } else {
                console.error("✗ Invalid file type");
                setError('Lütfen sadece PDF dosyası yükleyin');
            }
        }
    };

    // Upload
    const handleSubmit = async (e) => {
        e.preventDefault();

        console.log("=== SUBMIT EVENT ===");
        console.log("Selected file:", selectedFile);

        if (!selectedFile) {
            console.error("✗ No file selected");
            setError('Lütfen önce bir PDF dosyası seçin');
            return;
        }

        setUploading(true);
        setError(null);

        console.log("Starting upload:", selectedFile.name);
        console.log("File size:", selectedFile.size, "bytes");
        console.log("File type:", selectedFile.type);

        try {
            console.log("Calling uploadReport API...");
            const response = await uploadReport(selectedFile);
            console.log("✓ Upload successful!");
            console.log("Response:", response);

            alert(`PDF başarıyla yüklendi ve analiz edildi!\n\nRapor ID: ${response.report_id}\nDosya: ${response.filename}`);

            // Reset
            setSelectedFile(null);
            setUploading(false);

            // Callback
            if (onUploadComplete) {
                console.log("Calling onUploadComplete callback");
                onUploadComplete(response);
            }

            // Reload
            console.log("Reloading page...");
            setTimeout(() => {
                window.location.reload();
            }, 1000);

        } catch (error) {
            console.error("=== UPLOAD ERROR ===");
            console.error("Error object:", error);
            console.error("Error message:", error.message);
            console.error("Response data:", error.response?.data);
            console.error("Response status:", error.response?.status);

            const errorMsg = error.response?.data?.error || error.message || 'Yükleme başarısız oldu';
            setError(errorMsg);
            setUploading(false);

            alert(`Hata: ${errorMsg}`);
        }
    };

    return (
        <div className="upload-form">
            <h2>PDF Test Raporunu Yükle ve Analiz Et</h2>
            
            <form onSubmit={handleSubmit}>
                {/* Drag & Drop Area */}
                <div 
                    className={`drop-zone ${dragActive ? 'active' : ''} ${selectedFile ? 'has-file' : ''}`}
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
                                style={{ display: 'none' }}
                            />
                            <p className="hint-text">Sadece PDF formatı desteklenir</p>
                        </div>
                    )}
                </div>

                {/* Error Message */}
                {error && (
                    <div className="error-message">
                        ⚠️ {error}
                    </div>
                )}

                {/* Submit Button */}
                <button 
                    type="submit" 
                    disabled={!selectedFile || uploading}
                    className="submit-btn"
                >
                    {uploading ? 'Yükleniyor ve Analiz Ediliyor...' : 'PDF Yükle ve AI ile Analiz Et'}
                </button>
            </form>
        </div>
    );
}

export default UploadForm;
