from __future__ import annotations

from app.errors import ErrorCode
from app.services.ocr import OCRInput, OCRProvider, OCRService


class TimeoutOnceProvider(OCRProvider):
    def __init__(self) -> None:
        self.calls = 0

    def extract_text(self, ocr_input: OCRInput) -> str:
        self.calls += 1
        if self.calls == 1:
            raise TimeoutError("timeout")
        return "二次函数顶点式"


def test_ocr_client_retries_once_on_timeout() -> None:
    provider = TimeoutOnceProvider()
    service = OCRService(provider=provider)

    result = service.recognize(
        OCRInput(
            object_key="mistake/user/file.png",
            content=b"image",
            mime_type="image/png",
        )
    )

    assert result.text == "二次函数顶点式"
    assert result.status == "ready"
    assert result.error_code is None
    assert provider.calls == 2


def test_ocr_client_returns_structured_failure_after_retry() -> None:
    class FailingProvider(OCRProvider):
        def extract_text(self, ocr_input: OCRInput) -> str:
            raise TimeoutError("timeout")

    result = OCRService(provider=FailingProvider()).recognize(
        OCRInput(
            object_key="mistake/user/file.png",
            content=b"image",
            mime_type="image/png",
        )
    )

    assert result.status == "ocr_failed"
    assert result.text == ""
    assert result.error_code == ErrorCode.OCR_FAILED
