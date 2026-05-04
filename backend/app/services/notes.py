from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, Protocol
from uuid import UUID, uuid4

from app.core.supabase import SupabaseRestClient
from app.errors import ErrorCode
from app.schemas.mistakes import IngestStatus, ItemStatus, Tag, TagKind
from app.schemas.notes import (
    NoteCandidate,
    NoteClassifyResult,
    NoteCreateRequest,
    NoteDetail,
    NoteIngestRequest,
    NoteIngestResponse,
    NoteListItem,
    NoteListResponse,
    NoteUpdateRequest,
)
from app.schemas.uploads import (
    IMAGE_MAX_SIZE_BYTES,
    PDF_MAX_SIZE_BYTES,
    SUPPORTED_UPLOAD_MIME_TYPES,
)
from app.services.ingestion import (
    FileStore,
    IngestSessionRepository,
    ObjectKeyOwnershipError,
    StoredObject,
)
from app.services.llm.deepseek import LLMClassificationError
from app.services.ocr import OCRInput, OCRService
from app.services.pdf import PDFProcessingError, PDFQuestionSplitter
from app.services.tag_normalizer import TagNormalizerService, TagRecord


class NoteClassifierClient(Protocol):
    def classify_note_text(
        self,
        *,
        user_id: str,
        ingest_session_id: str | None,
        ocr_text: str,
    ) -> NoteClassifyResult: ...


@dataclass(frozen=True)
class NoteClassificationOutcome:
    status: Literal["ready", "pending_classification"]
    result: NoteClassifyResult | None
    error_code: ErrorCode | None = None


class NoteClassifier(Protocol):
    def classify(
        self,
        *,
        user_id: str,
        ingest_session_id: str | None,
        ocr_text: str,
    ) -> NoteClassificationOutcome: ...


class NoteClassifierService:
    def __init__(self, *, deepseek_client: NoteClassifierClient) -> None:
        self._deepseek_client = deepseek_client

    def classify(
        self,
        *,
        user_id: str,
        ingest_session_id: str | None,
        ocr_text: str,
    ) -> NoteClassificationOutcome:
        try:
            result = self._deepseek_client.classify_note_text(
                user_id=user_id,
                ingest_session_id=ingest_session_id,
                ocr_text=ocr_text,
            )
            return NoteClassificationOutcome(status="ready", result=result)
        except LLMClassificationError as exc:
            return NoteClassificationOutcome(
                status="pending_classification",
                result=None,
                error_code=exc.error_code,
            )


