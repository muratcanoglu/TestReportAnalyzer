import sys
from pathlib import Path

import pytest
from flask import Flask


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.routes import reports_bp as routes_blueprint


@pytest.fixture
def test_app(tmp_path):
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["UPLOAD_FOLDER"] = str(tmp_path)
    app.register_blueprint(routes_blueprint, url_prefix="/api")
    return app


@pytest.fixture
def sample_pdf(tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%Stub PDF content")
    return pdf_path


@pytest.fixture
def stub_pdf_dependencies(monkeypatch):
    import backend.routes as routes_pkg
    import backend.routes.__init__ as routes_module

    def fake_extract_text(_):
        return {
            "structured_text": "Test A - PASS\nTest B - FAIL",
            "text": "Test A - PASS\nTest B - FAIL",
        }

    def fake_parse_results(_):
        return [
            {
                "test_name": "Test A",
                "status": "PASS",
                "failure_reason": "",
                "suggested_fix": "",
                "ai_provider": "rule-based",
            },
            {
                "test_name": "Test B",
                "status": "FAIL",
                "failure_reason": "Exceeded limit",
                "suggested_fix": "Calibrate sensor",
                "ai_provider": "rule-based",
            },
        ]

    def fake_comprehensive_analysis(_):
        return {
            "report_type": "r80",
            "report_type_label": "ECE R80",
            "basic_stats": {
                "total_tests": 2,
                "passed": 1,
                "failed": 1,
                "tests": fake_parse_results(None),
            },
            "comprehensive_analysis": {
                "test_conditions": "Ambient 20C, humidity 40%",
            },
            "measurement_params": [
                {"name": "HAC Left", "value": 32.5},
                {"name": "ThAC Left", "value": 41.2},
            ],
        }

    for target in (routes_module, routes_pkg):
        monkeypatch.setattr(target, "extract_text_from_pdf", fake_extract_text)
        monkeypatch.setattr(target, "parse_test_results", fake_parse_results)
        monkeypatch.setattr(target, "analyze_pdf_comprehensive", fake_comprehensive_analysis)
        monkeypatch.setattr(target, "infer_report_type", lambda *_: ("r80", "ECE R80"))


@pytest.fixture
def client(test_app):
    with test_app.test_client() as client:
        yield client


def _post_analyze_request(client, sample_pdf):
    with open(sample_pdf, "rb") as handle:
        data = {
            "files": (handle, Path(sample_pdf).name),
        }
        return client.post(
            "/api/analyze-files",
            data=data,
            content_type="multipart/form-data",
        )


def test_analyze_files_returns_measurement_data(client, sample_pdf, stub_pdf_dependencies, monkeypatch):
    import backend.routes.__init__ as routes_module

    monkeypatch.setattr(
        routes_module.ai_analyzer,
        "generate_report_summary",
        lambda **_: {"localized_summaries": None},
    )

    response = _post_analyze_request(client, sample_pdf)
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["summaries"], "summaries should not be empty"
    measurement = payload["summaries"][0]["measurement_analysis"]
    assert measurement["measured_values"]["left_dummy"]["HAC"] == pytest.approx(32.5)
    assert measurement["overall_summary"]
    assert measurement["test_conditions_summary"].startswith("Ambient")


def test_analyze_files_handles_ai_failure(client, sample_pdf, stub_pdf_dependencies, monkeypatch):
    import backend.routes.__init__ as routes_module

    def fail_summary(**_):
        raise RuntimeError("ai down")

    monkeypatch.setattr(routes_module.ai_analyzer, "generate_report_summary", fail_summary)

    response = _post_analyze_request(client, sample_pdf)
    assert response.status_code == 200
    payload = response.get_json()
    summary = payload["summaries"][0]
    assert summary["measurement_analysis"]["measured_values"]
    assert summary["measurement_analysis"]["overall_summary"]
    assert summary["measurement_analysis"]["test_conditions_summary"]
    assert summary["ai_summary_mode"] == "plain-text"
    assert summary["ai_raw_summary"] == ""
