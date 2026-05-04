from __future__ import annotations

from pathlib import Path

import pytest

from app.services.pdf import PDFProcessingError, PDFQuestionSplitter

REAL_PDF_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "sample_pdfs"


@pytest.mark.manual_smoke
def test_user_supplied_pdf_fixtures_can_be_parsed_manually() -> None:
    pdf_paths = sorted(REAL_PDF_DIR.glob("*.pdf"))
    if not pdf_paths:
        pytest.skip("No user supplied PDF fixtures found")

    splitter = PDFQuestionSplitter()
    for pdf_path in pdf_paths:
        try:
            result = splitter.extract_questions(pdf_path.read_bytes())
        except PDFProcessingError as exc:
            print(f"{pdf_path.name}: structured failure {exc.error_code.value}")
            continue
        print(f"{pdf_path.name}: produced {len(result.candidates)} candidates")
        assert result.text
