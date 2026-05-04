from __future__ import annotations

from pathlib import Path

import pytest
from pypdf import PdfWriter

from app.errors import ErrorCode
from app.schemas.uploads import PDF_MAX_PAGES, PDF_MAX_SIZE_BYTES
from app.services.pdf import PDFProcessingError, PDFQuestionSplitter, split_question_text

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures"
SAMPLE_PDF = FIXTURE_DIR / "sample_exam.pdf"
IMAGE_ONLY_PDF = FIXTURE_DIR / "image_only.pdf"


def test_pdf_split_returns_multiple_candidates() -> None:
    result = PDFQuestionSplitter().extract_questions(SAMPLE_PDF.read_bytes())

    assert len(result.candidates) >= 2
    assert result.candidates[0].question_text.startswith("1.")
    assert result.candidates[1].question_text.startswith("2.")
    assert all(candidate.page_number == 1 for candidate in result.candidates)


def test_pdf_over_limit_returns_upload_limit_error() -> None:
    writer = PdfWriter()
    for _ in range(PDF_MAX_PAGES + 1):
        writer.add_blank_page(width=72, height=72)
    pdf_path = FIXTURE_DIR / "over_limit_pages.pdf"
    try:
        with pdf_path.open("wb") as file:
            writer.write(file)

        with pytest.raises(PDFProcessingError) as exc_info:
            PDFQuestionSplitter().extract_questions(pdf_path.read_bytes())
    finally:
        pdf_path.unlink(missing_ok=True)

    assert exc_info.value.error_code == ErrorCode.UPLOAD_LIMIT_EXCEEDED


def test_pdf_size_over_limit_returns_upload_limit_error() -> None:
    oversized = b"%PDF-1.4\n" + b"x" * PDF_MAX_SIZE_BYTES

    with pytest.raises(PDFProcessingError) as exc_info:
        PDFQuestionSplitter().extract_questions(oversized)

    assert exc_info.value.error_code == ErrorCode.UPLOAD_LIMIT_EXCEEDED


def test_pdf_with_no_text_layer_returns_extraction_failed() -> None:
    with pytest.raises(PDFProcessingError) as exc_info:
        PDFQuestionSplitter().extract_questions(IMAGE_ONLY_PDF.read_bytes())

    assert exc_info.value.error_code == ErrorCode.PDF_TEXT_EXTRACTION_FAILED


def test_broken_pdf_returns_parse_failed() -> None:
    with pytest.raises(PDFProcessingError) as exc_info:
        PDFQuestionSplitter().extract_questions(b"not a pdf")

    assert exc_info.value.error_code == ErrorCode.PDF_PARSE_FAILED


def test_unsplittable_text_returns_single_candidate() -> None:
    assert split_question_text("This worksheet has no numbering") == [
        "This worksheet has no numbering"
    ]
