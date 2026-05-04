from __future__ import annotations

from uuid import UUID

import pytest

from app.schemas.mistakes import MistakeCreateRequest
from app.services.mistakes import (
    InMemoryMistakeRepository,
    MistakeCreateConflictError,
    MistakeCreateService,
)
from app.services.tag_normalizer import InMemoryTagRepository, TagNormalizerService

USER_ID = "00000000-0000-4000-8000-000000000001"


def test_create_mistake_upserts_normalized_tags() -> None:
    mistake_repository = InMemoryMistakeRepository()
    tag_repository = InMemoryTagRepository()
    service = MistakeCreateService(
        mistake_repository=mistake_repository,
        tag_normalizer=TagNormalizerService(repository=tag_repository),
    )

    detail = service.create_mistake(
        user_id=USER_ID,
        request=MistakeCreateRequest(
            ingest_session_id=UUID("00000000-0000-4000-8000-000000000010"),
            subject_id=2,
            source_type="photo",
            object_key=f"mistake/{USER_ID}/file.png",
            ocr_text="OCR text",
            question="user edited question",
            status="pending",
            tags=[
                {"kind": "knowledge_point", "name": "二次函数顶点式"},
                {"kind": "knowledge_point", "name": "顶点式"},
            ],
        ),
    )

    assert detail.subject_id == 2
    assert detail.status == "pending"
    assert detail.question == "user edited question"
    assert len(detail.tags) == 1
    assert detail.tags[0].normalized_name == "顶点式"
    assert mistake_repository.mistakes[0]["subject_id"] == 2
    assert len(mistake_repository.mistake_tags) == 1


def test_create_mistake_rejects_used_ingest_session() -> None:
    service = MistakeCreateService(
        mistake_repository=InMemoryMistakeRepository(),
        tag_normalizer=TagNormalizerService(repository=InMemoryTagRepository()),
    )
    request = MistakeCreateRequest(
        ingest_session_id=UUID("00000000-0000-4000-8000-000000000010"),
        subject_id=1,
        source_type="photo",
        object_key=f"mistake/{USER_ID}/file.png",
        question="question",
        tags=[],
    )

    service.create_mistake(user_id=USER_ID, request=request)

    with pytest.raises(MistakeCreateConflictError):
        service.create_mistake(
            user_id=USER_ID,
            request=request,
        )
