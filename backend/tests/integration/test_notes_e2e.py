from __future__ import annotations

from collections.abc import Iterator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from httpx import Response

from app.api.auth import get_auth_service
from app.api.mistakes import get_mistake_create_service
from app.api.notes import (
    get_note_create_service,
    get_note_crud_service,
    get_note_ingestion_service,
)
from app.core.auth_jwt import JwksFetchError
from app.core.settings import Settings
from app.core.wechat import WeChatIdentity
from app.main import app
from app.schemas.notes import NoteClassifyResult
from app.services.auth import AuthService, SupabaseWechatAuthGateway
from app.services.ingestion import InMemoryIngestSessionRepository, StoredObject
from app.services.mistakes import InMemoryMistakeRepository, MistakeCreateService
from app.services.notes import (
    InMemoryNoteRepository,
    NoteClassificationOutcome,
    NoteClassifier,
    NoteCreateService,
    NoteCrudService,
    NoteIngestionService,
)
from app.services.ocr import OCRInput, OCRProvider, OCRService
from app.services.tag_normalizer import InMemoryTagRepository, TagNormalizerService


class FakeWeChatClient:
    def exchange_code(self, code: str) -> WeChatIdentity:
        return WeChatIdentity(openid=f"test-notes-e2e-{code}-{uuid4().hex}")


class FakeFileStore:
    def get_object(self, object_key: str) -> StoredObject:
        return StoredObject(content=b"image", mime_type="image/png")


class TextOCRProvider(OCRProvider):
    def extract_text(self, ocr_input: OCRInput) -> str:
        return "raw note text"


class StaticNoteClassifier(NoteClassifier):
    def classify(
        self,
        *,
        user_id: str,
        ingest_session_id: str | None,
        ocr_text: str,
    ) -> NoteClassificationOutcome:
        return NoteClassificationOutcome(
            status="ready",
            result=NoteClassifyResult(
                subject="math",
                content="organized note",
                knowledge_points=["vertex form"],
            ),
        )


def _settings_or_skip() -> Settings:
    try:
        return Settings()  # type: ignore[call-arg]
    except Exception as exc:
        pytest.skip(f"Supabase .env is not configured: {exc}")


def _request_or_skip_jwks(
    client: TestClient,
    method: str,
    url: str,
    **kwargs: object,
) -> Response:
    try:
        return client.request(method, url, **kwargs)
    except JwksFetchError as exc:
        pytest.skip(f"Supabase JWKS unavailable: {exc}")


@pytest.fixture
def live_client_with_memory_notes() -> Iterator[TestClient]:
    settings = _settings_or_skip()
    session_repository = InMemoryIngestSessionRepository()
    note_repository = InMemoryNoteRepository()
    mistake_repository = InMemoryMistakeRepository()
    tag_repository = InMemoryTagRepository()

    app.dependency_overrides[get_auth_service] = lambda: AuthService(
        wechat_client=FakeWeChatClient(),
        supabase_gateway=SupabaseWechatAuthGateway(settings),
    )
    app.dependency_overrides[get_note_ingestion_service] = lambda: NoteIngestionService(
        file_store=FakeFileStore(),
        session_repository=session_repository,
        ocr_service=OCRService(provider=TextOCRProvider()),
        classifier=StaticNoteClassifier(),
    )
    app.dependency_overrides[get_note_create_service] = lambda: NoteCreateService(
        note_repository=note_repository,
        tag_normalizer=TagNormalizerService(repository=tag_repository),
    )
    app.dependency_overrides[get_note_crud_service] = lambda: NoteCrudService(
        note_repository=note_repository,
        tag_normalizer=TagNormalizerService(repository=tag_repository),
    )
    app.dependency_overrides[get_mistake_create_service] = lambda: MistakeCreateService(
        mistake_repository=mistake_repository,
        tag_normalizer=TagNormalizerService(repository=tag_repository),
    )
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_note_e2e_owner_only(live_client_with_memory_notes: TestClient) -> None:
    client = live_client_with_memory_notes
    login_a = client.post("/auth/wx-login", json={"code": "note-a"})
    login_b = client.post("/auth/wx-login", json={"code": "note-b"})
    assert login_a.status_code == 200
    assert login_b.status_code == 200
    token_a = login_a.json()["access_token"]
    token_b = login_b.json()["access_token"]
    user_a = login_a.json()["user_profile"]["id"]
    user_b = login_b.json()["user_profile"]["id"]
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    ingest_response = _request_or_skip_jwks(
        client,
        "POST",
        "/notes/ingest",
        headers=headers_a,
        json={
            "object_key": f"note/{user_a}/note.png",
            "source_type": "photo",
            "subject_id": 1,
        },
    )
    assert ingest_response.status_code == 200

    create_note_response = _request_or_skip_jwks(
        client,
        "POST",
        "/notes",
        headers=headers_a,
        json={
            "ingest_session_id": ingest_response.json()["session_id"],
            "subject_id": 1,
            "source_type": "photo",
            "object_key": f"note/{user_a}/note.png",
            "ocr_text": ingest_response.json()["ocr_text"],
            "content": "organized note",
            "tags": [{"kind": "knowledge_point", "name": "vertex form"}],
        },
    )
    assert create_note_response.status_code == 200
    note_id = create_note_response.json()["id"]

    create_mistake_response = _request_or_skip_jwks(
        client,
        "POST",
        "/mistakes",
        headers=headers_a,
        json={
            "subject_id": 1,
            "source_type": "photo",
            "object_key": f"mistake/{user_a}/mistake.png",
            "question": "shared tag mistake",
            "tags": [{"kind": "knowledge_point", "name": "vertex form"}],
        },
    )
    assert create_mistake_response.status_code == 200
    assert (
        create_note_response.json()["tags"][0]["id"]
        == create_mistake_response.json()["tags"][0]["id"]
    )

    list_a = _request_or_skip_jwks(client, "GET", "/notes", headers=headers_a)
    list_b = _request_or_skip_jwks(client, "GET", "/notes", headers=headers_b)
    assert list_a.status_code == 200
    assert [item["id"] for item in list_a.json()["items"]] == [note_id]
    assert list_b.status_code == 200
    assert list_b.json()["items"] == []

    patch_response = _request_or_skip_jwks(
        client,
        "PATCH",
        f"/notes/{note_id}",
        headers=headers_a,
        json={
            "subject_id": 1,
            "source_type": "photo",
            "object_key": f"note/{user_a}/note.png",
            "content": "updated organized note",
            "tags": [
                {"kind": "knowledge_point", "name": "vertex form"},
                {"kind": "knowledge_point", "name": "vertexform"},
                {"kind": "knowledge_point", "name": " vertex  form "},
                {"kind": "knowledge_point", "name": "vertex form."},
                {"kind": "knowledge_point", "name": "vertex\tform,"},
            ],
        },
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["content"] == "updated organized note"
    assert len(patch_response.json()["tags"]) == 1
    assert patch_response.json()["tags"][0]["normalized_name"] == "vertexform"

    delete_response = _request_or_skip_jwks(
        client,
        "DELETE",
        f"/notes/{note_id}",
        headers=headers_a,
    )
    assert delete_response.status_code == 204
    assert _request_or_skip_jwks(client, "GET", "/notes", headers=headers_a).json()["items"] == []
    assert (
        _request_or_skip_jwks(client, "GET", f"/notes/{note_id}", headers=headers_a).status_code
        == 404
    )
    assert (
        _request_or_skip_jwks(client, "GET", f"/notes/{note_id}", headers=headers_b).status_code
        == 404
    )
    assert user_a != user_b
