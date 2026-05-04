from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel

from app.errors import ErrorCode


class SourceType(StrEnum):
    PHOTO = "photo"
    PDF = "pdf"


class IngestStatus(StrEnum):
    READY = "ready"
    PENDING_CLASSIFICATION = "pending_classification"
    OCR_FAILED = "ocr_failed"


class ItemStatus(StrEnum):
    ACTIVE = "active"
    PENDING = "pending"


class AnswerStatus(StrEnum):
    UNREVIEWED = "unreviewed"
    CORRECTED = "corrected"
    PENDING = "pending"


class TagKind(StrEnum):
    KNOWLEDGE_POINT = "knowledge_point"
    QUESTION_TYPE = "question_type"
    ERROR_CAUSE = "error_cause"


class TagInput(BaseModel):
    kind: TagKind
    name: str


class Tag(BaseModel):
    id: UUID
    kind: TagKind
    name: str
    normalized_name: str


class MistakeCandidate(BaseModel):
    subject_id: int
    question: str
    my_answer: str = ""
    correct_answer: str = ""
    knowledge_points: list[str]
    question_type: str = ""
    difficulty: int | None = None
    error_cause: str = ""
    analysis: str = ""
    page_number: int | None = None


class MistakeIngestRequest(BaseModel):
    object_key: str
    source_type: SourceType
    subject_id: int


class MistakeIngestResponse(BaseModel):
    session_id: UUID
    status: IngestStatus
    ocr_text: str
    candidates: list[MistakeCandidate]
    error_code: ErrorCode | None = None


class MistakeCreateRequest(BaseModel):
    ingest_session_id: UUID | None = None
    subject_id: int
    source_type: SourceType
    object_key: str
    preview_object_key: str | None = None
    ocr_text: str = ""
    question: str
    my_answer: str = ""
    correct_answer: str = ""
    analysis: str = ""
    question_type: str = ""
    difficulty: int | None = None
    error_cause: str = ""
    status: ItemStatus = ItemStatus.ACTIVE
    answer_status: AnswerStatus = AnswerStatus.UNREVIEWED
    annotation: str = ""
    tags: list[TagInput]


class MistakeDetail(BaseModel):
    id: UUID
    subject_id: int
    thumbnail_url: str | None = None
    question_excerpt: str
    answer_status: AnswerStatus
    status: ItemStatus
    tags: list[Tag]
    created_at: datetime
    deleted_at: datetime | None = None
    object_key: str
    image_url: str | None = None
    ocr_text: str
    question: str
    my_answer: str
    correct_answer: str
    analysis: str
    question_type: str = ""
    difficulty: int | None = None
    error_cause: str = ""
    annotation: str = ""
    last_viewed_at: datetime | None = None
