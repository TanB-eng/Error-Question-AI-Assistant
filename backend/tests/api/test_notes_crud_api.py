from __future__ import annotations

from uuid import UUID

from fastapi.testclient import TestClient

from app.api.notes import get_note_crud_service
from app.deps import CurrentUser, current_user
from app.main import app
from app.schemas.notes import NoteDetail, NoteListResponse, NoteUpdateRequest
from app.services.notes import NoteNotFoundError

USER_ID = "00000000-0000-4000-8000-000000000001"
NOTE_ID = "00000000-0000-4000-8000-000000000010"


class FakeNoteCrudService:
    def __init__(self) -> None:
        self.deleted: list[str] = []
        self.updates: list[NoteUpdateRequest] = []

    def list_notes(
        self,
        *,
        user_id: str,
        subject_id: int | None = None,
        tag_id: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> NoteListResponse:
        return NoteListResponse(
            items=[
                _detail(
                    content="active note",
                    note_id=NOTE_ID,
                )
            ],
            page=page,
            page_size=page_size,
            total=1,
        )

    def get_note(self, *, user_id: str, note_id: str) -> NoteDetail:
        return _detail(content="active note", note_id=note_id)

    def update_note(
        self,
        *,
        user_id: str,
        note_id: str,
        request: NoteUpdateRequest,
    ) -> NoteDetail:
        self.updates.append(request)
        return _detail(content=request.content, note_id=note_id)

    def delete_note(self, *, user_id: str, note_id: str) -> None:
        self.deleted.append(note_id)


class MissingNoteCrudService(FakeNoteCrudService):
    def get_note(self, *, user_id: str, note_id: str) -> NoteDetail:
        raise NoteNotFoundError("missing")


def _detail(*, content: str, note_id: str) -> NoteDetail:
    return NoteDetail(
        id=UUID(note_id),
        subject_id=1,
        content_excerpt=content,
        tags=[],
        created_at="2026-05-04T00:00:00Z",
        object_key=f"note/{USER_ID}/file.png",
        ocr_text="ocr",
        content=content,
    )


def _override_user() -> None:
    app.dependency_overrides[current_user] = lambda: CurrentUser(id=USER_ID, access_token="jwt")


def test_note_soft_delete_hides_from_active_list() -> None:
    service = FakeNoteCrudService()
    _override_user()
    app.dependency_overrides[get_note_crud_service] = lambda: service
    client = TestClient(app)

    try:
        delete_response = client.delete(f"/notes/{NOTE_ID}")
        list_response = client.get("/notes")
    finally:
        app.dependency_overrides.clear()

    assert delete_response.status_code == 204
    assert service.deleted == [NOTE_ID]
    assert list_response.status_code == 200
    assert list_response.json()["items"][0]["content_excerpt"] == "active note"


def test_note_detail_update_and_not_found_mapping() -> None:
    service = FakeNoteCrudService()
    _override_user()
    app.dependency_overrides[get_note_crud_service] = lambda: service
    client = TestClient(app)

    try:
        detail_response = client.get(f"/notes/{NOTE_ID}")
        patch_response = client.patch(
            f"/notes/{NOTE_ID}",
            json={
                "subject_id": 2,
                "source_type": "photo",
                "object_key": f"note/{USER_ID}/file.png",
                "content": "updated note",
                "tags": [{"kind": "knowledge_point", "name": "vertex form"}],
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert detail_response.status_code == 200
    assert patch_response.status_code == 200
    assert patch_response.json()["content"] == "updated note"
    assert service.updates[0].subject_id == 2

    _override_user()
    app.dependency_overrides[get_note_crud_service] = lambda: MissingNoteCrudService()
    try:
        not_found_response = TestClient(app).get(f"/notes/{NOTE_ID}")
    finally:
        app.dependency_overrides.clear()

    assert not_found_response.status_code == 404
    assert not_found_response.json()["error"]["code"] == "OBJECT_NOT_FOUND"
