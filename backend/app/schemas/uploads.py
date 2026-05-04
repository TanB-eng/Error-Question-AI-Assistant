from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

SUPPORTED_UPLOAD_MIME_TYPES = ("image/jpeg", "image/png", "application/pdf")
PDF_MAX_SIZE_BYTES = 10 * 1024 * 1024
IMAGE_MAX_SIZE_BYTES = 5 * 1024 * 1024
PDF_MAX_PAGES = 20
SIGNED_UPLOAD_TTL_SECONDS = 300


class UploadScene(StrEnum):
    MISTAKE = "mistake"
    NOTE = "note"


class UploadSignRequest(BaseModel):
    mime_type: Literal["image/jpeg", "image/png", "application/pdf"]
    scene: UploadScene
    filename: str | None = None


class UploadSignResponse(BaseModel):
    signed_url: str
    object_key: str
    bucket: str
    expires_in: int = Field(le=SIGNED_UPLOAD_TTL_SECONDS)
    max_size_bytes: int
    max_pdf_pages: int | None = None
