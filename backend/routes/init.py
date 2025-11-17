# -*- coding: utf-8 -*-
"""
Routes Blueprint - Main
"""
import logging

from flask import Blueprint

logger = logging.getLogger(__name__)

reports_bp = Blueprint('reports', __name__, url_prefix='/api')

try:  # pragma: no cover - prefer absolute imports
    from backend.routes import ai as _ai_routes  # noqa: F401  # ensure AI routes registered
except ImportError:  # pragma: no cover - fallback for script execution
    logger.warning("backend.routes.init falling back to relative import for ai routes")
    try:
        from . import ai as _ai_routes  # type: ignore # noqa: F401
    except ImportError:  # pragma: no cover - running from repository root
        logger.warning(
            "backend.routes.init using local ai import; ensure PYTHONPATH includes project root.",
        )
        import ai as _ai_routes  # type: ignore # noqa: F401

# Upload endpoint
from flask import request, jsonify
from werkzeug.utils import secure_filename
import os
from datetime import datetime


@reports_bp.route('/upload', methods=['POST'])
def upload_report():
    """PDF yükle ve analiz et"""
    logger.info("=" * 70)
    logger.info("UPLOAD ENDPOINT CALLED")
    logger.info("=" * 70)

    if 'file' not in request.files:
        logger.error("'file' key not found")
        return jsonify({'error': 'Dosya bulunamadı'}), 400

    file = request.files['file']

    if file.filename == '':
        logger.error("Empty filename")
        return jsonify({'error': 'Dosya seçilmedi'}), 400

    if not file.filename.lower().endswith('.pdf'):
        logger.error(f"Invalid file type: {file.filename}")
        return jsonify({'error': 'Sadece PDF dosyaları desteklenir'}), 400

    try:
        # Import yap (circular import önlemek için burada)
        from database import insert_report, update_report_stats, update_report_comprehensive_analysis, insert_test_result
        from pdf_analyzer import analyze_pdf_comprehensive

        # Dosyayı kaydet
        filename = secure_filename(file.filename)
        uploads_dir = 'uploads'
        if not os.path.exists(uploads_dir):
            os.makedirs(uploads_dir)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_filename = f"{timestamp}_{filename}"
        pdf_path = os.path.join(uploads_dir, unique_filename)

        file.save(pdf_path)
        logger.info(f"Dosya kaydedildi: {pdf_path}")

        # Analiz
        logger.info("PDF analizi başlatılıyor...")
        analysis_result = analyze_pdf_comprehensive(pdf_path)

        # Database'e kaydet
        report_id = insert_report(filename=filename, pdf_path=pdf_path)

        update_report_stats(
            report_id,
            analysis_result['basic_stats']['total_tests'],
            analysis_result['basic_stats']['passed'],
            analysis_result['basic_stats']['failed']
        )

        update_report_comprehensive_analysis(
            report_id,
            analysis_result['comprehensive_analysis'],
            analysis_result.get('structured_data'),
            analysis_result.get('tables')
        )

        for test in analysis_result['basic_stats']['tests']:
            insert_test_result(
                report_id,
                test['name'],
                test['status'],
                test.get('error_message'),
                test.get('failure_reason'),
                test.get('suggested_fix'),
                test.get('ai_provider', 'rule-based')
            )

        logger.info(f"Rapor kaydedildi: ID={report_id}")
        logger.info("=" * 70)

        return jsonify({
            'success': True,
            'report_id': report_id,
            'filename': filename,
            'basic_stats': analysis_result['basic_stats'],
            'message': 'PDF başarıyla yüklendi ve analiz edildi'
        }), 200

    except Exception as e:
        logger.error(f"Upload hatası: {e}", exc_info=True)
        return jsonify({
            'error': 'Yükleme başarısız oldu',
            'detail': str(e)
        }), 500


@reports_bp.route('/reports', methods=['GET'])
def get_reports():
    """Tüm raporları listele"""
    from database import get_all_reports
    try:
        reports = get_all_reports()
        return jsonify({'reports': reports}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@reports_bp.route('/reports/<int:report_id>', methods=['GET'])
def get_report(report_id):
    """Tek rapor detayı"""
    from database import get_report_by_id
    try:
        report = get_report_by_id(report_id)
        if not report:
            return jsonify({'error': 'Rapor bulunamadı'}), 404

        detailed_analysis = {
            'test_conditions': report.get('test_conditions_summary', ''),
            'graphs': report.get('graphs_description', ''),
            'results': report.get('detailed_results', ''),
            'improvements': report.get('improvement_suggestions', '')
        }

        response = {
            'report': {
                'id': report['id'],
                'filename': report['filename'],
                'upload_date': report['upload_date'],
                'total_tests': report['total_tests'],
                'passed_tests': report['passed_tests'],
                'failed_tests': report['failed_tests'],
                'tests': report.get('tests', [])
            },
            'detailed_analysis': detailed_analysis
        }

        return jsonify(response), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@reports_bp.route('/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({
        'status': 'ok',
        'message': 'Backend çalışıyor',
        'timestamp': datetime.now().isoformat()
    })
