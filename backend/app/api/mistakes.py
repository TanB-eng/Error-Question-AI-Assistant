from __future__ import annotations

from typing import Annotated, Protocol

from fastapi import APIRouter, Depends

from app.core.ocr_client import get_ocr_provider
from app.core.settings import Settings, get_settings
from app.core.supabase import create_user_client
from app.deps import CurrentUser, current_user
from app.errors import ErrorCode, api_error
from app.schemas.mistakes import (
    MistakeCreateRequest,
    MistakeDetail,
    MistakeIngestRequest,
    MistakeIngestResponse,
)
from app.services.classifier import ClassifierService
from app.services.ingestion import (
    IngestionService,
    ObjectKeyOwnershipError,
    ObjectNotFoundError,
    SupabaseIngestSessionRepository,
    SupabaseStorageFileStore,
)
from app.services.llm.deepseek import DeepSeekClient, SupabaseLLMAuditSink
from app.services.mistakes import (
    MistakeCreateConflictError,
    MistakeCreateService,
    MistakeObjectKeyOwnershipError,
    SupabaseMistakeRepository,
)
from app.services.ocr import OCRService
from app.services.tag_normalizer import SupabaseTagRepository, TagNormalizerService

router = APIRouter(prefix="/mistakes", tags=["Mistakes"])


class IngestionServiceProtocol(Protocol):
    def ingest_mistake(
        self, *, user_id: str, request: MistakeIngestRequest
    ) -> MistakeIngestResponse: ...


class MistakeCreateServiceProtocol(Protocol):
    def create_mistake(self, *, user_id: str, request: MistakeCreateRequest) -> MistakeDetail: ...


def get_ingestion_service(
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[CurrentUser, Depends(current_user)],
) -> IngestionServiceProtocol:
    user_client = create_user_client(settings, access_token=user.access_token)
    deepseek = DeepSeekClient(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        model=settings.deepseek_model,
        audit_sink=SupabaseLLMAuditSink(client=user_client),
    )
    return IngestionService(
        file_store=SupabaseStorageFileStore(settings),
        session_repository=SupabaseIngestSessionRepository(client=user_client),
        ocr_service=OCRService(provider=get_ocr_provider(settings)),
        classifier=ClassifierService(deepseek_client=deepseek),
    )


def get_mistake_create_service(
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[CurrentUser, Depends(current_user)],
) -> MistakeCreateServiceProtocol:
    user_client = create_user_client(settings, access_token=user.access_token)
    return MistakeCreateService(
        mistake_repository=SupabaseMistakeRepository(client=user_client),
        tag_normalizer=TagNormalizerService(
            repository=SupabaseTagRepository(client=user_client),
        ),
    )


@router.post("/ingest", response_model=MistakeIngestResponse)
def ingest_mistake(
    request: MistakeIngestRequest,
    user: Annotated[CurrentUser, Depends(current_user)],
    ingestion_service: Annotated[IngestionServiceProtocol, Depends(get_ingestion_service)],
) -> MistakeIngestResponse:
    try:
        return ingestion_service.ingest_mistake(user_id=user.id, request=request)
    except ObjectKeyOwnershipError as exc:
        raise api_error(403, ErrorCode.FORBIDDEN, "无权访问该文件") from exc
    except ObjectNotFoundError as exc:
        raise api_error(404, ErrorCode.OBJECT_NOT_FOUND, "文件不存在或已被删除") from exc


@router.post("", response_model=MistakeDetail)
def create_mistake(
    request: MistakeCreateRequest,
    user: Annotated[CurrentUser, Depends(current_user)],
    mistake_create_service: Annotated[
        MistakeCreateServiceProtocol, Depends(get_mistake_create_service)
    ],
) -> MistakeDetail:
    try:
        return mistake_create_service.create_mistake(user_id=user.id, request=request)
    except MistakeObjectKeyOwnershipError as exc:
        raise api_error(403, ErrorCode.FORBIDDEN, "object key is not owned by user") from exc
    except MistakeCreateConflictError as exc:
        raise api_error(409, ErrorCode.CONFLICT, "录入会话已保存") from exc
