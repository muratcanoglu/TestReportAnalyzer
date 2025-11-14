import axios from "axios";

const isDebugEnabled =
  String(process.env.REACT_APP_DEBUG || "")
    .toLowerCase()
    .trim() === "true";

const debugLog = (...args) => {
  if (isDebugEnabled) {
    console.debug("[api]", ...args);
  }
};

const resolveBaseUrl = () => {
  const envBaseUrl = process.env.REACT_APP_API_BASE_URL?.trim();
  if (envBaseUrl) {
    return envBaseUrl;
  }

  const { hostname, origin } = window.location;
  if (hostname === "localhost" || hostname === "127.0.0.1") {
    return "http://localhost:5000/api";
  }

  return `${origin.replace(/\/$/, "")}/api`;
};

const API_BASE = resolveBaseUrl();
debugLog(`Using API base URL: ${API_BASE}`);

const client = axios.create({
  baseURL: API_BASE,
});

client.interceptors.response.use(
  (response) => {
    debugLog(
      `${response.config.method?.toUpperCase()} ${response.config.url}`,
      response.status
    );
    return response;
  },
  (error) => {
    if (error.config) {
      debugLog(
        `Request failed: ${error.config.method?.toUpperCase()} ${
          error.config.url || ""
        }`,
        error.message
      );
    } else {
      debugLog("Request error", error.message || error);
    }
    return Promise.reject(error);
  }
);

export const uploadReport = async (file, engine) => {
  const formData = new FormData();
  formData.append("file", file);

  if (engine) {
    formData.append("engine", engine);
  }

  try {
    const response = await client.post("/upload", formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
      timeout: 120000,
    });

    return response.data;
  } catch (error) {
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
  const response = await client.get(`/ai-status`);
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
