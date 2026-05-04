from __future__ import annotations

import respx
from httpx import Response

from app.errors import ErrorCode
from app.services.classifier import ClassifierService
from app.services.llm.deepseek import DeepSeekClient, LLMCallRecord


class MemoryAuditSink:
    def __init__(self) -> None:
        self.records: list[LLMCallRecord] = []

    def record_llm_call(self, record: LLMCallRecord) -> None:
        self.records.append(record)


@respx.mock
def test_invalid_json_twice_returns_pending() -> None:
    audit = MemoryAuditSink()
    deepseek = DeepSeekClient(
        api_key="deepseek-test-key",
        base_url="https://deepseek.local",
        model="deepseek-chat",
        audit_sink=audit,
    )
    route = respx.post("https://deepseek.local/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "choices": [{"message": {"content": "```json\nnot-json\n```"}}],
                "usage": {"prompt_tokens": 7, "completion_tokens": 2},
            },
        )
    )

    outcome = ClassifierService(deepseek_client=deepseek).classify(
        user_id="00000000-0000-4000-8000-000000000001",
        ingest_session_id="00000000-0000-4000-8000-000000000002",
        ocr_text="OCR 文本",
    )

    assert outcome.status == "pending_classification"
    assert outcome.result is None
    assert outcome.error_code == ErrorCode.LLM_SCHEMA_INVALID
    assert route.call_count == 2
    assert audit.records[-1].schema_hit is False
    assert audit.records[-1].retry_count == 1
