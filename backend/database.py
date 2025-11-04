"""Database utilities for the TestReportAnalyzer backend."""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "database.db"
SCHEMA_PATH = BASE_DIR / "models" / "schema.sql"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db_connection() -> sqlite3.Connection:
    """Return a new SQLite connection to the application database."""
    return _connect()


def init_db() -> None:
    """Initialise the database using the schema file if necessary."""
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with closing(_connect()) as conn:
        with SCHEMA_PATH.open("r", encoding="utf-8") as schema_file:
            conn.executescript(schema_file.read())
        try:
            conn.execute("ALTER TABLE test_results ADD COLUMN ai_provider TEXT DEFAULT 'rule-based'")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE reports ADD COLUMN test_type TEXT DEFAULT 'unknown'")
        except sqlite3.OperationalError:
            pass
        for column, definition in (
            ("test_conditions_summary", "TEXT"),
            ("graphs_description", "TEXT"),
            ("detailed_results", "TEXT"),
            ("improvement_suggestions", "TEXT"),
            ("analysis_language", "TEXT DEFAULT 'tr'"),
            ("structured_data", "TEXT"),
            ("table_count", "INTEGER DEFAULT 0"),
        ):
            try:
                conn.execute(f"ALTER TABLE reports ADD COLUMN {column} {definition}")
            except sqlite3.OperationalError:
                pass
        conn.commit()


def insert_report(
    filename: str,
    pdf_path: str,
    test_type: str = "unknown",
    comprehensive_analysis: Optional[Dict[str, str]] = None,
) -> int:
    """Insert a new report record and return its ID."""
    normalized_type = (test_type or "unknown").strip().lower()
    with closing(_connect()) as conn:
        columns = ["filename", "pdf_path", "test_type"]
        values: List[object] = [filename, pdf_path, normalized_type]

        if comprehensive_analysis:
            columns.extend(
                [
                    "test_conditions_summary",
                    "graphs_description",
                    "detailed_results",
                    "improvement_suggestions",
                    "analysis_language",
                ]
            )
            values.extend(
                [
                    comprehensive_analysis.get("test_conditions"),
                    comprehensive_analysis.get("graphs"),
                    comprehensive_analysis.get("results"),
                    comprehensive_analysis.get("improvements"),
                    comprehensive_analysis.get("analysis_language"),
                ]
            )

        placeholders = ", ".join(["?"] * len(columns))
        column_sql = ", ".join(columns)
        cursor = conn.execute(
            f"INSERT INTO reports ({column_sql}) VALUES ({placeholders})",
            values,
        )
        conn.commit()
        return int(cursor.lastrowid)


def report_exists_with_filename(filename: str) -> bool:
    """Return whether a report with the provided filename already exists."""

    normalized = (filename or "").strip()
    if not normalized:
        return False

    with closing(_connect()) as conn:
        cursor = conn.execute(
            "SELECT 1 FROM reports WHERE LOWER(filename) = LOWER(?) LIMIT 1",
            (normalized.lower(),),
        )
        return cursor.fetchone() is not None


def update_report_stats(report_id: int, total: int, passed: int, failed: int) -> None:
    """Update aggregate statistics for a report."""
    with closing(_connect()) as conn:
        conn.execute(
            """
            UPDATE reports
            SET total_tests = ?, passed_tests = ?, failed_tests = ?
            WHERE id = ?
            """,
            (total, passed, failed, report_id),
        )
        conn.commit()