class NoteIngestionService:
    def __init__(
        self,
        *,
        file_store: FileStore,
        session_repository: IngestSessionRepository,
        ocr_service: OCRService,
        classifier: NoteClassifier,
        pdf_splitter: PDFQuestionSplitter | None = None,
    ) -> None:
        self._file_store = file_store
        self._session_repository = session_repository
        self._ocr_service = ocr_service
        self._classifier = classifier
        self._pdf_splitter = pdf_splitter if pdf_splitter is not None else PDFQuestionSplitter()

    def ingest_note(self, *, user_id: str, request: NoteIngestRequest) -> NoteIngestResponse:
        _ensure_note_object_key_owned_by_user(object_key=request.object_key, user_id=user_id)
        stored_object = self._file_store.get_object(request.object_key)
        if stored_object.mime_type not in SUPPORTED_UPLOAD_MIME_TYPES:
            session_id = self._create_session(
                user_id=user_id,
                request=request,
                mime_type=stored_object.mime_type,
            )
            return self._finish(
                session_id=session_id,
                status=IngestStatus.OCR_FAILED,
                ocr_text="",
                candidates=[],
                error_code=ErrorCode.UNSUPPORTED_MIME_TYPE,
                session_status="failed",
            )

        session_id = self._create_session(
            user_id=user_id,
            request=request,
            mime_type=stored_object.mime_type,
        )
        if _is_oversized(stored_object):
            return self._finish(
                session_id=session_id,
                status=IngestStatus.OCR_FAILED,
                ocr_text="",
                candidates=[],
                error_code=ErrorCode.UPLOAD_LIMIT_EXCEEDED,
                session_status="failed",
            )

        if stored_object.mime_type == "application/pdf":
            try:
                ocr_text = self._pdf_splitter.extract_questions(stored_object.content).text
            except PDFProcessingError as exc:
                return self._finish(
                    session_id=session_id,
                    status=IngestStatus.OCR_FAILED,
                    ocr_text="",
                    candidates=[],
                    error_code=exc.error_code,
                    session_status="failed",
                )
        else:
            ocr_result = self._ocr_service.recognize(
                OCRInput(
                    object_key=request.object_key,
                    content=stored_object.content,
                    mime_type=stored_object.mime_type,
                )
            )
            if ocr_result.status == "ocr_failed":
                return self._finish(
                    session_id=session_id,
                    status=IngestStatus.OCR_FAILED,
                    ocr_text="",
                    candidates=[],
                    error_code=ocr_result.error_code,
                    session_status="failed",
                )
            ocr_text = ocr_result.text

        classification = self._classifier.classify(
            user_id=user_id,
            ingest_session_id=session_id,
            ocr_text=ocr_text,
        )
        if classification.status == "pending_classification" or classification.result is None:
            candidate = _manual_note_candidate(
                subject_id=request.subject_id,
                content=ocr_text,
                status=IngestStatus.PENDING_CLASSIFICATION,
                error_code=classification.error_code,
            )
            return self._finish(
                session_id=session_id,
                status=IngestStatus.PENDING_CLASSIFICATION,
                ocr_text=ocr_text,
                candidates=[candidate],
                error_code=classification.error_code,
                session_status="pending",
            )

        candidate = NoteCandidate(
            subject_id=request.subject_id,
            status=IngestStatus.READY,
            content=classification.result.content,
            knowledge_points=classification.result.knowledge_points,
        )
        return self._finish(
            session_id=session_id,
            status=IngestStatus.READY,
            ocr_text=ocr_text,
            candidates=[candidate],
            error_code=None,
            session_status="classified",
        )

    def _create_session(
        self,
        *,
        user_id: str,
        request: NoteIngestRequest,
        mime_type: str,
    ) -> str:
        return self._session_repository.create_session(
            user_id=user_id,
            scene="note",
            source_type=request.source_type.value,
            subject_id=request.subject_id,
            object_key=request.object_key,
            mime_type=mime_type,
        )

    def _finish(
        self,
        *,
        session_id: str,
        status: IngestStatus,
        ocr_text: str,
        candidates: list[NoteCandidate],
        error_code: ErrorCode | None,
        session_status: str,
    ) -> NoteIngestResponse:
        self._session_repository.update_session(
            session_id=session_id,
            status=session_status,
            ocr_text=ocr_text,
            candidate_payload={
                "status": status.value,
                "candidates": [candidate.model_dump(mode="json") for candidate in candidates],
            },
            error_code=error_code,
        )
        return NoteIngestResponse(
            session_id=UUID(session_id),
            status=status,
            ocr_text=ocr_text,
            candidates=candidates,
            error_code=error_code,
        )


def _manual_note_candidate(
    *,
    subject_id: int,
    content: str,
    status: IngestStatus,
    error_code: ErrorCode | None,
) -> NoteCandidate:
    return NoteCandidate(
        subject_id=subject_id,
        status=status,
        content=content,
        knowledge_points=[],
        error_code=error_code,
    )


def _is_oversized(stored_object: StoredObject) -> bool:
    limits = {
        "image/jpeg": IMAGE_MAX_SIZE_BYTES,
        "image/png": IMAGE_MAX_SIZE_BYTES,
        "application/pdf": PDF_MAX_SIZE_BYTES,
    }
    limit = limits.get(stored_object.mime_type)
    return limit is not None and len(stored_object.content) > limit


def _ensure_note_object_key_owned_by_user(*, object_key: str, user_id: str) -> None:
    expected = f"note/{user_id}/"
    if not object_key.startswith(expected):
        raise ObjectKeyOwnershipError("note object key is not owned by current user")


class NoteCreateConflictError(RuntimeError):
    """Raised when an ingest session has already been saved."""


class NoteNotFoundError(RuntimeError):
    """Raised when a note is missing, deleted, or not owned by the current user."""


class NoteObjectKeyOwnershipError(RuntimeError):
    """Raised when a note object key does not belong to the current user."""


class NoteRepository(Protocol):
    def is_ingest_session_used(self, *, ingest_session_id: str) -> bool: ...

    def insert_note(self, *, user_id: str, request: NoteCreateRequest) -> dict[str, object]: ...

    def link_tag(self, *, user_id: str, note_id: str, tag_id: str) -> None: ...

    def replace_tags(self, *, user_id: str, note_id: str, tag_ids: list[str]) -> None: ...

    def mark_ingest_session_saved(self, *, ingest_session_id: str) -> None: ...

    def list_notes(
        self,
        *,
        user_id: str,
        subject_id: int | None,
        tag_id: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[dict[str, object]], int]: ...

    def get_note(self, *, user_id: str, note_id: str) -> dict[str, object]: ...

    def update_note(
        self,
        *,
        user_id: str,
        note_id: str,
        request: NoteUpdateRequest,
    ) -> dict[str, object]: ...

    def soft_delete_note(self, *, user_id: str, note_id: str) -> None: ...


