from __future__ import annotations

from uuid import UUID

from fastapi.testclient import TestClient

from app.api.mistakes import get_ingestion_service
from app.deps import CurrentUser, current_user
from app.main import app
from app.schemas.mistakes import IngestStatus, MistakeIngestRequest, MistakeIngestResponse
from app.services.ingestion import ObjectNotFoundError


class FakeIngestionService:
    def __init__(self) -> None:
        self.user_ids: list[str] = []
        self.requests: list[MistakeIngestRequest] = []

    def ingest_mistake(
        self, *, user_id: str, request: MistakeIngestRequest
    ) -> MistakeIngestResponse:
        self.user_ids.append(user_id)
        self.requests.append(request)
        return MistakeIngestResponse(
            session_id=UUID("00000000-0000-4000-8000-000000000001"),
            status=IngestStatus.READY,
            ocr_text="OCR 文本",
            candidates=[],
        )


class MissingObjectIngestionService:
    def ingest_mistake(
        self, *, user_id: str, request: MistakeIngestRequest
    ) -> MistakeIngestResponse:
        raise ObjectNotFoundError("missing")


def test_mistake_ingest_requires_jwt() -> None:
    client = TestClient(app)

    response = client.post(
        "/mistakes/ingest",
        json={"object_key": "mistake/user/file.png", "source_type": "photo", "subject_id": 1},
    )

    assert response.status_code == 401


def test_mistake_ingest_calls_service_with_current_user() -> None:
    service = FakeIngestionService()
    app.dependency_overrides[current_user] = lambda: CurrentUser(
        id="00000000-0000-4000-8000-000000000001",
        access_token="jwt",
    )
    app.dependency_overrides[get_ingestion_service] = lambda: service
    client = TestClient(app)

    response = client.post(
        "/mistakes/ingest",
        json={"object_key": "mistake/user/file.png", "source_type": "photo", "subject_id": 1},
    )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert service.user_ids == ["00000000-0000-4000-8000-000000000001"]
    assert service.requests[0].object_key == "mistake/user/file.png"


def test_mistake_ingest_missing_object_returns_404() -> None:
    app.dependency_overrides[current_user] = lambda: CurrentUser(
        id="00000000-0000-4000-8000-000000000001",
        access_token="jwt",
    )
    app.dependency_overrides[get_ingestion_service] = lambda: MissingObjectIngestionService()
    client = TestClient(app)

    response = client.post(
        "/mistakes/ingest",
        json={"object_key": "mistake/user/file.png", "source_type": "photo", "subject_id": 1},
    )

    app.dependency_overrides.clear()
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "OBJECT_NOT_FOUND"