def insert_test_result(
    report_id: int,
    test_name: str,
    status: str,
    error_message: Optional[str],
    reason: Optional[str],
    fix: Optional[str],
    ai_provider: str = "rule-based",
) -> None:
    """Insert a single test result entry."""
    with closing(_connect()) as conn:
        conn.execute(
            """
            INSERT INTO test_results (
                report_id,
                test_name,
                status,
                error_message,
                failure_reason,
                suggested_fix,
                ai_provider
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (report_id, test_name, status, error_message, reason, fix, ai_provider),
        )
        conn.commit()


def get_all_reports(sort_by: str = "date", order: str = "desc") -> List[Dict]:
    """Return all reports ordered by the requested column."""
    column_map = {
        "date": "upload_date",
        "name": "filename",
        "total": "total_tests",
        "passed": "passed_tests",
        "failed": "failed_tests",
    }
    column = column_map.get(sort_by.lower(), "upload_date")
    direction = "ASC" if order.lower() == "asc" else "DESC"

    with closing(_connect()) as conn:
        cursor = conn.execute(
            f"""
            SELECT id, filename, upload_date, total_tests, passed_tests, failed_tests, test_type
            FROM reports
            ORDER BY {column} {direction}
            """
        )
        return [dict(row) for row in cursor.fetchall()]


def get_report_by_id(report_id: int) -> Optional[Dict]:
    """Return a single report with aggregated statistics."""
    with closing(_connect()) as conn:
        cursor = conn.execute(
            """
            SELECT
                id,
                filename,
                upload_date,
                total_tests,
                passed_tests,
                failed_tests,
                pdf_path,
                test_type,
                test_conditions_summary,
                graphs_description,
                detailed_results,
                improvement_suggestions,
                analysis_language,
                structured_data,
                table_count
            FROM reports
            WHERE id = ?
            """,
            (report_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def update_report_comprehensive_analysis(
    report_id: int,
    analysis: Dict[str, str],
    structured_data: Optional[Dict[str, object]] = None,
    tables: Optional[List[Dict[str, object]]] = None,
) -> None:
    """Persist comprehensive analysis columns for a report."""

    if not analysis:
        return

    with closing(_connect()) as conn:
        conn.execute(
            """
            UPDATE reports
            SET
                test_conditions_summary = ?,
                graphs_description = ?,
                detailed_results = ?,
                improvement_suggestions = ?,
                analysis_language = COALESCE(?, analysis_language),
                structured_data = ?,
                table_count = ?
            WHERE id = ?
            """,
            (
                analysis.get("test_conditions"),
                analysis.get("graphs"),
                analysis.get("results"),
                analysis.get("improvements"),
                analysis.get("analysis_language"),
                json.dumps(structured_data) if structured_data else None,
                len(tables) if tables else 0,
                report_id,
            ),
        )
        conn.commit()


def get_failed_tests(report_id: int) -> List[Dict]:
    """Return all failed tests for a given report."""
    with closing(_connect()) as conn:
        cursor = conn.execute(
            """
            SELECT id, test_name, status, error_message, failure_reason, suggested_fix, ai_provider
            FROM test_results
            WHERE report_id = ? AND status = 'FAIL'
            ORDER BY id ASC
            """,
            (report_id,),
        )
        return [dict(row) for row in cursor.fetchall()]


def get_test_results(report_id: int) -> List[Dict]:
    """Return all test results for a report."""
    with closing(_connect()) as conn:
        cursor = conn.execute(
            """
            SELECT id, test_name, status, error_message, failure_reason, suggested_fix, ai_provider
            FROM test_results
            WHERE report_id = ?
            ORDER BY id ASC
            """,
            (report_id,),
        )
        return [dict(row) for row in cursor.fetchall()]


def delete_report(report_id: int) -> Optional[str]:
    """Delete report and return stored PDF path if found."""
    with closing(_connect()) as conn:
        cursor = conn.execute(
            "SELECT pdf_path FROM reports WHERE id = ?",
            (report_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        pdf_path = row[0]
        conn.execute("DELETE FROM reports WHERE id = ?", (report_id,))
        conn.commit()
        return pdf_path


def clear_all_data() -> List[str]:
    """Delete all reports and test results, returning removed PDF paths."""
    with closing(_connect()) as conn:
        cursor = conn.execute("SELECT pdf_path FROM reports")
        pdf_paths = [row[0] for row in cursor.fetchall() if row[0]]
        conn.execute("DELETE FROM test_results")
        conn.execute("DELETE FROM reports")
        conn.commit()
        return pdf_paths
