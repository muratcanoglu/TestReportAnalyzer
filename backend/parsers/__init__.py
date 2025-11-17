"""Parser helpers for PDF formats."""

import logging

logger = logging.getLogger(__name__)

try:  # pragma: no cover - prefer absolute imports
    from backend.parsers.kielt_parser import parse_page_2_metadata
except ImportError:  # pragma: no cover - fallback for script execution
    logger.warning(
        "backend.parsers falling back to relative imports for parse_page_2_metadata",
    )
    try:
        from .kielt_parser import parse_page_2_metadata  # type: ignore
    except ImportError:  # pragma: no cover - running from repository root
        logger.warning(
            "backend.parsers using local import path; ensure PYTHONPATH includes project root.",
        )
        from kielt_parser import parse_page_2_metadata  # type: ignore

__all__ = ["parse_page_2_metadata"]