class InMemoryNoteRepository:
    def __init__(self) -> None:
        self.notes: list[dict[str, object]] = []
        self.note_tags: list[dict[str, object]] = []
        self.used_sessions: set[str] = set()

    def is_ingest_session_used(self, *, ingest_session_id: str) -> bool:
        return ingest_session_id in self.used_sessions

    def insert_note(self, *, user_id: str, request: NoteCreateRequest) -> dict[str, object]:
        now = datetime.now(UTC)
        row: dict[str, object] = {
            "id": str(uuid4()),
            "user_id": user_id,
            "subject_id": request.subject_id,
            "source_type": request.source_type.value,
            "object_key": request.object_key,
            "preview_object_key": request.preview_object_key,
            "ocr_text": request.ocr_text,
            "content": request.content,
            "status": request.status.value,
            "created_at": now,
            "deleted_at": None,
        }
        self.notes.append(row)
        return row

    def link_tag(self, *, user_id: str, note_id: str, tag_id: str) -> None:
        self.note_tags.append(
            {"user_id": user_id, "note_id": note_id, "tag_id": tag_id, "deleted_at": None}
        )

    def replace_tags(self, *, user_id: str, note_id: str, tag_ids: list[str]) -> None:
        self.note_tags = [
            link
            for link in self.note_tags
            if not (link["user_id"] == user_id and link["note_id"] == note_id)
        ]
        for tag_id in tag_ids:
            self.link_tag(user_id=user_id, note_id=note_id, tag_id=tag_id)

    def mark_ingest_session_saved(self, *, ingest_session_id: str) -> None:
        self.used_sessions.add(ingest_session_id)

    def list_notes(
        self,
        *,
        user_id: str,
        subject_id: int | None,
        tag_id: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[dict[str, object]], int]:
        rows = [
            note
            for note in self.notes
            if note["user_id"] == user_id
            and note.get("deleted_at") is None
            and (subject_id is None or int(str(note["subject_id"])) == subject_id)
            and (tag_id is None or self._note_has_tag(note_id=str(note["id"]), tag_id=tag_id))
        ]
        rows.sort(key=lambda row: _datetime_from_row(row["created_at"]), reverse=True)
        start = (page - 1) * page_size
        return rows[start : start + page_size], len(rows)

    def get_note(self, *, user_id: str, note_id: str) -> dict[str, object]:
        for note in self.notes:
            if (
                note["user_id"] == user_id
                and note["id"] == note_id
                and note.get("deleted_at") is None
            ):
                return note
        raise NoteNotFoundError("note not found")

    def update_note(
        self,
        *,
        user_id: str,
        note_id: str,
        request: NoteUpdateRequest,
    ) -> dict[str, object]:
        note = self.get_note(user_id=user_id, note_id=note_id)
        note.update(
            {
                "subject_id": request.subject_id,
                "source_type": request.source_type.value,
                "object_key": request.object_key,
                "preview_object_key": request.preview_object_key,
                "ocr_text": request.ocr_text,
                "content": request.content,
                "status": request.status.value,
            }
        )
        return note

    def soft_delete_note(self, *, user_id: str, note_id: str) -> None:
        note = self.get_note(user_id=user_id, note_id=note_id)
        note["deleted_at"] = datetime.now(UTC)

    def _note_has_tag(self, *, note_id: str, tag_id: str) -> bool:
        return any(
            link["note_id"] == note_id
            and link["tag_id"] == tag_id
            and link.get("deleted_at") is None
            for link in self.note_tags
        )


