from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.mistakes import get_ingestion_service, get_mistake_create_service
from app.deps import CurrentUser, current_user
from app.main import app
from app.services.classifier import ClassificationOutcome
from app.services.ingestion import (
    IngestionService,
    InMemoryIngestSessionRepository,
    StoredObject,
)
from app.services.mistakes import InMemoryMistakeRepository, MistakeCreateService
from app.services.ocr import OCRInput, OCRProvider, OCRService
from app.services.tag_normalizer import InMemoryTagRepository, TagNormalizerService

USER_A = "00000000-0000-4000-8000-000000000001"
USER_B = "00000000-0000-4000-8000-000000000002"


class FakeFileStore:
    def get_object(self, object_key: str) -> StoredObject:
        return StoredObject(content=b"image-bytes", mime_type="image/png")


class BrokenOCRProvider(OCRProvider):
    def extract_text(self, ocr_input: OCRInput) -> str:
        raise RuntimeError("ocr failed")


class TripWireClassifier:
    def classify(
        self,
        *,
        user_id: str,
        ingest_session_id: str | None,
        ocr_text: str,
    ) -> ClassificationOutcome:
        raise AssertionError("classifier must not run when OCR fails")


def _override_user(user_id: str = USER_A) -> None:
    app.dependency_overrides[current_user] = lambda: CurrentUser(
        id=user_id,
        access_token="jwt",
    )


def test_ocr_failure_manual_save_and_tag_merge() -> None:
    session_repository = InMemoryIngestSessionRepository()
    mistake_repository = InMemoryMistakeRepository()
    tag_repository = InMemoryTagRepository()
    _override_user()
    app.dependency_overrides[get_ingestion_service] = lambda: IngestionService(
        file_store=FakeFileStore(),
        session_repository=session_repository,
        ocr_service=OCRService(provider=BrokenOCRProvider()),
        classifier=TripWireClassifier(),
    )
    app.dependency_overrides[get_mistake_create_service] = lambda: MistakeCreateService(
        mistake_repository=mistake_repository,
        tag_normalizer=TagNormalizerService(repository=tag_repository),
    )
    client = TestClient(app)
    object_key = f"mistake/{USER_A}/manual-after-ocr-failed.png"

    try:
        ingest_response = client.post(
            "/mistakes/ingest",
            json={
                "object_key": object_key,
                "source_type": "photo",
                "subject_id": 1,
            },
        )
        ingest_body = ingest_response.json()

        create_response = client.post(
            "/mistakes",
            json={
                "ingest_session_id": ingest_body["session_id"],
                "subject_id": 2,
                "source_type": "photo",
                "object_key": object_key,
                "ocr_text": "",
                "question": "manual question after OCR failure",
                "status": "pending",
                "tags": [
                    {"kind": "knowledge_point", "name": "vertex form"},
                    {"kind": "knowledge_point", "name": "vertexform"},
                    {"kind": "knowledge_point", "name": " vertex  form "},
                    {"kind": "knowledge_point", "name": "vertex form."},
                    {"kind": "knowledge_point", "name": "vertex\tform,"},
                ],
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert ingest_response.status_code == 200
    assert ingest_body["status"] == "ocr_failed"
    assert ingest_body["error_code"] == "OCR_FAILED"
    assert session_repository.sessions[ingest_body["session_id"]]["status"] == "failed"

    assert create_response.status_code == 200
    create_body = create_response.json()
    assert create_body["subject_id"] == 2
    assert create_body["question"] == "manual question after OCR failure"
    assert create_body["status"] == "pending"
    assert len(create_body["tags"]) == 1
    assert create_body["tags"][0]["normalized_name"] == "vertexform"
    assert len(mistake_repository.mistakes) == 1
    assert len(mistake_repository.mistake_tags) == 1
    assert ingest_body["session_id"] in mistake_repository.used_sessions


def test_create_rejects_cross_user_object_key_before_save() -> None:
    mistake_repository = InMemoryMistakeRepository()
    tag_repository = InMemoryTagRepository()
    _override_user()
    app.dependency_overrides[get_mistake_create_service] = lambda: MistakeCreateService(
        mistake_repository=mistake_repository,
        tag_normalizer=TagNormalizerService(repository=tag_repository),
    )
    client = TestClient(app)

    try:
        response = client.post(
            "/mistakes",
            json={
                "subject_id": 1,
                "source_type": "photo",
                "object_key": f"mistake/{USER_B}/other-user-file.png",
                "question": "must not save",
                "tags": [{"kind": "knowledge_point", "name": "vertex form"}],
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
    assert mistake_repository.mistakes == []
    assert mistake_repository.mistake_tags == []
