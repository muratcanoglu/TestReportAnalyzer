# -*- coding: utf-8 -*-
"""AI-related API routes for the backend."""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

try:  # pragma: no cover - prefer absolute imports
    from backend.ai_providers import analyze_with_ai
    from backend.config import AI_PROVIDER, ai_config_status
except ImportError:  # pragma: no cover - fallback for script execution
    logger.warning("backend.routes.ai falling back to relative imports for AI providers")
    try:
        from ..ai_providers import analyze_with_ai  # type: ignore
        from ..config import AI_PROVIDER, ai_config_status  # type: ignore
    except ImportError:  # pragma: no cover - running from repository root
        logger.warning(
            "backend.routes.ai using local import paths; ensure PYTHONPATH includes project root.",
        )
        from ai_providers import analyze_with_ai  # type: ignore
        from config import AI_PROVIDER, ai_config_status  # type: ignore

bp = Blueprint("ai_routes", __name__, url_prefix="/api")


@bp.route("/health/ai", methods=["GET"])
def health_ai():
    """Return basic status information for AI configuration."""
    status = ai_config_status()
    return jsonify({"ok": True, "ai": status})


@bp.route("/ai/analyze", methods=["POST"])
def ai_analyze():
    """Trigger an AI-powered analysis for the provided text."""
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"ok": False, "error": "text is required"}), 400

    if AI_PROVIDER == "none":
        return jsonify({"ok": False, "error": "AI disabled (AI_PROVIDER=none)"}), 400

    try:
        result = analyze_with_ai(text)
        return jsonify({"ok": True, "result": result})
    except Exception as exc:  # pragma: no cover - runtime errors returned to caller
        return jsonify({"ok": False, "error": str(exc)}), 500
