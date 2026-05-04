from __future__ import annotations

from uuid import UUID

from fastapi.testclient import TestClient

from app.api.mistakes import get_mistake_create_service
from app.deps import CurrentUser, current_user
from app.main import app
from app.schemas.mistakes import MistakeCreateRequest, MistakeDetail
from app.services.mistakes import MistakeCreateConflictError

USER_ID = "00000000-0000-4000-8000-000000000001"


class FakeMistakeCreateService:
    def __init__(self) -> None:
        self.user_ids: list[str] = []
        self.requests: list[MistakeCreateRequest] = []

    def create_mistake(self, *, user_id: str, request: MistakeCreateRequest) -> MistakeDetail:
        self.user_ids.append(user_id)
        self.requests.append(request)
        return MistakeDetail(
            id=UUID("00000000-0000-4000-8000-000000000002"),
            subject_id=request.subject_id,
            question_excerpt=request.question,
            answer_status=request.answer_status,
            status=request.status,
            tags=[],
            created_at="2026-05-04T00:00:00Z",
            object_key=request.object_key,
            ocr_text=request.ocr_text,
            question=request.question,
            my_answer=request.my_answer,
            correct_answer=request.correct_answer,
            analysis=request.analysis,
            question_type=request.question_type,
            difficulty=request.difficulty,
            error_cause=request.error_cause,
            annotation=request.annotation,
        )


class ConflictMistakeCreateService:
    def create_mistake(self, *, user_id: str, request: MistakeCreateRequest) -> MistakeDetail:
        raise MistakeCreateConflictError("already used")


def _override_user() -> None:
    app.dependency_overrides[current_user] = lambda: CurrentUser(
        id=USER_ID,
        access_token="jwt",
    )


def test_create_mistake_returns_detail() -> None:
    service = FakeMistakeCreateService()
    _override_user()
    app.dependency_overrides[get_mistake_create_service] = lambda: service
    client = TestClient(app)

    response = client.post(
        "/mistakes",
        json={
            "subject_id": 2,
            "source_type": "photo",
            "object_key": f"mistake/{USER_ID}/file.png",
            "question": "user edited question",
            "tags": [{"kind": "knowledge_point", "name": "顶点式"}],
        },
    )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["subject_id"] == 2
    assert response.json()["question"] == "user edited question"
    assert service.user_ids == [USER_ID]
    assert service.requests[0].subject_id == 2


def test_create_mistake_used_ingest_session_returns_409() -> None:
    _override_user()
    app.dependency_overrides[get_mistake_create_service] = lambda: ConflictMistakeCreateService()
    client = TestClient(app)

    response = client.post(
        "/mistakes",
        json={
            "ingest_session_id": "00000000-0000-4000-8000-000000000010",
            "subject_id": 1,
            "source_type": "photo",
            "object_key": f"mistake/{USER_ID}/file.png",
            "question": "question",
            "tags": [],
        },
    )

    app.dependency_overrides.clear()
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"
