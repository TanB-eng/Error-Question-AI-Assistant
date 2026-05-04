from __future__ import annotations

from uuid import UUID

from app.errors import ErrorCode
from app.schemas.classify import ClassifyResult
from app.schemas.mistakes import IngestStatus, MistakeIngestRequest
from app.schemas.uploads import PDF_MAX_SIZE_BYTES
from app.services.classifier import ClassificationOutcome
from app.services.ingestion import (
    IngestionService,
    InMemoryIngestSessionRepository,
    StoredObject,
)
from app.services.ocr import OCRInput, OCRProvider, OCRService

USER_ID = "00000000-0000-4000-8000-000000000001"
OBJECT_PREFIX = f"mistake/{USER_ID}"


class FakeFileStore:
    def __init__(self, stored_object: StoredObject) -> None:
        self.stored_object = stored_object
        self.requested_keys: list[str] = []

    def get_object(self, object_key: str) -> StoredObject:
        self.requested_keys.append(object_key)
        return self.stored_object


class TextOCRProvider(OCRProvider):
    def __init__(self, text: str) -> None:
        self.text = text

    def extract_text(self, ocr_input: OCRInput) -> str:
        return self.text


class BrokenOCRProvider(OCRProvider):
    def extract_text(self, ocr_input: OCRInput) -> str:
        raise RuntimeError("ocr failed")


class FakeClassifier:
    def __init__(self, outcome: ClassificationOutcome) -> None:
        self.outcome = outcome
        self.received_texts: list[str] = []

    def classify(
        self,
        *,
        user_id: str,
        ingest_session_id: str | None,
        ocr_text: str,
    ) -> ClassificationOutcome:
        self.received_texts.append(ocr_text)
        UUID(str(ingest_session_id))
        return self.outcome


def test_photo_ingest_returns_ready_candidate_with_mocks() -> None:
    repository = InMemoryIngestSessionRepository()
    classifier = FakeClassifier(
        ClassificationOutcome(
            status="ready",
            result=ClassifyResult(
                subject="math",
                question="model question",
                knowledge_points=["vertex form"],
                difficulty=3,
            ),
        )
    )
    service = IngestionService(
        file_store=FakeFileStore(StoredObject(content=b"image", mime_type="image/png")),
        session_repository=repository,
        ocr_service=OCRService(provider=TextOCRProvider("recognized question text")),
        classifier=classifier,
    )

    response = service.ingest_mistake(
        user_id=USER_ID,
        request=MistakeIngestRequest(
            object_key=f"{OBJECT_PREFIX}/file.png",
            source_type="photo",
            subject_id=1,
        ),
    )

    assert response.status == IngestStatus.READY
    assert response.ocr_text == "recognized question text"
    assert response.candidates[0].subject_id == 1
    assert response.candidates[0].question == "model question"
    assert classifier.received_texts == ["recognized question text"]
    assert repository.sessions[str(response.session_id)]["status"] == "classified"


def test_photo_ingest_ocr_failure_returns_manual_candidate() -> None:
    service = IngestionService(
        file_store=FakeFileStore(StoredObject(content=b"image", mime_type="image/png")),
        session_repository=InMemoryIngestSessionRepository(),
        ocr_service=OCRService(provider=BrokenOCRProvider()),
        classifier=FakeClassifier(
            ClassificationOutcome(status="pending_classification", result=None)
        ),
    )

    response = service.ingest_mistake(
        user_id=USER_ID,
        request=MistakeIngestRequest(
            object_key=f"{OBJECT_PREFIX}/file.png",
            source_type="photo",
            subject_id=1,
        ),
    )

    assert response.status == IngestStatus.OCR_FAILED
    assert response.candidates == []
    assert response.error_code == ErrorCode.OCR_FAILED


def test_photo_ingest_llm_failure_returns_pending_candidate() -> None:
    service = IngestionService(
        file_store=FakeFileStore(StoredObject(content=b"image", mime_type="image/png")),
        session_repository=InMemoryIngestSessionRepository(),
        ocr_service=OCRService(provider=TextOCRProvider("recognized question text")),
        classifier=FakeClassifier(
            ClassificationOutcome(
                status="pending_classification",
                result=None,
                error_code=ErrorCode.LLM_SCHEMA_INVALID,
            )
        ),
    )

    response = service.ingest_mistake(
        user_id=USER_ID,
        request=MistakeIngestRequest(
            object_key=f"{OBJECT_PREFIX}/file.png",
            source_type="photo",
            subject_id=1,
        ),
    )

    assert response.status == IngestStatus.PENDING_CLASSIFICATION
    assert response.error_code == ErrorCode.LLM_SCHEMA_INVALID
    assert response.candidates[0].question == "recognized question text"
    assert response.candidates[0].knowledge_points == []


def test_photo_ingest_large_image_returns_upload_limit_exceeded() -> None:
    service = IngestionService(
        file_store=FakeFileStore(
            StoredObject(
                content=b"x" * (5 * 1024 * 1024 + 1),
                mime_type="image/png",
            )
        ),
        session_repository=InMemoryIngestSessionRepository(),
        ocr_service=OCRService(provider=TextOCRProvider("unused")),
        classifier=FakeClassifier(
            ClassificationOutcome(status="pending_classification", result=None)
        ),
    )

    response = service.ingest_mistake(
        user_id=USER_ID,
        request=MistakeIngestRequest(
            object_key=f"{OBJECT_PREFIX}/file.png",
            source_type="photo",
            subject_id=1,
        ),
    )

    assert response.status == IngestStatus.OCR_FAILED
    assert response.error_code == ErrorCode.UPLOAD_LIMIT_EXCEEDED


def test_pdf_ingest_over_limit_returns_upload_limit_exceeded() -> None:
    service = IngestionService(
        file_store=FakeFileStore(
            StoredObject(
                content=b"x" * (PDF_MAX_SIZE_BYTES + 1),
                mime_type="application/pdf",
            )
        ),
        session_repository=InMemoryIngestSessionRepository(),
        ocr_service=OCRService(provider=TextOCRProvider("unused")),
        classifier=FakeClassifier(
            ClassificationOutcome(status="pending_classification", result=None)
        ),
    )

    response = service.ingest_mistake(
        user_id=USER_ID,
        request=MistakeIngestRequest(
            object_key=f"{OBJECT_PREFIX}/file.pdf",
            source_type="pdf",
            subject_id=1,
        ),
    )

    assert response.status == IngestStatus.OCR_FAILED
    assert response.error_code == ErrorCode.UPLOAD_LIMIT_EXCEEDED


def test_ingest_rejects_unsupported_mime_type_before_ocr() -> None:
    repository = InMemoryIngestSessionRepository()
    classifier = FakeClassifier(
        ClassificationOutcome(status="pending_classification", result=None)
    )
    service = IngestionService(
        file_store=FakeFileStore(
            StoredObject(content=b"payload", mime_type="text/plain")
        ),
        session_repository=repository,
        ocr_service=OCRService(provider=TextOCRProvider("unused")),
        classifier=classifier,
    )

    response = service.ingest_mistake(
        user_id=USER_ID,
        request=MistakeIngestRequest(
            object_key=f"{OBJECT_PREFIX}/file.txt",
            source_type="photo",
            subject_id=1,
        ),
    )

    assert response.status == IngestStatus.OCR_FAILED
    assert response.error_code == ErrorCode.UNSUPPORTED_MIME_TYPE
    assert classifier.received_texts == []
    assert list(repository.sessions.values())[0]["status"] == "failed"