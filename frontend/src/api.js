import axios from "axios";

const API_BASE = window.location.hostname === "localhost"
  ? "http://localhost:5000/api"
  : "http://127.0.0.1:5000/api";

const client = axios.create({
  baseURL: API_BASE,
});

export const uploadReport = async (file) => {
  console.log('=== UPLOAD API CALL ===');
  console.log('File:', file);
  console.log('File name:', file.name);
  console.log('File size:', file.size);
  console.log('File type:', file.type);

  // FormData oluştur
  const formData = new FormData();
  formData.append('file', file);

  console.log('FormData oluşturuldu');

  try {
    console.log('Request gönderiliyor: POST /api/upload');

    const response = await axios.post(`${API_BASE}/upload`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      },
      timeout: 120000  // 2 dakika timeout (AI analizi uzun sürebilir)
    });

    console.log('Response alındı:', response.data);
    return response.data;

  } catch (error) {
    console.error('=== UPLOAD ERROR ===');
    console.error('Error:', error);
    console.error('Response:', error.response?.data);
    console.error('Status:', error.response?.status);

    throw error;
  }
};

export const getAllReports = async (sortBy = "date", order = "desc") => {
  const response = await client.get("/reports", {
    params: { sortBy, order },
  });
  return response.data.reports;
};

export const getReportById = async (id) => {
  const response = await client.get(`/reports/${id}`);
  return response.data;
};

export const getDetailedReport = async (id) => {
  const response = await client.get(`/reports/${id}/detailed`);
  return response.data;
};

export const getFailedTests = async (id) => {
  const response = await client.get(`/reports/${id}/failures`);
  return response.data.failures;
};

export const getReportTables = async (id) => {
  const response = await client.get(`/reports/${id}/tables`);
  return response.data;
};

export const deleteReport = async (id) => {
  const response = await client.delete(`/reports/${id}`);
  return response.data;
};

export const getAIStatus = async () => {
  const response = await axios.get(`${API_BASE}/ai-status`);
  return response.data;
};

export const analyzeReportsWithAI = async (files, engine) => {
  const formData = new FormData();
  files.forEach((file, index) => {
    const fileName = file?.name || `report-${index + 1}.pdf`;
    formData.append("files", file, fileName);
  });
  formData.append("engine", engine);

  const response = await client.post("/analyze-files", formData);
  return response.data;
};

export const downloadReportFile = async (id) => {
  const response = await client.get(`/reports/${id}/download`, {
    responseType: "blob",
  });
  return response.data;
};

export const compareReports = async (reportIds) => {
  const response = await client.post("/reports/compare", {
    report_ids: reportIds,
  });
  return response.data;
};

export const resetAllData = async () => {
  const response = await client.post("/reset");
  return response.data;
};

export const getReportDownloadUrl = (id) => `${API_BASE}/reports/${id}/download`;
