from __future__ import annotations

from pathlib import Path

import respx
from fastapi.testclient import TestClient
from httpx import Response
from pypdf import PdfWriter

from app.api.mistakes import get_ingestion_service
from app.deps import CurrentUser, current_user
from app.main import app
from app.services.classifier import ClassifierService
from app.services.ingestion import (
    IngestionService,
    InMemoryIngestSessionRepository,
    StoredObject,
)
from app.services.llm.deepseek import DeepSeekClient, LLMCallRecord
from app.services.ocr import OCRInput, OCRProvider, OCRService

USER_ID = "00000000-0000-4000-8000-000000000001"
SAMPLE_PDF = Path(__file__).resolve().parents[1] / "fixtures" / "sample_exam.pdf"


class PDFFileStore:
    def __init__(self, content: bytes) -> None:
        self._content = content

    def get_object(self, object_key: str) -> StoredObject:
        return StoredObject(content=self._content, mime_type="application/pdf")


class TripWireOCRProvider(OCRProvider):
    def extract_text(self, ocr_input: OCRInput) -> str:
        raise AssertionError("PDF ingest must use pypdf, not OCR provider")


class MemoryAuditSink:
    def __init__(self) -> None:
        self.records: list[LLMCallRecord] = []

    def record_llm_call(self, record: LLMCallRecord) -> None:
        self.records.append(record)


def _override_pdf_ingestion_service(
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
    app.dependency_overrides[get_ingestion_service] = lambda: IngestionService(
        file_store=PDFFileStore(content if content is not None else SAMPLE_PDF.read_bytes()),
        session_repository=session_repository,
        ocr_service=OCRService(provider=TripWireOCRProvider()),
        classifier=ClassifierService(deepseek_client=deepseek),
    )
    return session_repository


def _valid_response(question: str) -> Response:
    return Response(
        200,
        json={
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"subject":"math","question":"'
                            + question
                            + '","my_answer":"","correct_answer":"",'
                            '"knowledge_points":["linear equation"],'
                            '"question_type":"","difficulty":2,'
                            '"error_cause":"","analysis":""}'
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
def test_pdf_ingest_returns_multiple_review_candidates() -> None:
    audit = MemoryAuditSink()
    route = respx.post("https://deepseek.local/chat/completions").mock(
        side_effect=[
            _valid_response("classified question 1"),
            _valid_response("classified question 2"),
            _valid_response("classified question 3"),
        ]
    )
    session_repository = _override_pdf_ingestion_service(audit)
    try:
        client = TestClient(app)
        response = client.post(
            "/mistakes/ingest",
            json={
                "object_key": f"mistake/{USER_ID}/sample.pdf",
                "source_type": "pdf",
                "subject_id": 1,
            },
        )
    finally:
        app.dependency_overrides.clear()

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "ready"
    assert len(body["candidates"]) == 3
    assert [candidate["status"] for candidate in body["candidates"]] == [
        "ready",
        "ready",
        "ready",
    ]
    assert [candidate["page_number"] for candidate in body["candidates"]] == [1, 1, 1]
    assert route.call_count == 3
    assert len(audit.records) == 3
    assert session_repository.sessions[body["session_id"]]["status"] == "classified"


@respx.mock
def test_pdf_ingest_allows_partial_pending_candidates() -> None:
    audit = MemoryAuditSink()
    route = respx.post("https://deepseek.local/chat/completions").mock(
        side_effect=[
            _valid_response("classified question 1"),
            _invalid_response(),
            _invalid_response(),
            _valid_response("classified question 3"),
        ]
    )
    session_repository = _override_pdf_ingestion_service(audit)
    try:
        client = TestClient(app)
        response = client.post(
            "/mistakes/ingest",
            json={
                "object_key": f"mistake/{USER_ID}/sample.pdf",
                "source_type": "pdf",
                "subject_id": 1,
            },
        )
    finally:
        app.dependency_overrides.clear()

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "pending_classification"
    assert [candidate["status"] for candidate in body["candidates"]] == [
        "ready",
        "pending_classification",
        "ready",
    ]
    assert body["candidates"][1]["error_code"] == "LLM_SCHEMA_INVALID"
    assert route.call_count == 4
    assert len(audit.records) == 3
    assert session_repository.sessions[body["session_id"]]["status"] == "pending"


@respx.mock
def test_pdf_ingest_rejects_oversized_pdf() -> None:
    audit = MemoryAuditSink()
    session_repository = _override_pdf_ingestion_service(
        audit,
        content=b"%PDF-1.4\n" + b"x" * (11 * 1024 * 1024),
    )
    try:
        client = TestClient(app)
        response = client.post(
            "/mistakes/ingest",
            json={
                "object_key": f"mistake/{USER_ID}/oversized.pdf",
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
def test_pdf_ingest_rejects_too_many_pages() -> None:
    writer = PdfWriter()
    for _ in range(21):
        writer.add_blank_page(width=72, height=72)
    pdf_buffer = Path(__file__).resolve().parents[1] / "fixtures" / "tmp_21_pages.pdf"
    try:
        with pdf_buffer.open("wb") as file:
            writer.write(file)
        audit = MemoryAuditSink()
        session_repository = _override_pdf_ingestion_service(
            audit,
            content=pdf_buffer.read_bytes(),
        )
        client = TestClient(app)
        response = client.post(
            "/mistakes/ingest",
            json={
                "object_key": f"mistake/{USER_ID}/too-many-pages.pdf",
                "source_type": "pdf",
                "subject_id": 1,
            },
        )
    finally:
        app.dependency_overrides.clear()
        pdf_buffer.unlink(missing_ok=True)

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "ocr_failed"
    assert body["error_code"] == "UPLOAD_LIMIT_EXCEEDED"
    assert audit.records == []
    assert session_repository.sessions[body["session_id"]]["status"] == "failed"
