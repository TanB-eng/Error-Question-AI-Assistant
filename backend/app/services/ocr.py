from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

from app.errors import ErrorCode
from app.schemas.uploads import IMAGE_MAX_SIZE_BYTES

OCR_RETRY_COUNT = 1


@dataclass(frozen=True)
class OCRInput:
    object_key: str
    content: bytes
    mime_type: str


@dataclass(frozen=True)
class OCRResult:
    text: str
    status: Literal["ready", "ocr_failed"]
    error_code: ErrorCode | None = None


class OCRProvider(ABC):
    @abstractmethod
    def extract_text(self, ocr_input: OCRInput) -> str:
        """Return OCR text for the given uploaded file bytes."""


class MockOCRProvider(OCRProvider):
    def __init__(self, *, text: str = "题干：已识别的测试题目") -> None:
        self._text = text

    def extract_text(self, ocr_input: OCRInput) -> str:
        return self._text


class OCRService:
    def __init__(self, *, provider: OCRProvider, retry_count: int = OCR_RETRY_COUNT) -> None:
        self._provider = provider
        self._retry_count = retry_count

    def recognize(self, ocr_input: OCRInput) -> OCRResult:
        if _is_image(ocr_input.mime_type) and len(ocr_input.content) > IMAGE_MAX_SIZE_BYTES:
            return OCRResult(
                text="",
                status="ocr_failed",
                error_code=ErrorCode.UPLOAD_LIMIT_EXCEEDED,
            )

        attempts = self._retry_count + 1
        for attempt in range(attempts):
            try:
                text = self._provider.extract_text(ocr_input).strip()
                return OCRResult(text=text, status="ready")
            except Exception:
                if attempt == attempts - 1:
                    return OCRResult(text="", status="ocr_failed", error_code=ErrorCode.OCR_FAILED)
        return OCRResult(text="", status="ocr_failed", error_code=ErrorCode.OCR_FAILED)


def _is_image(mime_type: str) -> bool:
    return mime_type in {"image/jpeg", "image/png"}
