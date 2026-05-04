from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID, uuid4

import httpx

from app.core.settings import Settings
from app.core.supabase import SupabaseRestClient
from app.errors import ErrorCode
from app.schemas.mistakes import (
    IngestStatus,
    MistakeCandidate,
    MistakeIngestRequest,
    MistakeIngestResponse,
)
from app.schemas.uploads import (
    IMAGE_MAX_SIZE_BYTES,
    PDF_MAX_SIZE_BYTES,
    SUPPORTED_UPLOAD_MIME_TYPES,
)
from app.services.classifier import ClassificationOutcome
from app.services.ocr import OCRInput, OCRService
from app.services.pdf import PDFProcessingError, PDFQuestionSplitter

BUCKET_BY_SCENE = {"mistake": "mistakes", "note": "notes"}


@dataclass(frozen=True)
class StoredObject:
    content: bytes
    mime_type: str


class FileStore(Protocol):
    def get_object(self, object_key: str) -> StoredObject: ...


class ObjectKeyOwnershipError(RuntimeError):
    """Raised when an object key does not belong to the current user."""


class ObjectNotFoundError(RuntimeError):
    """Raised when a user-owned object key no longer exists in storage."""


class IngestSessionRepository(Protocol):
    def create_session(
        self,
        *,
        user_id: str,
        scene: str,
        source_type: str,
        subject_id: int,
        object_key: str,
        mime_type: str,
    ) -> str: ...

    def update_session(
        self,
        *,
        session_id: str,
        status: str,
        ocr_text: str,
        candidate_payload: dict[str, object],
        error_code: ErrorCode | None,
    ) -> None: ...


class MistakeClassifier(Protocol):
    def classify(
        self,
        *,
        user_id: str,
        ingest_session_id: str | None,
        ocr_text: str,
    ) -> ClassificationOutcome: ...


class InMemoryIngestSessionRepository:
    def __init__(self) -> None:
        self.sessions: dict[str, dict[str, object]] = {}

    def create_session(
        self,
        *,
        user_id: str,
        scene: str,
        source_type: str,
        subject_id: int,
        object_key: str,
        mime_type: str,
    ) -> str:
        session_id = str(uuid4())
        self.sessions[session_id] = {
            "user_id": user_id,
            "scene": scene,
            "source_type": source_type,
            "subject_id": subject_id,
            "object_key": object_key,
            "mime_type": mime_type,
            "status": "uploaded",
            "ocr_text": "",
            "candidate_payload": {},
            "error_code": None,
        }
        return session_id

    def update_session(
        self,
        *,
        session_id: str,
        status: str,
        ocr_text: str,
        candidate_payload: dict[str, object],
        error_code: ErrorCode | None,
    ) -> None:
        self.sessions[session_id].update(
            {
                "status": status,
                "ocr_text": ocr_text,
                "candidate_payload": candidate_payload,
                "error_code": error_code.value if error_code is not None else None,
            }
        )


class SupabaseIngestSessionRepository:
    def __init__(self, *, client: SupabaseRestClient) -> None:
        self._client = client

    def create_session(
        self,
        *,
        user_id: str,
        scene: str,
        source_type: str,
        subject_id: int,
        object_key: str,
        mime_type: str,
    ) -> str:
        response = self._client.request(
            "POST",
            "/ingest_sessions",
            headers={"Prefer": "return=representation"},
            json={
                "user_id": user_id,
                "scene": scene,
                "source_type": source_type,
                "subject_id": subject_id,
                "object_key": object_key,
                "mime_type": mime_type,
                "status": "uploaded",
            },
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list) or not payload or not isinstance(payload[0], dict):
            raise RuntimeError("Invalid ingest session response")
        session_id = payload[0].get("id")
        if not isinstance(session_id, str):
            raise RuntimeError("Invalid ingest session id")
        return session_id

    def update_session(
        self,
        *,
        session_id: str,
        status: str,
        ocr_text: str,
        candidate_payload: dict[str, object],
        error_code: ErrorCode | None,
    ) -> None:
        response = self._client.request(
            "PATCH",
            "/ingest_sessions",
            params={"id": f"eq.{session_id}"},
            headers={"Prefer": "return=minimal"},
            json={
                "status": status,
                "ocr_text": ocr_text,
                "candidate_payload": candidate_payload,
                "error_code": error_code.value if error_code is not None else None,
            },
        )
        response.raise_for_status()


