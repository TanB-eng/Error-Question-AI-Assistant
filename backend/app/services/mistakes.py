from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from app.core.supabase import SupabaseRestClient
from app.schemas.mistakes import (
    AnswerStatus,
    ItemStatus,
    MistakeCreateRequest,
    MistakeDetail,
    Tag,
    TagKind,
)
from app.services.tag_normalizer import TagNormalizerService, TagRecord


class MistakeCreateConflictError(RuntimeError):
    """Raised when an ingest session has already been saved."""


class MistakeObjectKeyOwnershipError(RuntimeError):
    """Raised when a mistake object key does not belong to the current user."""


class MistakeRepository(Protocol):
    def is_ingest_session_used(self, *, ingest_session_id: str) -> bool: ...

    def insert_mistake(
        self, *, user_id: str, request: MistakeCreateRequest
    ) -> dict[str, object]: ...

    def link_tag(self, *, user_id: str, mistake_id: str, tag_id: str) -> None: ...

    def mark_ingest_session_saved(self, *, ingest_session_id: str) -> None: ...


class InMemoryMistakeRepository:
    def __init__(self) -> None:
        self.mistakes: list[dict[str, object]] = []
        self.mistake_tags: list[dict[str, str]] = []
        self.used_sessions: set[str] = set()

    def is_ingest_session_used(self, *, ingest_session_id: str) -> bool:
        return ingest_session_id in self.used_sessions

    def insert_mistake(self, *, user_id: str, request: MistakeCreateRequest) -> dict[str, object]:
        now = datetime.now(UTC)
        row: dict[str, object] = {
            "id": str(uuid4()),
            "user_id": user_id,
            "subject_id": request.subject_id,
            "source_type": request.source_type.value,
            "object_key": request.object_key,
            "preview_object_key": request.preview_object_key,
            "ocr_text": request.ocr_text,
            "question": request.question,
            "my_answer": request.my_answer,
            "correct_answer": request.correct_answer,
            "analysis": request.analysis,
            "question_type": request.question_type,
            "difficulty": request.difficulty,
            "error_cause": request.error_cause,
            "status": request.status.value,
            "answer_status": request.answer_status.value,
            "annotation": request.annotation,
            "created_at": now,
            "deleted_at": None,
        }
        self.mistakes.append(row)
        return row

    def link_tag(self, *, user_id: str, mistake_id: str, tag_id: str) -> None:
        self.mistake_tags.append(
            {
                "user_id": user_id,
                "mistake_id": mistake_id,
                "tag_id": tag_id,
            }
        )

    def mark_ingest_session_saved(self, *, ingest_session_id: str) -> None:
        self.used_sessions.add(ingest_session_id)


class SupabaseMistakeRepository:
    def __init__(self, *, client: SupabaseRestClient) -> None:
        self._client = client

    def is_ingest_session_used(self, *, ingest_session_id: str) -> bool:
        response = self._client.request(
            "GET",
            "/ingest_sessions",
            params={"id": f"eq.{ingest_session_id}", "status": "eq.saved", "select": "id"},
        )
        response.raise_for_status()
        payload = response.json()
        return isinstance(payload, list) and len(payload) > 0

    def insert_mistake(self, *, user_id: str, request: MistakeCreateRequest) -> dict[str, object]:
        response = self._client.request(
            "POST",
            "/mistakes",
            headers={"Prefer": "return=representation"},
            json={
                "user_id": user_id,
                "subject_id": request.subject_id,
                "source_type": request.source_type.value,
                "object_key": request.object_key,
                "preview_object_key": request.preview_object_key,
                "ocr_text": request.ocr_text,
                "question": request.question,
                "my_answer": request.my_answer,
                "correct_answer": request.correct_answer,
                "analysis": request.analysis,
                "question_type": request.question_type,
                "difficulty": request.difficulty,
                "error_cause": request.error_cause,
                "status": request.status.value,
                "answer_status": request.answer_status.value,
                "annotation": request.annotation,
            },
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list) or not payload or not isinstance(payload[0], dict):
            raise RuntimeError("Invalid mistake insert response")
        return payload[0]

    def link_tag(self, *, user_id: str, mistake_id: str, tag_id: str) -> None:
        response = self._client.request(
            "POST",
            "/mistake_tags",
            headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
            json={"user_id": user_id, "mistake_id": mistake_id, "tag_id": tag_id},
        )
        response.raise_for_status()

    def mark_ingest_session_saved(self, *, ingest_session_id: str) -> None:
        response = self._client.request(
            "PATCH",
            "/ingest_sessions",
            params={"id": f"eq.{ingest_session_id}"},
            headers={"Prefer": "return=minimal"},
            json={"status": "saved"},
        )
        response.raise_for_status()


