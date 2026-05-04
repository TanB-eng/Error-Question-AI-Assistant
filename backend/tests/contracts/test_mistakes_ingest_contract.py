from __future__ import annotations

from app.errors import ErrorCode
from app.schemas.mistakes import (
    IngestStatus,
    MistakeCandidate,
    MistakeIngestRequest,
    MistakeIngestResponse,
    SourceType,
)


def test_mistake_ingest_schema_matches_openapi() -> None:
    request = MistakeIngestRequest.model_validate(
        {
            "object_key": "mistake/user/file.png",
            "source_type": "photo",
            "subject_id": 1,
        }
    )
    response = MistakeIngestResponse.model_validate(
        {
            "session_id": "00000000-0000-4000-8000-000000000001",
            "status": "ocr_failed",
            "ocr_text": "",
            "candidates": [],
            "error_code": "OCR_FAILED",
        }
    )

    assert request.source_type == SourceType.PHOTO
    assert response.status == IngestStatus.OCR_FAILED
    assert response.error_code == ErrorCode.OCR_FAILED


def test_mistake_candidate_contains_review_fields() -> None:
    candidate = MistakeCandidate.model_validate(
        {
            "subject_id": 1,
            "question": "题干",
            "my_answer": "",
            "correct_answer": "",
            "knowledge_points": ["顶点式"],
            "question_type": "",
            "difficulty": None,
            "error_cause": "",
            "analysis": "",
        }
    )

    assert candidate.question == "题干"
    assert candidate.difficulty is None
