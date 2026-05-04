from __future__ import annotations

from pathlib import Path

import respx
from fastapi.testclient import TestClient
from httpx import Response
from pypdf import PdfWriter

from app.api.notes import get_note_ingestion_service
from app.deps import CurrentUser, current_user
from app.main import app
from app.services.ingestion import InMemoryIngestSessionRepository, StoredObject
from app.services.llm.deepseek import DeepSeekClient, LLMCallRecord
from app.services.notes import NoteClassifierService, NoteIngestionService
from app.services.ocr import OCRInput, OCRProvider, OCRService
from app.services.pdf import PDFQuestionSplitter

USER_ID = "00000000-0000-4000-8000-000000000001"
FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures"
SAMPLE_PDF = FIXTURE_DIR / "sample_exam.pdf"
IMAGE_ONLY_PDF = FIXTURE_DIR / "image_only.pdf"


class PDFFileStore:
    def __init__(self, content: bytes) -> None:
        self._content = content

    def get_object(self, object_key: str) -> StoredObject:
        return StoredObject(content=self._content, mime_type="application/pdf")


class TripWireOCRProvider(OCRProvider):
    def extract_text(self, ocr_input: OCRInput) -> str:
        raise AssertionError("PDF note ingest must use pypdf, not OCR provider")


class MemoryAuditSink:
    def __init__(self) -> None:
        self.records: list[LLMCallRecord] = []

    def record_llm_call(self, record: LLMCallRecord) -> None:
        self.records.append(record)


def _override_note_pdf_ingestion_service(
    audit: MemoryAuditSink,
    *,
    content: bytes | None = None,
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
        file_store=PDFFileStore(content if content is not None else SAMPLE_PDF.read_bytes()),
        session_repository=session_repository,
        ocr_service=OCRService(provider=TripWireOCRProvider()),
        classifier=NoteClassifierService(deepseek_client=deepseek),
    )
    return session_repository


def _valid_response(content: str) -> Response:
    escaped_content = content.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return Response(
        200,
        json={
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"subject":"math","content":"'
                            + escaped_content
                            + '","knowledge_points":["vertex form"]}'
                        )
                    }
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 8},
        },
    )


@respx.mock
def test_note_pdf_ingest_ready_path_uses_full_pdf_text() -> None:
    audit = MemoryAuditSink()
    expected_text = PDFQuestionSplitter().extract_questions(SAMPLE_PDF.read_bytes()).text
    route = respx.post("https://deepseek.local/chat/completions").mock(
        return_value=_valid_response(expected_text)
    )
    session_repository = _override_note_pdf_ingestion_service(audit)
    try:
        client = TestClient(app)
        response = client.post(
            "/notes/ingest",
            json={
                "object_key": f"note/{USER_ID}/sample.pdf",
                "source_type": "pdf",
                "subject_id": 1,
            },
        )
    finally:
        app.dependency_overrides.clear()

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "ready"
    assert body["ocr_text"] == expected_text
    assert body["candidates"][0]["content"] == expected_text
    assert route.call_count == 1
    assert audit.records[-1].schema_hit is True
    assert session_repository.sessions[body["session_id"]]["status"] == "classified"


@respx.mock
def test_note_pdf_ingest_rejects_pdf_without_text_layer() -> None:
    audit = MemoryAuditSink()
    session_repository = _override_note_pdf_ingestion_service(
        audit,
        content=IMAGE_ONLY_PDF.read_bytes(),
    )
    try:
        client = TestClient(app)
        response = client.post(
            "/notes/ingest",
            json={
                "object_key": f"note/{USER_ID}/image-only.pdf",
                "source_type": "pdf",
                "subject_id": 1,
            },
        )
    finally:
        app.dependency_overrides.clear()

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "ocr_failed"
    assert body["error_code"] == "PDF_TEXT_EXTRACTION_FAILED"
    assert audit.records == []
    assert session_repository.sessions[body["session_id"]]["status"] == "failed"


@respx.mock
def test_note_pdf_ingest_rejects_oversized_pdf() -> None:
    audit = MemoryAuditSink()
    session_repository = _override_note_pdf_ingestion_service(
        audit,
        content=b"%PDF-1.4\n" + b"x" * (11 * 1024 * 1024),
    )
    try:
        client = TestClient(app)
        response = client.post(
            "/notes/ingest",
            json={
                "object_key": f"note/{USER_ID}/oversized.pdf",
                "source_type": "pdf",
                "subject_id": 1,
            },
        )
    finally:
        app.dependency_overrides.clear()

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "ocr_failed"
    assert body["error_code"] == "UPLOAD_LIMIT_EXCEEDED"
    assert audit.records == []
    assert session_repository.sessions[body["session_id"]]["status"] == "failed"


@respx.mock
def test_note_pdf_ingest_rejects_too_many_pages() -> None:
    writer = PdfWriter()
    for _ in range(21):
        writer.add_blank_page(width=72, height=72)
    pdf_path = FIXTURE_DIR / "tmp_note_21_pages.pdf"
    try:
        with pdf_path.open("wb") as file:
            writer.write(file)
        audit = MemoryAuditSink()
        session_repository = _override_note_pdf_ingestion_service(
            audit,
            content=pdf_path.read_bytes(),
        )
        client = TestClient(app)
        response = client.post(
            "/notes/ingest",
            json={
                "object_key": f"note/{USER_ID}/too-many-pages.pdf",
                "source_type": "pdf",
                "subject_id": 1,
            },
        )
    finally:
        app.dependency_overrides.clear()
        pdf_path.unlink(missing_ok=True)

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "ocr_failed"
    assert body["error_code"] == "UPLOAD_LIMIT_EXCEEDED"
    assert audit.records == []
    assert session_repository.sessions[body["session_id"]]["status"] == "failed"
