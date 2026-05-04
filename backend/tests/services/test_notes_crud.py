from __future__ import annotations

import pytest

from app.schemas.notes import NoteCreateRequest, NoteUpdateRequest
from app.services.notes import (
    InMemoryNoteRepository,
    NoteCreateService,
    NoteCrudService,
    NoteNotFoundError,
    NoteObjectKeyOwnershipError,
)
from app.services.tag_normalizer import InMemoryTagRepository, TagNormalizerService

USER_ID = "00000000-0000-4000-8000-000000000001"
OTHER_USER_ID = "00000000-0000-4000-8000-000000000002"


def test_note_crud_soft_delete_hides_note_from_list_and_detail() -> None:
    repository = InMemoryNoteRepository()
    tag_repository = InMemoryTagRepository()
    create_service = NoteCreateService(
        note_repository=repository,
        tag_normalizer=TagNormalizerService(repository=tag_repository),
    )
    crud_service = NoteCrudService(
        note_repository=repository,
        tag_normalizer=TagNormalizerService(repository=tag_repository),
    )
    note = create_service.create_note(user_id=USER_ID, request=_create_request())

    crud_service.delete_note(user_id=USER_ID, note_id=str(note.id))

    assert crud_service.list_notes(user_id=USER_ID).items == []
    with pytest.raises(NoteNotFoundError):
        crud_service.get_note(user_id=USER_ID, note_id=str(note.id))


def test_note_crud_update_replaces_tags_with_normalized_single_tag() -> None:
    repository = InMemoryNoteRepository()
    tag_repository = InMemoryTagRepository()
    create_service = NoteCreateService(
        note_repository=repository,
        tag_normalizer=TagNormalizerService(repository=tag_repository),
    )
    crud_service = NoteCrudService(
        note_repository=repository,
        tag_normalizer=TagNormalizerService(repository=tag_repository),
    )
    note = create_service.create_note(user_id=USER_ID, request=_create_request())

    updated = crud_service.update_note(
        user_id=USER_ID,
        note_id=str(note.id),
        request=NoteUpdateRequest(
            subject_id=1,
            source_type="photo",
            object_key=f"note/{USER_ID}/note.png",
            content="updated content",
            tags=[
                {"kind": "knowledge_point", "name": "vertex form"},
                {"kind": "knowledge_point", "name": "vertexform"},
                {"kind": "knowledge_point", "name": " vertex  form "},
                {"kind": "knowledge_point", "name": "vertex form."},
                {"kind": "knowledge_point", "name": "vertex\tform,"},
            ],
        ),
    )

    assert updated.content == "updated content"
    assert len(updated.tags) == 1
    assert updated.tags[0].normalized_name == "vertexform"


def test_note_create_rejects_cross_user_object_key_before_insert() -> None:
    repository = InMemoryNoteRepository()
    service = NoteCreateService(
        note_repository=repository,
        tag_normalizer=TagNormalizerService(repository=InMemoryTagRepository()),
    )

    with pytest.raises(NoteObjectKeyOwnershipError):
        service.create_note(
            user_id=USER_ID,
            request=NoteCreateRequest(
                subject_id=1,
                source_type="photo",
                object_key=f"note/{OTHER_USER_ID}/note.png",
                content="bad owner",
                tags=[],
            ),
        )

    assert repository.notes == []


def test_note_crud_cross_user_detail_returns_not_found() -> None:
    repository = InMemoryNoteRepository()
    create_service = NoteCreateService(
        note_repository=repository,
        tag_normalizer=TagNormalizerService(repository=InMemoryTagRepository()),
    )
    crud_service = NoteCrudService(
        note_repository=repository,
        tag_normalizer=TagNormalizerService(repository=InMemoryTagRepository()),
    )
    note = create_service.create_note(user_id=USER_ID, request=_create_request())

    with pytest.raises(NoteNotFoundError):
        crud_service.get_note(user_id=OTHER_USER_ID, note_id=str(note.id))


def _create_request() -> NoteCreateRequest:
    return NoteCreateRequest(
        subject_id=1,
        source_type="photo",
        object_key=f"note/{USER_ID}/note.png",
        content="organized content",
        tags=[{"kind": "knowledge_point", "name": "vertex form"}],
    )
