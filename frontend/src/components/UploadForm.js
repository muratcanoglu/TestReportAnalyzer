import React, { useState } from 'react';
import { uploadReport } from '../api';

function UploadForm({ onUploadComplete }) {
    const [selectedFile, setSelectedFile] = useState(null);
    const [uploading, setUploading] = useState(false);
    const [error, setError] = useState(null);
    const [dragActive, setDragActive] = useState(false);

    // Dosya seçme (input ile)
    const handleFileSelect = (e) => {
        const file = e.target.files[0];
        console.log("Dosya seçildi:", file);
        
        if (file && file.type === 'application/pdf') {
            setSelectedFile(file);
            setError(null);
        } else {
            setError('Lütfen sadece PDF dosyası seçin');
            setSelectedFile(null);
        }
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

        console.log("Drop event:", e.dataTransfer.files);
        
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            const file = e.dataTransfer.files[0];
            
            if (file.type === 'application/pdf') {
                setSelectedFile(file);
                setError(null);
            } else {
                setError('Lütfen sadece PDF dosyası yükleyin');
            }
        }
    };

    // Upload
    const handleSubmit = async (e) => {
        e.preventDefault();
        
        if (!selectedFile) {
            setError('Lütfen önce bir PDF dosyası seçin');
            return;
        }

        setUploading(true);
        setError(null);
        
        console.log("Upload başlıyor:", selectedFile.name);

        try {
            const response = await uploadReport(selectedFile);
            console.log("Upload başarılı:", response);
            
            // Success
            alert(`PDF başarıyla yüklendi ve analiz edildi!\nRapor ID: ${response.report_id}`);
            
            // Reset
            setSelectedFile(null);
            setUploading(false);
            
            // Parent'a bildir
            if (onUploadComplete) {
                onUploadComplete(response);
            }
            
            // Sayfayı yenile (raporlar listesi için)
            window.location.reload();
            
        } catch (error) {
            console.error("Upload hatası:", error);
            setError(error.response?.data?.error || error.message || 'Yükleme başarısız oldu');
            setUploading(false);
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
