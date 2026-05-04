from __future__ import annotations

from app.errors import ErrorCode
from app.services.ocr import OCRInput, OCRProvider, OCRService


class BrokenOCRProvider(OCRProvider):
    def extract_text(self, ocr_input: OCRInput) -> str:
        raise RuntimeError("vendor failed")


def test_ocr_failure_allows_manual_save() -> None:
    result = OCRService(provider=BrokenOCRProvider()).recognize(
        OCRInput(
            object_key="mistake/user/uploaded.png",
            content=b"original-image-bytes",
            mime_type="image/png",
        )
    )

    assert result.status == "ocr_failed"
    assert result.text == ""
    assert result.error_code == ErrorCode.OCR_FAILED
