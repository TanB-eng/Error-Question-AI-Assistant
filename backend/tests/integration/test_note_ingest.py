from __future__ import annotations

import respx
from fastapi.testclient import TestClient
from httpx import Response

from app.api.notes import get_note_ingestion_service
from app.deps import CurrentUser, current_user
from app.main import app
from app.services.ingestion import InMemoryIngestSessionRepository, StoredObject
from app.services.llm.deepseek import DeepSeekClient, LLMCallRecord
from app.services.notes import NoteClassifierService, NoteIngestionService
from app.services.ocr import OCRInput, OCRProvider, OCRService

USER_ID = "00000000-0000-4000-8000-000000000001"
OTHER_USER_ID = "00000000-0000-4000-8000-000000000002"
OBJECT_KEY = f"note/{USER_ID}/file.png"


class ImageFileStore:
    def __init__(self, *, mime_type: str = "image/png", content: bytes = b"image") -> None:
        self._mime_type = mime_type
        self._content = content

    def get_object(self, object_key: str) -> StoredObject:
        return StoredObject(content=self._content, mime_type=self._mime_type)


class TripWireFileStore:
    def get_object(self, object_key: str) -> StoredObject:
        raise AssertionError("storage must not be called for cross-user object_key")


class MockOCRProvider(OCRProvider):
    def extract_text(self, ocr_input: OCRInput) -> str:
        return "recognized note text"


class MemoryAuditSink:
    def __init__(self) -> None:
        self.records: list[LLMCallRecord] = []

    def record_llm_call(self, record: LLMCallRecord) -> None:
        self.records.append(record)


def _override_note_ingestion_service(
    audit: MemoryAuditSink,
    *,
    file_store: object | None = None,
    mime_type: str = "image/png",
    content: bytes = b"image",
) -> InMemoryIngestSessionRepository:
    session_repository = InMemoryIngestSessionRepository()
    deepseek = DeepSeekClient(
        api_key="deepseek-test-key",
        base_url="https://deepseek.local",
        model="deepseek-chat",
        audit_sink=audit,
    )
    app.dependency_overrides[current_user] = lambda: CurrentUser(
        id=USER_ID,
        access_token="jwt",
    )
    app.dependency_overrides[get_note_ingestion_service] = lambda: NoteIngestionService(
        file_store=(
            file_store
            if file_store is not None
            else ImageFileStore(mime_type=mime_type, content=content)
        ),
        session_repository=session_repository,
        ocr_service=OCRService(provider=MockOCRProvider()),
        classifier=NoteClassifierService(deepseek_client=deepseek),
    )
    return session_repository


def _valid_response(content: str = "organized note") -> Response:
    return Response(
        200,
        json={
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"subject":"math","content":"'
                            + content
                            + '","knowledge_points":["vertex form"]}'
                        )
                    }
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 8},
        },
    )


def _invalid_response() -> Response:
    return Response(
        200,
        json={
            "choices": [{"message": {"content": "```json\nnot-json\n```"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 1},
        },
    )


@respx.mock
def test_note_image_ingest_ready_path() -> None:
    audit = MemoryAuditSink()
    route = respx.post("https://deepseek.local/chat/completions").mock(
        return_value=_valid_response()
    )
    session_repository = _override_note_ingestion_service(audit)
    try:
        client = TestClient(app)
        response = client.post(
            "/notes/ingest",
            json={"object_key": OBJECT_KEY, "source_type": "photo", "subject_id": 1},
        )
    finally:
        app.dependency_overrides.clear()

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "ready"
    assert body["ocr_text"] == "recognized note text"
    assert body["candidates"][0]["content"] == "organized note"
    assert route.call_count == 1
    assert audit.records[-1].schema_hit is True
    assert session_repository.sessions[body["session_id"]]["status"] == "classified"


@respx.mock
def test_note_image_ingest_invalid_json_twice_pending_path() -> None:
    audit = MemoryAuditSink()
    route = respx.post("https://deepseek.local/chat/completions").mock(
        return_value=_invalid_response()
    )
    session_repository = _override_note_ingestion_service(audit)
    try:
        client = TestClient(app)
        response = client.post(
            "/notes/ingest",
            json={"object_key": OBJECT_KEY, "source_type": "photo", "subject_id": 1},
        )
    finally:
        app.dependency_overrides.clear()

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "pending_classification"
    assert body["error_code"] == "LLM_SCHEMA_INVALID"
    assert body["candidates"][0]["content"] == body["ocr_text"]
    assert route.call_count == 2
    assert audit.records[-1].schema_hit is False
    assert audit.records[-1].retry_count == 1
    assert session_repository.sessions[body["session_id"]]["status"] == "pending"


@respx.mock
def test_note_image_ingest_retry_then_success_path() -> None:
    audit = MemoryAuditSink()
    route = respx.post("https://deepseek.local/chat/completions").mock(
        side_effect=[_invalid_response(), _valid_response()]
    )
    session_repository = _override_note_ingestion_service(audit)
    try:
        client = TestClient(app)
        response = client.post(
            "/notes/ingest",
            json={"object_key": OBJECT_KEY, "source_type": "photo", "subject_id": 1},
        )
    finally:
        app.dependency_overrides.clear()

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "ready"
    assert route.call_count == 2
    assert audit.records[-1].schema_hit is True
    assert audit.records[-1].retry_count == 1
    assert session_repository.sessions[body["session_id"]]["status"] == "classified"


@respx.mock
def test_note_image_ingest_rejects_unsupported_mime_type() -> None:
    audit = MemoryAuditSink()
    session_repository = _override_note_ingestion_service(audit, mime_type="application/zip")
    try:
        client = TestClient(app)
        response = client.post(
            "/notes/ingest",
            json={
                "object_key": f"note/{USER_ID}/file.zip",
                "source_type": "photo",
                "subject_id": 1,
            },
        )
    finally:
        app.dependency_overrides.clear()

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "ocr_failed"
    assert body["error_code"] == "UNSUPPORTED_MIME_TYPE"
    assert audit.records == []
    assert session_repository.sessions[body["session_id"]]["status"] == "failed"


@respx.mock
def test_note_image_ingest_rejects_object_key_owned_by_other_user() -> None:
    audit = MemoryAuditSink()
    session_repository = _override_note_ingestion_service(
        audit,
        file_store=TripWireFileStore(),
    )
    try:
        client = TestClient(app)
        response = client.post(
            "/notes/ingest",
            json={
                "object_key": f"note/{OTHER_USER_ID}/file.png",
                "source_type": "photo",
                "subject_id": 1,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
    assert audit.records == []
    assert session_repository.sessions == {}


@respx.mock
def test_note_image_ingest_rejects_oversized_image() -> None:
    audit = MemoryAuditSink()
    session_repository = _override_note_ingestion_service(
        audit,
        content=b"x" * (5 * 1024 * 1024 + 1),
    )
    try:
        client = TestClient(app)
        response = client.post(
            "/notes/ingest",
            json={"object_key": OBJECT_KEY, "source_type": "photo", "subject_id": 1},
        )
    finally:
        app.dependency_overrides.clear()

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "ocr_failed"
    assert body["error_code"] == "UPLOAD_LIMIT_EXCEEDED"
    assert audit.records == []
    assert session_repository.sessions[body["session_id"]]["status"] == "failed"
