from __future__ import annotations

from typing import Annotated, Protocol

from fastapi import APIRouter, Depends, Response

from app.core.ocr_client import get_ocr_provider
from app.core.settings import Settings, get_settings
from app.core.supabase import create_user_client
from app.deps import CurrentUser, current_user
from app.errors import ErrorCode, api_error
from app.schemas.notes import (
    NoteCreateRequest,
    NoteDetail,
    NoteIngestRequest,
    NoteIngestResponse,
    NoteListResponse,
    NoteUpdateRequest,
)
from app.services.ingestion import (
    ObjectKeyOwnershipError,
    ObjectNotFoundError,
    SupabaseIngestSessionRepository,
    SupabaseStorageFileStore,
)
from app.services.llm.deepseek import DeepSeekClient, SupabaseLLMAuditSink
from app.services.notes import (
    NoteClassifierService,
    NoteCreateConflictError,
    NoteCreateService,
    NoteCrudService,
    NoteIngestionService,
    NoteNotFoundError,
    NoteObjectKeyOwnershipError,
    SupabaseNoteRepository,
)
from app.services.ocr import OCRService
from app.services.tag_normalizer import SupabaseTagRepository, TagNormalizerService

router = APIRouter(prefix="/notes", tags=["Notes"])


class NoteIngestionServiceProtocol(Protocol):
    def ingest_note(self, *, user_id: str, request: NoteIngestRequest) -> NoteIngestResponse: ...


class NoteCreateServiceProtocol(Protocol):
    def create_note(self, *, user_id: str, request: NoteCreateRequest) -> NoteDetail: ...


class NoteCrudServiceProtocol(Protocol):
    def list_notes(
        self,
        *,
        user_id: str,
        subject_id: int | None = None,
        tag_id: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> NoteListResponse: ...

    def get_note(self, *, user_id: str, note_id: str) -> NoteDetail: ...

    def update_note(
        self,
        *,
        user_id: str,
        note_id: str,
        request: NoteUpdateRequest,
    ) -> NoteDetail: ...

    def delete_note(self, *, user_id: str, note_id: str) -> None: ...


def get_note_ingestion_service(
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[CurrentUser, Depends(current_user)],
) -> NoteIngestionServiceProtocol:
    user_client = create_user_client(settings, access_token=user.access_token)
    deepseek = DeepSeekClient(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        model=settings.deepseek_model,
        audit_sink=SupabaseLLMAuditSink(client=user_client),
    )
    return NoteIngestionService(
        file_store=SupabaseStorageFileStore(settings),
        session_repository=SupabaseIngestSessionRepository(client=user_client),
        ocr_service=OCRService(provider=get_ocr_provider(settings)),
        classifier=NoteClassifierService(deepseek_client=deepseek),
    )


def get_note_create_service(
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[CurrentUser, Depends(current_user)],
) -> NoteCreateServiceProtocol:
    user_client = create_user_client(settings, access_token=user.access_token)
    return NoteCreateService(
        note_repository=SupabaseNoteRepository(client=user_client),
        tag_normalizer=TagNormalizerService(repository=SupabaseTagRepository(client=user_client)),
    )


def get_note_crud_service(
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[CurrentUser, Depends(current_user)],
) -> NoteCrudServiceProtocol:
    user_client = create_user_client(settings, access_token=user.access_token)
    return NoteCrudService(
        note_repository=SupabaseNoteRepository(client=user_client),
        tag_normalizer=TagNormalizerService(repository=SupabaseTagRepository(client=user_client)),
    )


@router.post("/ingest", response_model=NoteIngestResponse)
def ingest_note(
    request: NoteIngestRequest,
    user: Annotated[CurrentUser, Depends(current_user)],
    note_ingestion_service: Annotated[
        NoteIngestionServiceProtocol, Depends(get_note_ingestion_service)
    ],
) -> NoteIngestResponse:
    try:
        return note_ingestion_service.ingest_note(user_id=user.id, request=request)
    except ObjectKeyOwnershipError as exc:
        raise api_error(403, ErrorCode.FORBIDDEN, "object key is not owned by user") from exc
    except ObjectNotFoundError as exc:
        raise api_error(404, ErrorCode.OBJECT_NOT_FOUND, "object not found") from exc


@router.post("", response_model=NoteDetail)
def create_note(
    request: NoteCreateRequest,
    user: Annotated[CurrentUser, Depends(current_user)],
    note_create_service: Annotated[NoteCreateServiceProtocol, Depends(get_note_create_service)],
) -> NoteDetail:
    try:
        return note_create_service.create_note(user_id=user.id, request=request)
    except NoteObjectKeyOwnershipError as exc:
        raise api_error(403, ErrorCode.FORBIDDEN, "object key is not owned by user") from exc
    except NoteCreateConflictError as exc:
        raise api_error(409, ErrorCode.CONFLICT, "ingest session already saved") from exc


@router.get("", response_model=NoteListResponse)
def list_notes(
    user: Annotated[CurrentUser, Depends(current_user)],
    note_crud_service: Annotated[NoteCrudServiceProtocol, Depends(get_note_crud_service)],
    subject_id: int | None = None,
    tag_id: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> NoteListResponse:
    return note_crud_service.list_notes(
        user_id=user.id,
        subject_id=subject_id,
        tag_id=tag_id,
        page=page,
        page_size=page_size,
    )


@router.get("/{note_id}", response_model=NoteDetail)
def get_note(
    note_id: str,
    user: Annotated[CurrentUser, Depends(current_user)],
    note_crud_service: Annotated[NoteCrudServiceProtocol, Depends(get_note_crud_service)],
) -> NoteDetail:
    try:
        return note_crud_service.get_note(user_id=user.id, note_id=note_id)
    except NoteNotFoundError as exc:
        raise api_error(404, ErrorCode.OBJECT_NOT_FOUND, "note not found") from exc


@router.patch("/{note_id}", response_model=NoteDetail)
def update_note(
    note_id: str,
    request: NoteUpdateRequest,
    user: Annotated[CurrentUser, Depends(current_user)],
    note_crud_service: Annotated[NoteCrudServiceProtocol, Depends(get_note_crud_service)],
) -> NoteDetail:
    try:
        return note_crud_service.update_note(user_id=user.id, note_id=note_id, request=request)
    except NoteObjectKeyOwnershipError as exc:
        raise api_error(403, ErrorCode.FORBIDDEN, "object key is not owned by user") from exc
    except NoteNotFoundError as exc:
        raise api_error(404, ErrorCode.OBJECT_NOT_FOUND, "note not found") from exc


@router.delete("/{note_id}", status_code=204)
def delete_note(
    note_id: str,
    user: Annotated[CurrentUser, Depends(current_user)],
    note_crud_service: Annotated[NoteCrudServiceProtocol, Depends(get_note_crud_service)],
) -> Response:
    try:
        note_crud_service.delete_note(user_id=user.id, note_id=note_id)
    except NoteNotFoundError as exc:
        raise api_error(404, ErrorCode.OBJECT_NOT_FOUND, "note not found") from exc
    return Response(status_code=204)
