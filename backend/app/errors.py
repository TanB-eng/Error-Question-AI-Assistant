from __future__ import annotations

from enum import StrEnum
from uuid import uuid4

from fastapi import HTTPException


class ErrorCode(StrEnum):
    AUTH_REQUIRED = "AUTH_REQUIRED"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    FORBIDDEN = "FORBIDDEN"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    OBJECT_NOT_FOUND = "OBJECT_NOT_FOUND"
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    UNSUPPORTED_MIME_TYPE = "UNSUPPORTED_MIME_TYPE"
    UPLOAD_UNSUPPORTED_TYPE = "UPLOAD_UNSUPPORTED_TYPE"
    UPLOAD_LIMIT_EXCEEDED = "UPLOAD_LIMIT_EXCEEDED"
    PDF_PARSE_FAILED = "PDF_PARSE_FAILED"
    PDF_TEXT_EXTRACTION_FAILED = "PDF_TEXT_EXTRACTION_FAILED"
    OCR_FAILED = "OCR_FAILED"
    LLM_SCHEMA_INVALID = "LLM_SCHEMA_INVALID"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    CONFLICT = "CONFLICT"


def api_error(status_code: int, code: ErrorCode, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "error": {
                "code": code.value,
                "message": message,
                "request_id": f"req_{uuid4().hex}",
            }
        },
    )
