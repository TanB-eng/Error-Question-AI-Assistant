from __future__ import annotations

from uuid import UUID

from fastapi.testclient import TestClient

from app.api.notes import get_note_create_service
from app.deps import CurrentUser, current_user
from app.main import app
from app.schemas.mistakes import ItemStatus
from app.schemas.notes import NoteCreateRequest, NoteDetail
from app.services.notes import (
    NoteCreateConflictError,
    NoteObjectKeyOwnershipError,
)

USER_ID = "00000000-0000-4000-8000-000000000001"


class FakeNoteCreateService:
    def __init__(self) -> None:
        self.user_ids: list[str] = []
        self.requests: list[NoteCreateRequest] = []

    def create_note(self, *, user_id: str, request: NoteCreateRequest) -> NoteDetail:
        self.user_ids.append(user_id)
        self.requests.append(request)
        return NoteDetail(
            id=UUID("00000000-0000-4000-8000-000000000002"),
            subject_id=request.subject_id,
            content_excerpt=request.content,
            status=request.status,
            tags=[],
            created_at="2026-05-04T00:00:00Z",
            object_key=request.object_key,
            ocr_text=request.ocr_text,
            content=request.content,
        )


class ConflictNoteCreateService:
    def create_note(self, *, user_id: str, request: NoteCreateRequest) -> NoteDetail:
        raise NoteCreateConflictError("already used")


class ForbiddenNoteCreateService:
    def create_note(self, *, user_id: str, request: NoteCreateRequest) -> NoteDetail:
        raise NoteObjectKeyOwnershipError("forbidden")


def _override_user() -> None:
    app.dependency_overrides[current_user] = lambda: CurrentUser(
        id=USER_ID,
        access_token="jwt",
    )


def test_create_note_upserts_knowledge_tags() -> None:
    service = FakeNoteCreateService()
    _override_user()
    app.dependency_overrides[get_note_create_service] = lambda: service
    client = TestClient(app)

    try:
        response = client.post(
            "/notes",
            json={
                "subject_id": 2,
                "source_type": "photo",
                "object_key": f"note/{USER_ID}/file.png",
                "content": "reviewed note",
                "tags": [{"kind": "knowledge_point", "name": "vertex form"}],
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["content"] == "reviewed note"
    assert response.json()["status"] == ItemStatus.ACTIVE
    assert service.user_ids == [USER_ID]
    assert service.requests[0].tags[0].name == "vertex form"


def test_create_note_used_ingest_session_returns_409() -> None:
    _override_user()
    app.dependency_overrides[get_note_create_service] = lambda: ConflictNoteCreateService()
    client = TestClient(app)

    try:
        response = client.post(
            "/notes",
            json={
                "ingest_session_id": "00000000-0000-4000-8000-000000000010",
                "subject_id": 1,
                "source_type": "photo",
                "object_key": f"note/{USER_ID}/file.png",
                "content": "question",
                "tags": [],
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"


def test_create_note_cross_user_object_key_returns_403() -> None:
    _override_user()
    app.dependency_overrides[get_note_create_service] = lambda: ForbiddenNoteCreateService()
    client = TestClient(app)

    try:
        response = client.post(
            "/notes",
            json={
                "subject_id": 1,
                "source_type": "photo",
                "object_key": "note/00000000-0000-4000-8000-000000000002/file.png",
                "content": "question",
                "tags": [],
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