class SupabaseNoteRepository:
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

    def insert_note(self, *, user_id: str, request: NoteCreateRequest) -> dict[str, object]:
        response = self._client.request(
            "POST",
            "/notes",
            headers={"Prefer": "return=representation"},
            json=_note_payload(user_id=user_id, request=request),
        )
        response.raise_for_status()
        return _first_row(response.json(), "Invalid note insert response")

    def link_tag(self, *, user_id: str, note_id: str, tag_id: str) -> None:
        response = self._client.request(
            "POST",
            "/note_tags",
            headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
            json={"user_id": user_id, "note_id": note_id, "tag_id": tag_id},
        )
        response.raise_for_status()

    def replace_tags(self, *, user_id: str, note_id: str, tag_ids: list[str]) -> None:
        response = self._client.request(
            "PATCH",
            "/note_tags",
            params={"user_id": f"eq.{user_id}", "note_id": f"eq.{note_id}"},
            headers={"Prefer": "return=minimal"},
            json={"deleted_at": datetime.now(UTC).isoformat()},
        )
        response.raise_for_status()
        for tag_id in tag_ids:
            self.link_tag(user_id=user_id, note_id=note_id, tag_id=tag_id)

    def mark_ingest_session_saved(self, *, ingest_session_id: str) -> None:
        response = self._client.request(
            "PATCH",
            "/ingest_sessions",
            params={"id": f"eq.{ingest_session_id}"},
            headers={"Prefer": "return=minimal"},
            json={"status": "saved"},
        )
        response.raise_for_status()

    def list_notes(
        self,
        *,
        user_id: str,
        subject_id: int | None,
        tag_id: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[dict[str, object]], int]:
        params: dict[str, str] = {
            "user_id": f"eq.{user_id}",
            "deleted_at": "is.null",
            "order": "created_at.desc",
            "limit": str(page_size),
            "offset": str((page - 1) * page_size),
        }
        if subject_id is not None:
            params["subject_id"] = f"eq.{subject_id}"
        response = self._client.request("GET", "/notes", params=params)
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list):
            raise RuntimeError("Invalid note list response")
        if tag_id is not None:
            rows = [
                row
                for row in rows
                if self._note_has_tag(note_id=str(row["id"]), tag_id=tag_id)
            ]
        return rows, len(rows)

    def get_note(self, *, user_id: str, note_id: str) -> dict[str, object]:
        response = self._client.request(
            "GET",
            "/notes",
            params={"id": f"eq.{note_id}", "user_id": f"eq.{user_id}", "deleted_at": "is.null"},
        )
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
            raise NoteNotFoundError("note not found")
        return rows[0]

    def update_note(
        self,
        *,
        user_id: str,
        note_id: str,
        request: NoteUpdateRequest,
    ) -> dict[str, object]:
        response = self._client.request(
            "PATCH",
            "/notes",
            params={"id": f"eq.{note_id}", "user_id": f"eq.{user_id}", "deleted_at": "is.null"},
            headers={"Prefer": "return=representation"},
            json=_note_payload(user_id=user_id, request=request),
        )
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
            raise NoteNotFoundError("note not found")
        return rows[0]

    def soft_delete_note(self, *, user_id: str, note_id: str) -> None:
        response = self._client.request(
            "PATCH",
            "/notes",
            params={"id": f"eq.{note_id}", "user_id": f"eq.{user_id}", "deleted_at": "is.null"},
            headers={"Prefer": "return=representation"},
            json={"deleted_at": datetime.now(UTC).isoformat()},
        )
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list) or not rows:
            raise NoteNotFoundError("note not found")

    def _note_has_tag(self, *, note_id: str, tag_id: str) -> bool:
        response = self._client.request(
            "GET",
            "/note_tags",
            params={
                "note_id": f"eq.{note_id}",
                "tag_id": f"eq.{tag_id}",
                "deleted_at": "is.null",
                "select": "id",
            },
        )
        response.raise_for_status()
        rows = response.json()
        return isinstance(rows, list) and bool(rows)


class NoteCreateService:
    def __init__(
        self,
        *,
        note_repository: NoteRepository,
        tag_normalizer: TagNormalizerService,
    ) -> None:
        self._note_repository = note_repository
        self._tag_normalizer = tag_normalizer

    def create_note(self, *, user_id: str, request: NoteCreateRequest) -> NoteDetail:
        _ensure_create_object_key_owned_by_user(object_key=request.object_key, user_id=user_id)
        if request.ingest_session_id is not None and self._note_repository.is_ingest_session_used(
            ingest_session_id=str(request.ingest_session_id)
        ):
            raise NoteCreateConflictError("ingest session already used")

        note = self._note_repository.insert_note(user_id=user_id, request=request)
        tag_records = _upsert_knowledge_tags(
            tag_normalizer=self._tag_normalizer,
            user_id=user_id,
            subject_id=request.subject_id,
            tag_names=[tag.name for tag in request.tags if tag.kind == "knowledge_point"],
        )
        for tag in tag_records:
            self._note_repository.link_tag(
                user_id=user_id,
                note_id=str(note["id"]),
                tag_id=tag.id,
            )
        if request.ingest_session_id is not None:
            self._note_repository.mark_ingest_session_saved(
                ingest_session_id=str(request.ingest_session_id)
            )
        return _detail_from_row(note, tag_records)


