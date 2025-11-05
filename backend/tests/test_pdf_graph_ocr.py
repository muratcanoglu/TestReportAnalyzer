"""Integration-style tests for the PDF graph OCR utilities."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

fitz = pytest.importorskip("fitz")
pytesseract = pytest.importorskip("pytesseract")
PIL = pytest.importorskip("PIL")  # noqa: F841 - ensures Pillow is available
from PIL import Image, ImageDraw

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.pdf_analyzer import (  # noqa: E402
    _format_graph_ocr_results,
    extract_graph_images,
    ocr_graph_images,
)


def _has_tesseract() -> bool:
    try:
        version = pytesseract.get_tesseract_version()
        return bool(version)
    except (OSError, pytesseract.pytesseract.TesseractNotFoundError):  # type: ignore[attr-defined]
        return False


@pytest.mark.skipif(not _has_tesseract(), reason="Tesseract OCR binary not available")
def test_graph_ocr_extracts_text(tmp_path: Path) -> None:
    """Ensure that OCR returns non-empty text for a generated graph page."""

    image_path = tmp_path / "graph.png"
    pdf_path = tmp_path / "graph.pdf"

    image = Image.new("RGB", (420, 220), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 40, 400, 200), outline="black", width=3)
    draw.text((30, 50), "Force (kN)", fill="black")
    draw.text((30, 90), "Peak: 4.80 kN", fill="black")
    draw.text((30, 130), "Time (s)", fill="black")
    image.save(image_path)

    document = fitz.open()
    page = document.new_page(width=595, height=842)
    rect = fitz.Rect(72, 72, 72 + image.width, 72 + image.height)
    page.insert_image(rect, filename=str(image_path))
    document.save(pdf_path)
    document.close()

    images = extract_graph_images(pdf_path)
    assert images, "PDF grafiğinden görsel çıkarılamadı"

    ocr_results = ocr_graph_images(images)
    assert any(result.get("text") for result in ocr_results), "OCR çıktısı boş"

    formatted = _format_graph_ocr_results(ocr_results)
    assert formatted.strip(), "Biçimlendirilmiş OCR çıktısı boş"