class MistakeCreateService:
    def __init__(
        self,
        *,
        mistake_repository: MistakeRepository,
        tag_normalizer: TagNormalizerService,
    ) -> None:
        self._mistake_repository = mistake_repository
        self._tag_normalizer = tag_normalizer

    def create_mistake(self, *, user_id: str, request: MistakeCreateRequest) -> MistakeDetail:
        _ensure_mistake_object_key_owned_by_user(
            object_key=request.object_key,
            user_id=user_id,
        )
        session_used = (
            request.ingest_session_id is not None
            and self._mistake_repository.is_ingest_session_used(
                ingest_session_id=str(request.ingest_session_id)
            )
        )
        if session_used:
            raise MistakeCreateConflictError("ingest session already used")

        mistake = self._mistake_repository.insert_mistake(user_id=user_id, request=request)
        tag_records = self._tag_normalizer.upsert_tags(
            user_id=user_id,
            subject_id=request.subject_id,
            kind="knowledge_point",
            names=[tag.name for tag in request.tags if tag.kind == "knowledge_point"],
        )
        for tag in tag_records:
            self._mistake_repository.link_tag(
                user_id=user_id,
                mistake_id=str(mistake["id"]),
                tag_id=tag.id,
            )
        if request.ingest_session_id is not None:
            self._mistake_repository.mark_ingest_session_saved(
                ingest_session_id=str(request.ingest_session_id)
            )
        return _detail_from_row(mistake, tag_records)


def _detail_from_row(row: dict[str, object], tag_records: list[TagRecord]) -> MistakeDetail:
    question = str(row["question"])
    return MistakeDetail(
        id=UUID(str(row["id"])),
        subject_id=_required_int(row["subject_id"]),
        question_excerpt=question[:40],
        answer_status=AnswerStatus(str(row.get("answer_status", "unreviewed"))),
        status=ItemStatus(str(row.get("status", "active"))),
        tags=[
            Tag(
                id=UUID(tag.id),
                kind=TagKind(tag.kind),
                name=tag.name,
                normalized_name=tag.normalized_name,
            )
            for tag in tag_records
        ],
        created_at=_datetime_from_row(row["created_at"]),
        deleted_at=None,
        object_key=str(row["object_key"]),
        image_url=None,
        ocr_text=str(row.get("ocr_text", "")),
        question=question,
        my_answer=str(row.get("my_answer", "")),
        correct_answer=str(row.get("correct_answer", "")),
        analysis=str(row.get("analysis", "")),
        question_type=str(row.get("question_type", "")),
        difficulty=_optional_int(row.get("difficulty")),
        error_cause=str(row.get("error_cause", "")),
        annotation=str(row.get("annotation", "")),
        last_viewed_at=None,
    )


def _datetime_from_row(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _required_int(value: object) -> int:
    if isinstance(value, int):
        return value
    return int(str(value))


def _ensure_mistake_object_key_owned_by_user(*, object_key: str, user_id: str) -> None:
    expected_prefix = f"mistake/{user_id}/"
    if not object_key.startswith(expected_prefix):
        raise MistakeObjectKeyOwnershipError("object_key is not owned by user")