class NoteCrudService:
    def __init__(
        self,
        *,
        note_repository: NoteRepository,
        tag_normalizer: TagNormalizerService,
    ) -> None:
        self._note_repository = note_repository
        self._tag_normalizer = tag_normalizer

    def list_notes(
        self,
        *,
        user_id: str,
        subject_id: int | None = None,
        tag_id: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> NoteListResponse:
        rows, total = self._note_repository.list_notes(
            user_id=user_id,
            subject_id=subject_id,
            tag_id=tag_id,
            page=page,
            page_size=page_size,
        )
        return NoteListResponse(
            items=[_list_item_from_row(row, []) for row in rows],
            page=page,
            page_size=page_size,
            total=total,
        )

    def get_note(self, *, user_id: str, note_id: str) -> NoteDetail:
        row = self._note_repository.get_note(user_id=user_id, note_id=note_id)
        return _detail_from_row(row, [])

    def update_note(
        self,
        *,
        user_id: str,
        note_id: str,
        request: NoteUpdateRequest,
    ) -> NoteDetail:
        _ensure_create_object_key_owned_by_user(object_key=request.object_key, user_id=user_id)
        note = self._note_repository.update_note(user_id=user_id, note_id=note_id, request=request)
        tag_records = _upsert_knowledge_tags(
            tag_normalizer=self._tag_normalizer,
            user_id=user_id,
            subject_id=request.subject_id,
            tag_names=[tag.name for tag in request.tags if tag.kind == "knowledge_point"],
        )
        self._note_repository.replace_tags(
            user_id=user_id,
            note_id=note_id,
            tag_ids=[tag.id for tag in tag_records],
        )
        return _detail_from_row(note, tag_records)

    def delete_note(self, *, user_id: str, note_id: str) -> None:
        self._note_repository.soft_delete_note(user_id=user_id, note_id=note_id)


def _upsert_knowledge_tags(
    *,
    tag_normalizer: TagNormalizerService,
    user_id: str,
    subject_id: int,
    tag_names: list[str],
) -> list[TagRecord]:
    return tag_normalizer.upsert_tags(
        user_id=user_id,
        subject_id=subject_id,
        kind="knowledge_point",
        names=tag_names,
    )


def _detail_from_row(row: dict[str, object], tag_records: list[TagRecord]) -> NoteDetail:
    content = str(row["content"])
    return NoteDetail(
        id=UUID(str(row["id"])),
        subject_id=_required_int(row["subject_id"]),
        content_excerpt=content[:40],
        status=ItemStatus(str(row.get("status", "active"))),
        tags=[_tag_from_record(tag) for tag in tag_records],
        created_at=_datetime_from_row(row["created_at"]),
        deleted_at=_optional_datetime(row.get("deleted_at")),
        object_key=str(row["object_key"]),
        ocr_text=str(row.get("ocr_text", "")),
        content=content,
    )


def _list_item_from_row(row: dict[str, object], tag_records: list[TagRecord]) -> NoteListItem:
    content = str(row["content"])
    return NoteListItem(
        id=UUID(str(row["id"])),
        subject_id=_required_int(row["subject_id"]),
        content_excerpt=content[:40],
        status=ItemStatus(str(row.get("status", "active"))),
        tags=[_tag_from_record(tag) for tag in tag_records],
        created_at=_datetime_from_row(row["created_at"]),
        deleted_at=_optional_datetime(row.get("deleted_at")),
    )


def _tag_from_record(tag: TagRecord) -> Tag:
    return Tag(
        id=UUID(tag.id),
        kind=TagKind(tag.kind),
        name=tag.name,
        normalized_name=tag.normalized_name,
    )


def _note_payload(*, user_id: str, request: NoteCreateRequest) -> dict[str, object]:
    return {
        "user_id": user_id,
        "subject_id": request.subject_id,
        "source_type": request.source_type.value,
        "object_key": request.object_key,
        "preview_object_key": request.preview_object_key,
        "ocr_text": request.ocr_text,
        "content": request.content,
        "status": request.status.value,
    }


def _first_row(payload: object, error_message: str) -> dict[str, object]:
    if not isinstance(payload, list) or not payload or not isinstance(payload[0], dict):
        raise RuntimeError(error_message)
    return payload[0]


def _datetime_from_row(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _optional_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    return _datetime_from_row(value)


def _required_int(value: object) -> int:
    if isinstance(value, int):
        return value
    return int(str(value))


def _ensure_create_object_key_owned_by_user(*, object_key: str, user_id: str) -> None:
    expected = f"note/{user_id}/"
    if not object_key.startswith(expected):
        raise NoteObjectKeyOwnershipError("object_key is not owned by user")
