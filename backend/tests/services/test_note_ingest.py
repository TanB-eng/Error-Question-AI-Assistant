from __future__ import annotations

from app.errors import ErrorCode
from app.schemas.mistakes import IngestStatus
from app.schemas.notes import NoteClassifyResult, NoteIngestRequest
from app.services.ingestion import InMemoryIngestSessionRepository, StoredObject
from app.services.notes import (
    NoteClassificationOutcome,
    NoteClassifierService,
    NoteIngestionService,
)
from app.services.ocr import OCRInput, OCRProvider, OCRService

USER_ID = "00000000-0000-4000-8000-000000000001"
OBJECT_KEY = f"note/{USER_ID}/file.png"


class FakeFileStore:
    def __init__(self, *, mime_type: str = "image/png", content: bytes = b"image") -> None:
        self._mime_type = mime_type
        self._content = content

    def get_object(self, object_key: str) -> StoredObject:
        return StoredObject(content=self._content, mime_type=self._mime_type)


class TextOCRProvider(OCRProvider):
    def extract_text(self, ocr_input: OCRInput) -> str:
        return "raw note OCR text"


class FakeNoteClassifier:
    def __init__(self, outcome: NoteClassificationOutcome) -> None:
        self.outcome = outcome
        self.received_texts: list[str] = []

    def classify(
        self,
        *,
        user_id: str,
        ingest_session_id: str | None,
        ocr_text: str,
    ) -> NoteClassificationOutcome:
        self.received_texts.append(ocr_text)
        return self.outcome


class InvalidJSONNoteClient:
    def classify_note_text(
        self,
        *,
        user_id: str,
        ingest_session_id: str | None,
        ocr_text: str,
    ) -> NoteClassifyResult:
        from app.services.llm.deepseek import LLMClassificationError

        raise LLMClassificationError(ErrorCode.LLM_SCHEMA_INVALID)


def test_note_ingest_returns_ready_candidate() -> None:
    repository = InMemoryIngestSessionRepository()
    classifier = FakeNoteClassifier(
        NoteClassificationOutcome(
            status="ready",
            result=NoteClassifyResult(
                subject="math",
                content="organized note",
                knowledge_points=["vertex form"],
            ),
        )
    )
    service = NoteIngestionService(
        file_store=FakeFileStore(),
        session_repository=repository,
        ocr_service=OCRService(provider=TextOCRProvider()),
        classifier=classifier,
    )

    response = service.ingest_note(
        user_id=USER_ID,
        request=NoteIngestRequest(object_key=OBJECT_KEY, source_type="photo", subject_id=1),
    )

    assert response.status == IngestStatus.READY
    assert response.candidates[0].content == "organized note"
    assert response.candidates[0].knowledge_points == ["vertex form"]
    assert repository.sessions[str(response.session_id)]["scene"] == "note"
    assert repository.sessions[str(response.session_id)]["status"] == "classified"


def test_note_invalid_json_twice_returns_pending() -> None:
    repository = InMemoryIngestSessionRepository()
    service = NoteIngestionService(
        file_store=FakeFileStore(),
        session_repository=repository,
        ocr_service=OCRService(provider=TextOCRProvider()),
        classifier=NoteClassifierService(deepseek_client=InvalidJSONNoteClient()),
    )

    response = service.ingest_note(
        user_id=USER_ID,
        request=NoteIngestRequest(object_key=OBJECT_KEY, source_type="photo", subject_id=1),
    )

    assert response.status == IngestStatus.PENDING_CLASSIFICATION
    assert response.error_code == ErrorCode.LLM_SCHEMA_INVALID
    assert response.candidates[0].content == "raw note OCR text"
    assert response.candidates[0].knowledge_points == []
    assert repository.sessions[str(response.session_id)]["status"] == "pending"


def test_note_ingest_rejects_unsupported_mime_type_before_llm() -> None:
    repository = InMemoryIngestSessionRepository()
    classifier = FakeNoteClassifier(
        NoteClassificationOutcome(status="pending_classification", result=None)
    )
    service = NoteIngestionService(
        file_store=FakeFileStore(mime_type="application/zip", content=b"zip"),
        session_repository=repository,
        ocr_service=OCRService(provider=TextOCRProvider()),
        classifier=classifier,
    )

    response = service.ingest_note(
        user_id=USER_ID,
        request=NoteIngestRequest(
            object_key=f"note/{USER_ID}/file.zip",
            source_type="photo",
            subject_id=1,
        ),
    )

    assert response.status == IngestStatus.OCR_FAILED
    assert response.error_code == ErrorCode.UNSUPPORTED_MIME_TYPE
    assert classifier.received_texts == []
    assert repository.sessions[str(response.session_id)]["status"] == "failed"
