CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    upload_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    total_tests INTEGER DEFAULT 0,
    passed_tests INTEGER DEFAULT 0,
    failed_tests INTEGER DEFAULT 0,
    pdf_path TEXT NOT NULL,
    test_type TEXT DEFAULT 'unknown',
    test_conditions_summary TEXT,
    graphs_description TEXT,
    detailed_results TEXT,
    improvement_suggestions TEXT,
    analysis_language TEXT DEFAULT 'tr',
    structured_data TEXT,
    table_count INTEGER DEFAULT 0,
    test_standard TEXT,
    seat_model TEXT,
    lab_name TEXT,
    vehicle_platform TEXT
);

CREATE TABLE IF NOT EXISTS test_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL,
    test_name TEXT NOT NULL,
    status TEXT CHECK(status IN ('PASS', 'FAIL')) NOT NULL,
    error_message TEXT,
    failure_reason TEXT,
    suggested_fix TEXT,
    ai_provider TEXT DEFAULT 'rule-based',
    FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_report_id ON test_results(report_id);
CREATE INDEX IF NOT EXISTS idx_status ON test_results(status);
