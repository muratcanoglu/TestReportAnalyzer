import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { getAllReports } from "./api";
import AllReports from "./components/AllReports";
import ArchiveManagement from "./components/ArchiveManagement";
import HomeSection from "./components/HomeSection";
import NaturalLanguageQuery from "./components/NaturalLanguageQuery";
import ReportDetail from "./components/ReportDetail";
import SettingsPanel from "./components/SettingsPanel";
import TestReportsBoard from "./components/TestReportsBoard";
import { detectReportType } from "./utils/reportUtils";
import { createAnalysisEntry } from "./utils/analysisUtils";

const NAV_ITEMS = [
  { path: "/", label: "Ana Sayfa", exact: true },
  { path: "/archive", label: "Arşiv Yönetimi" },
  { path: "/query", label: "Doğal Dil Sorgusu" },
  { path: "/r80", label: "R80 Darbe Testleri" },
  { path: "/r10", label: "R10 EMC Testleri" },
  { path: "/reports", label: "Raporlar" },
  { path: "/settings", label: "Ayarlar" },
];

const App = () => {
  const location = useLocation();
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [theme, setTheme] = useState("dark");
  const [analysisEngine, setAnalysisEngine] = useState("chatgpt");
  const [searchQuery, setSearchQuery] = useState("");
  const [analysisHistory, setAnalysisHistory] = useState([]);
  const [isAnalysisProcessing, setIsAnalysisProcessing] = useState(false);

  const handleAnalysisProcessingStart = useCallback(() => {
    setIsAnalysisProcessing(true);
  }, []);

  const handleAnalysisProcessingEnd = useCallback(() => {
    setIsAnalysisProcessing(false);
  }, []);
  const navigate = useNavigate();

  const fetchReports = async () => {
    setLoading(true);
    try {
      const data = await getAllReports();
      setReports(data);
      setError(null);
    } catch (err) {
      setError("Raporlar yüklenemedi. Lütfen daha sonra tekrar deneyin.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReports();
  }, []);

  useEffect(() => {
    document.body.classList.remove("light-theme", "dark-theme");
    document.body.classList.add(`${theme}-theme`);
  }, [theme]);

  const reportGroups = useMemo(() => {
    const r80 = reports.filter((report) => detectReportType(report) === "R80 Darbe Testi");
    const r10 = reports.filter((report) => detectReportType(report) === "R10 EMC Testi");
    return { r80, r10 };
  }, [reports]);

  const handleAnalysisComplete = useCallback(
    (result, context = {}) => {
      if (!result) {
        return null;
      }

      const entry = createAnalysisEntry(result, {
        engineKey: context.engineKey ?? analysisEngine,
        source: context.source ?? "home",
      });

      if (!entry) {
        return null;
      }

      setAnalysisHistory((prev) => [entry, ...prev]);
      return entry;
    },
    [analysisEngine]
  );

  const clearAnalysisHistory = useCallback(() => {
    setAnalysisHistory([]);
  }, []);

  const recentAnalyses = useMemo(() => analysisHistory.slice(0, 2), [analysisHistory]);
  const archivedAnalyses = useMemo(() => analysisHistory.slice(2), [analysisHistory]);

  const filteredReports = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    if (!query) {
      return [];
    }
    return reports.filter((report) => {
      const fileName = report.filename?.toLowerCase() ?? "";
      const detectedType = detectReportType(report)?.toLowerCase() ?? "";
      return fileName.includes(query) || detectedType.includes(query);
    });
  }, [reports, searchQuery]);

  const handleReportSearchSelect = (report) => {
    if (!report?.id) {
      return;
    }
    navigate(`/report/${report.id}`);
    setSearchQuery("");
  };

  const isHome = location.pathname === "/";

  const isNavActive = (item) => {
    const detailView = location.pathname.startsWith("/report/");
    if (item.exact) {
      return location.pathname === item.path;
    }
    if (item.path === "/reports") {
      return location.pathname.startsWith(item.path) || detailView;
    }
    return location.pathname.startsWith(item.path);
  };

  const currentNavLabel = useMemo(() => {
    const detailView = location.pathname.startsWith("/report/");
    if (detailView) {
      return "Rapor Detayı";
    }
    const current = NAV_ITEMS.find((item) => {
      if (item.exact) {
        return location.pathname === item.path;
      }
      if (item.path === "/reports") {
        return location.pathname.startsWith(item.path) || detailView;
      }
      return location.pathname.startsWith(item.path);
    });
    return current?.label ?? "";
  }, [location.pathname]);

  return (
    <div className={`app-root ${theme}-theme`}>
      <aside className="sidebar">
        <div className="sidebar-header">
          <h1>Test Report Analyzer</h1>
        </div>
        <nav className="sidebar-nav">
          {NAV_ITEMS.map((item) => (
            <Link
              key={item.path}
              to={item.path}
              className={isNavActive(item) ? "active" : ""}
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </aside>
      <div className="main-area">
        <header className={`topbar ${isHome ? "topbar-home" : ""}`}>
          {isHome ? (
            <>
              <div className="topbar-home-left">
                <h1 className="topbar-title">AI Destekli Test Analiz Platformu</h1>
                <p className="muted-text">
                  Analiz Motoru: {analysisEngine === "claude" ? "Claude" : "ChatGPT"}
                </p>
              </div>
              <div className="topbar-home-right">
                <div className="report-search">
                  <span className="search-icon" aria-hidden="true">
                    🔍
                  </span>
                  <input
                    type="search"
                    placeholder="Rapor Ara"
                    value={searchQuery}
                    aria-label="Rapor Ara"
                    onChange={(event) => setSearchQuery(event.target.value)}
                  />
                </div>
                {searchQuery.trim() && (
                  <div className="report-search-results">
                    {filteredReports.length > 0 ? (
                      filteredReports.map((report) => (
                        <button
                          key={report.id}
                          type="button"
                          className="report-search-result"
                          onClick={() => handleReportSearchSelect(report)}
                        >
                          <span className="report-search-result-name">{report.filename}</span>
                          <span className="report-search-result-type">
                            {detectReportType(report) || "Bilinmeyen"}
                          </span>
                        </button>
                      ))
                    ) : (
                      <div className="report-search-empty">Sonuç bulunamadı</div>
                    )}
                  </div>
                )}
              </div>
            </>
          ) : (
            <div>
              <h2>{currentNavLabel}</h2>
              <p className="muted-text">
                Analiz Motoru: {analysisEngine === "claude" ? "Claude" : "ChatGPT"}
              </p>
            </div>
          )}
        </header>
        <main className="content-area">
          <Routes>
            <Route
              path="/"
              element={
                <HomeSection
                  reports={reports}
                  onRefresh={fetchReports}
                  loading={loading}
                  error={error}
                  analysisEngine={analysisEngine}
                  recentAnalyses={recentAnalyses}
                  onAnalysisComplete={handleAnalysisComplete}
                  onClearAnalyses={clearAnalysisHistory}
                  isAnalysisProcessing={isAnalysisProcessing}
                  onAnalysisProcessingStart={handleAnalysisProcessingStart}
                  onAnalysisProcessingEnd={handleAnalysisProcessingEnd}
                />
              }
            />
            <Route
              path="/archive"
              element={
                <ArchiveManagement
                  reports={reports}
                  analysisEngine={analysisEngine}
                  analysisArchive={archivedAnalyses}
                  onRefresh={fetchReports}
                  onAnalysisComplete={handleAnalysisComplete}
                />
              }
            />
            <Route
              path="/query"
              element={<NaturalLanguageQuery reports={reports} analysisEngine={analysisEngine} />}
            />
            <Route
              path="/r80"
              element={
                <TestReportsBoard
                  title="R80 Darbe Testleri"
                  reports={reportGroups.r80}
                  analysisEngine={analysisEngine}
                  onAnalysisComplete={handleAnalysisComplete}
                />
              }
            />
            <Route
              path="/r10"
              element={
                <TestReportsBoard
                  title="R10 EMC Testleri"
                  reports={reportGroups.r10}
                  analysisEngine={analysisEngine}
                  onAnalysisComplete={handleAnalysisComplete}
                />
              }
            />
            <Route
              path="/reports"
              element={<AllReports reports={reports} onReportDeleted={fetchReports} />}
            />
            <Route
              path="/settings"
              element={
                <SettingsPanel
                  theme={theme}
                  onThemeChange={setTheme}
                  analysisEngine={analysisEngine}
                  onEngineChange={setAnalysisEngine}
                />
              }
            />
            <Route path="/report/:id" element={<ReportDetail />} />
          </Routes>
        </main>
      </div>
    </div>
  );
};

export default App;
