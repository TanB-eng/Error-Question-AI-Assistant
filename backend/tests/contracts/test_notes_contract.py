from __future__ import annotations

from app.schemas.mistakes import IngestStatus, ItemStatus, SourceType
from app.schemas.notes import (
    NoteCandidate,
    NoteCreateRequest,
    NoteIngestRequest,
    NoteIngestResponse,
)


def test_note_schemas_match_openapi() -> None:
    ingest_request = NoteIngestRequest.model_validate(
        {
            "object_key": "note/00000000-0000-4000-8000-000000000001/file.png",
            "source_type": "photo",
            "subject_id": 1,
        }
    )
    ingest_response = NoteIngestResponse.model_validate(
        {
            "session_id": "00000000-0000-4000-8000-000000000001",
            "status": "ready",
            "ocr_text": "note OCR text",
            "candidates": [
                {
                    "subject_id": 1,
                    "status": "ready",
                    "content": "organized note",
                    "knowledge_points": ["vertex form"],
                }
            ],
            "error_code": None,
        }
    )
    create_request = NoteCreateRequest.model_validate(
        {
            "subject_id": 1,
            "source_type": "photo",
            "object_key": "note/00000000-0000-4000-8000-000000000001/file.png",
            "content": "user reviewed note",
            "tags": [{"kind": "knowledge_point", "name": "vertex form"}],
        }
    )

    assert ingest_request.source_type == SourceType.PHOTO
    assert ingest_response.status == IngestStatus.READY
    assert ingest_response.candidates[0].content == "organized note"
    assert create_request.status == ItemStatus.ACTIVE


def test_note_candidate_excludes_mistake_only_fields() -> None:
    field_names = set(NoteCandidate.model_fields)

    assert "difficulty" not in field_names
    assert "question_type" not in field_names
    assert "error_cause" not in field_names
