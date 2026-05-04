from __future__ import annotations

from uuid import UUID

from app.schemas.mistakes import (
    AnswerStatus,
    ItemStatus,
    MistakeCreateRequest,
    MistakeDetail,
    SourceType,
    TagInput,
)


def test_mistake_create_schema_matches_openapi() -> None:
    request = MistakeCreateRequest.model_validate(
        {
            "ingest_session_id": "00000000-0000-4000-8000-000000000001",
            "subject_id": 2,
            "source_type": "photo",
            "object_key": "mistake/user/file.png",
            "ocr_text": "OCR text",
            "question": "user edited question",
            "my_answer": "",
            "correct_answer": "",
            "analysis": "",
            "question_type": "",
            "difficulty": None,
            "error_cause": "",
            "status": "pending",
            "answer_status": "unreviewed",
            "annotation": "note",
            "tags": [{"kind": "knowledge_point", "name": "顶点式"}],
        }
    )

    assert request.subject_id == 2
    assert request.source_type == SourceType.PHOTO
    assert request.tags == [TagInput(kind="knowledge_point", name="顶点式")]
    assert request.status == ItemStatus.PENDING
    assert request.answer_status == AnswerStatus.UNREVIEWED


def test_mistake_detail_schema_contains_created_item_fields() -> None:
    detail = MistakeDetail.model_validate(
        {
            "id": "00000000-0000-4000-8000-000000000002",
            "subject_id": 2,
            "question_excerpt": "user edited question",
            "answer_status": "unreviewed",
            "status": "pending",
            "tags": [
                {
                    "id": "00000000-0000-4000-8000-000000000003",
                    "kind": "knowledge_point",
                    "name": "顶点式",
                    "normalized_name": "顶点式",
                }
            ],
            "created_at": "2026-05-04T00:00:00Z",
            "deleted_at": None,
            "object_key": "mistake/user/file.png",
            "image_url": None,
            "ocr_text": "OCR text",
            "question": "user edited question",
            "my_answer": "",
            "correct_answer": "",
            "analysis": "",
            "question_type": "",
            "difficulty": None,
            "error_cause": "",
            "annotation": "note",
            "last_viewed_at": None,
        }
    )

    assert detail.id == UUID("00000000-0000-4000-8000-000000000002")
    assert detail.subject_id == 2
