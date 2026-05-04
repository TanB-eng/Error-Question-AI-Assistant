from __future__ import annotations

from uuid import UUID

from fastapi.testclient import TestClient

from app.api.notes import get_note_ingestion_service
from app.deps import CurrentUser, current_user
from app.main import app
from app.schemas.mistakes import IngestStatus
from app.schemas.notes import NoteIngestRequest, NoteIngestResponse
from app.services.ingestion import ObjectNotFoundError

USER_ID = "00000000-0000-4000-8000-000000000001"


class FakeNoteIngestionService:
    def __init__(self) -> None:
        self.user_ids: list[str] = []
        self.requests: list[NoteIngestRequest] = []

    def ingest_note(self, *, user_id: str, request: NoteIngestRequest) -> NoteIngestResponse:
        self.user_ids.append(user_id)
        self.requests.append(request)
        return NoteIngestResponse(
            session_id=UUID("00000000-0000-4000-8000-000000000001"),
            status=IngestStatus.READY,
            ocr_text="note OCR text",
            candidates=[],
        )


class MissingObjectNoteIngestionService:
    def ingest_note(self, *, user_id: str, request: NoteIngestRequest) -> NoteIngestResponse:
        raise ObjectNotFoundError("missing")


def test_note_ingest_requires_jwt() -> None:
    client = TestClient(app)

    response = client.post(
        "/notes/ingest",
        json={"object_key": f"note/{USER_ID}/file.png", "source_type": "photo", "subject_id": 1},
    )

    assert response.status_code == 401


def test_note_ingest_calls_service_with_current_user() -> None:
    service = FakeNoteIngestionService()
    app.dependency_overrides[current_user] = lambda: CurrentUser(id=USER_ID, access_token="jwt")
    app.dependency_overrides[get_note_ingestion_service] = lambda: service
    client = TestClient(app)

    try:
        response = client.post(
            "/notes/ingest",
            json={
                "object_key": f"note/{USER_ID}/file.png",
                "source_type": "photo",
                "subject_id": 1,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert service.user_ids == [USER_ID]
    assert service.requests[0].object_key == f"note/{USER_ID}/file.png"


def test_note_ingest_missing_object_returns_404() -> None:
    app.dependency_overrides[current_user] = lambda: CurrentUser(id=USER_ID, access_token="jwt")
    app.dependency_overrides[get_note_ingestion_service] = (
        lambda: MissingObjectNoteIngestionService()
    )
    client = TestClient(app)

    try:
        response = client.post(
            "/notes/ingest",
            json={
                "object_key": f"note/{USER_ID}/file.png",
                "source_type": "photo",
                "subject_id": 1,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "OBJECT_NOT_FOUND"
