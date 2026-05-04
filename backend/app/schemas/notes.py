from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.errors import ErrorCode
from app.schemas.mistakes import IngestStatus, ItemStatus, SourceType, Tag, TagInput


class NoteClassifyResult(BaseModel):
    subject: str = ""
    content: str = ""
    knowledge_points: list[str] = []


class NoteCandidate(BaseModel):
    subject_id: int
    status: IngestStatus = IngestStatus.READY
    content: str
    knowledge_points: list[str]
    page_number: int | None = None
    error_code: ErrorCode | None = None


class NoteIngestRequest(BaseModel):
    object_key: str
    source_type: SourceType
    subject_id: int


class NoteIngestResponse(BaseModel):
    session_id: UUID
    status: IngestStatus
    ocr_text: str
    candidates: list[NoteCandidate]
    error_code: ErrorCode | None = None


class NoteCreateRequest(BaseModel):
    ingest_session_id: UUID | None = None
    subject_id: int
    source_type: SourceType
    object_key: str
    preview_object_key: str | None = None
    ocr_text: str = ""
    content: str
    status: ItemStatus = ItemStatus.ACTIVE
    tags: list[TagInput]


class NoteUpdateRequest(NoteCreateRequest):
    pass


class NoteListItem(BaseModel):
    id: UUID
    subject_id: int
    thumbnail_url: str | None = None
    content_excerpt: str
    status: ItemStatus = ItemStatus.ACTIVE
    tags: list[Tag]
    created_at: datetime
    deleted_at: datetime | None = None


class NoteDetail(NoteListItem):
    object_key: str
    file_url: str | None = None
    ocr_text: str
    content: str


class NoteListResponse(BaseModel):
    items: list[NoteListItem]
    page: int
    page_size: int
    total: int