class SupabaseStorageFileStore:
    def __init__(
        self,
        settings: Settings,
        *,
        client: httpx.Client | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._settings = settings
        self._client = client if client is not None else httpx.Client()
        self._timeout_seconds = timeout_seconds

    def get_object(self, object_key: str) -> StoredObject:
        bucket = _bucket_for_object_key(object_key)
        try:
            response = self._client.get(
                f"{self._settings.supabase_url.rstrip('/')}/storage/v1/object/{bucket}/{object_key}",
                headers={
                    "apikey": self._settings.supabase_service_role_key,
                    "Authorization": f"Bearer {self._settings.supabase_service_role_key}",
                },
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise ObjectNotFoundError("storage object not found") from exc
            raise
        mime_type = response.headers.get("content-type", "application/octet-stream").split(";")[0]
        return StoredObject(
            content=response.content,
            mime_type=mime_type,
        )


class IngestionService:
    def __init__(
        self,
        *,
        file_store: FileStore,
        session_repository: IngestSessionRepository,
        ocr_service: OCRService,
        classifier: MistakeClassifier,
        pdf_splitter: PDFQuestionSplitter | None = None,
    ) -> None:
        self._file_store = file_store
        self._session_repository = session_repository
        self._ocr_service = ocr_service
        self._classifier = classifier
        self._pdf_splitter = pdf_splitter if pdf_splitter is not None else PDFQuestionSplitter()

    def ingest_mistake(
        self, *, user_id: str, request: MistakeIngestRequest
    ) -> MistakeIngestResponse:
        _ensure_object_key_owned_by_user(
            object_key=request.object_key,
            scene="mistake",
            user_id=user_id,
        )
        stored_object = self._file_store.get_object(request.object_key)
        if stored_object.mime_type not in SUPPORTED_UPLOAD_MIME_TYPES:
            session_id = self._session_repository.create_session(
                user_id=user_id,
                scene="mistake",
                source_type=request.source_type.value,
                subject_id=request.subject_id,
                object_key=request.object_key,
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

        session_id = self._session_repository.create_session(
            user_id=user_id,
            scene="mistake",
            source_type=request.source_type.value,
            subject_id=request.subject_id,
            object_key=request.object_key,
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

        if request.source_type.value == "pdf":
            return self._ingest_pdf(
                user_id=user_id,
                request=request,
                session_id=session_id,
                stored_object=stored_object,
            )

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

        classification = self._classifier.classify(
            user_id=user_id,
            ingest_session_id=session_id,
            ocr_text=ocr_result.text,
        )
        if classification.status == "pending_classification" or classification.result is None:
            candidate = _manual_candidate(
                subject_id=request.subject_id,
                question=ocr_result.text,
                status=IngestStatus.PENDING_CLASSIFICATION,
                error_code=classification.error_code,
            )
            return self._finish(
                session_id=session_id,
                status=IngestStatus.PENDING_CLASSIFICATION,
                ocr_text=ocr_result.text,
                candidates=[candidate],
                error_code=classification.error_code,
                session_status="pending",
            )

        candidate = MistakeCandidate(
            subject_id=request.subject_id,
            question=classification.result.question,
            my_answer=classification.result.my_answer,
            correct_answer=classification.result.correct_answer,
            knowledge_points=classification.result.knowledge_points,
            question_type=classification.result.question_type,
            difficulty=classification.result.difficulty,
            error_cause=classification.result.error_cause,
            analysis=classification.result.analysis,
        )
        return self._finish(
            session_id=session_id,
            status=IngestStatus.READY,
            ocr_text=ocr_result.text,
            candidates=[candidate],
            error_code=None,
            session_status="classified",
        )

    def _ingest_pdf(
        self,
        *,
        user_id: str,
        request: MistakeIngestRequest,
        session_id: str,
        stored_object: StoredObject,
    ) -> MistakeIngestResponse:
        try:
            pdf_result = self._pdf_splitter.extract_questions(stored_object.content)
        except PDFProcessingError as exc:
            return self._finish(
                session_id=session_id,
                status=IngestStatus.OCR_FAILED,
                ocr_text="",
                candidates=[],
                error_code=exc.error_code,
                session_status="failed",
            )

        candidates: list[MistakeCandidate] = []
        has_pending = False
        for question_candidate in pdf_result.candidates:
            classification = self._classifier.classify(
                user_id=user_id,
                ingest_session_id=session_id,
                ocr_text=question_candidate.question_text,
            )
            if classification.status == "pending_classification" or classification.result is None:
                has_pending = True
                candidates.append(
                    _manual_candidate(
                        subject_id=request.subject_id,
                        question=question_candidate.question_text,
                        page_number=question_candidate.page_number,
                        status=IngestStatus.PENDING_CLASSIFICATION,
                        error_code=classification.error_code,
                    )
                )
                continue

            result = classification.result
            candidates.append(
                MistakeCandidate(
                    subject_id=request.subject_id,
                    status=IngestStatus.READY,
                    question=result.question,
                    my_answer=result.my_answer,
                    correct_answer=result.correct_answer,
                    knowledge_points=result.knowledge_points,
                    question_type=result.question_type,
                    difficulty=result.difficulty,
                    error_cause=result.error_cause,
                    analysis=result.analysis,
                    page_number=question_candidate.page_number,
                    error_code=None,
                )
            )

        response_status = (
            IngestStatus.PENDING_CLASSIFICATION if has_pending else IngestStatus.READY
        )
        return self._finish(
            session_id=session_id,
            status=response_status,
            ocr_text=pdf_result.text,
            candidates=candidates,
            error_code=ErrorCode.LLM_SCHEMA_INVALID if has_pending else None,
            session_status="pending" if has_pending else "classified",
        )

    def _finish(
        self,
        *,
        session_id: str,
        status: IngestStatus,
        ocr_text: str,
        candidates: list[MistakeCandidate],
        error_code: ErrorCode | None,
        session_status: str,
    ) -> MistakeIngestResponse:
        candidate_payload: dict[str, object] = {
            "status": status.value,
            "candidates": [candidate.model_dump(mode="json") for candidate in candidates],
        }
        self._session_repository.update_session(
            session_id=session_id,
            status=session_status,
            ocr_text=ocr_text,
            candidate_payload=candidate_payload,
            error_code=error_code,
        )
        return MistakeIngestResponse(
            session_id=UUID(session_id),
            status=status,
            ocr_text=ocr_text,
            candidates=candidates,
            error_code=error_code,
        )


def _manual_candidate(
    *,
    subject_id: int,
    question: str,
    page_number: int | None = None,
    status: IngestStatus = IngestStatus.READY,
    error_code: ErrorCode | None = None,
) -> MistakeCandidate:
    return MistakeCandidate(
        subject_id=subject_id,
        status=status,
        question=question,
        my_answer="",
        correct_answer="",
        knowledge_points=[],
        question_type="",
        difficulty=None,
        error_cause="",
        analysis="",
        page_number=page_number,
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


def _ensure_object_key_owned_by_user(*, object_key: str, scene: str, user_id: str) -> None:
    expected = f"{scene}/{user_id}/"
    if not object_key.startswith(expected):
        raise ObjectKeyOwnershipError("object key is not owned by current user")


def _bucket_for_object_key(object_key: str) -> str:
    scene = object_key.split("/", 1)[0]
    return BUCKET_BY_SCENE[scene]
