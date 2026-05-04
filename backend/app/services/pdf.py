from __future__ import annotations

import re
from dataclasses import dataclass
from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.errors import ErrorCode
from app.schemas.uploads import PDF_MAX_PAGES, PDF_MAX_SIZE_BYTES

QUESTION_SPLIT_PATTERN = re.compile(
    r"(?=(?:^|\s)(?:\d+[\.\u3001]|题\s*\d+))",
    flags=re.MULTILINE,
)


class PDFProcessingError(RuntimeError):
    def __init__(self, error_code: ErrorCode) -> None:
        super().__init__(error_code.value)
        self.error_code = error_code


@dataclass(frozen=True)
class PDFQuestionCandidate:
    question_text: str
    page_number: int | None = None


@dataclass(frozen=True)
class PDFExtractionResult:
    text: str
    candidates: list[PDFQuestionCandidate]


class PDFQuestionSplitter:
    def extract_questions(self, content: bytes) -> PDFExtractionResult:
        if len(content) > PDF_MAX_SIZE_BYTES:
            raise PDFProcessingError(ErrorCode.UPLOAD_LIMIT_EXCEEDED)

        try:
            reader = PdfReader(BytesIO(content))
            page_count = len(reader.pages)
            if page_count > PDF_MAX_PAGES:
                raise PDFProcessingError(ErrorCode.UPLOAD_LIMIT_EXCEEDED)
            page_texts = [
                (page_number + 1, reader.pages[page_number].extract_text() or "")
                for page_number in range(page_count)
            ]
        except PDFProcessingError:
            raise
        except (PdfReadError, OSError, ValueError) as exc:
            raise PDFProcessingError(ErrorCode.PDF_PARSE_FAILED) from exc

        full_text = "\n".join(text for _, text in page_texts if text.strip()).strip()
        candidates: list[PDFQuestionCandidate] = []
        for page_number, text in page_texts:
            for question_text in split_question_text(text):
                candidates.append(
                    PDFQuestionCandidate(
                        question_text=question_text,
                        page_number=page_number,
                    )
                )

        if not candidates:
            raise PDFProcessingError(ErrorCode.PDF_TEXT_EXTRACTION_FAILED)
        return PDFExtractionResult(text=full_text, candidates=candidates)


def split_question_text(text: str) -> list[str]:
    compacted = re.sub(r"\s+", " ", text).strip()
    if not compacted:
        return []

    starts = [match.start() for match in QUESTION_SPLIT_PATTERN.finditer(compacted)]
    starts = sorted(set(starts))
    if len(starts) <= 1:
        return [compacted]

    parts: list[str] = []
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(compacted)
        part = compacted[start:end].strip()
        if part:
            parts.append(part)
    return parts or [compacted]
