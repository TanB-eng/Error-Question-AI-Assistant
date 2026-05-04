from __future__ import annotations

from enum import StrEnum
from uuid import uuid4

from fastapi import HTTPException


class ErrorCode(StrEnum):
    AUTH_REQUIRED = "AUTH_REQUIRED"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    UPLOAD_UNSUPPORTED_TYPE = "UPLOAD_UNSUPPORTED_TYPE"
    UPLOAD_LIMIT_EXCEEDED = "UPLOAD_LIMIT_EXCEEDED"


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
