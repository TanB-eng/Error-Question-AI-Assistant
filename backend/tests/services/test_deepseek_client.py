from __future__ import annotations

import respx
from httpx import Response

from app.services.llm.deepseek import DeepSeekClient, LLMCallRecord


class MemoryAuditSink:
    def __init__(self) -> None:
        self.records: list[LLMCallRecord] = []

    def record_llm_call(self, record: LLMCallRecord) -> None:
        self.records.append(record)


@respx.mock
def test_invalid_json_retries_once() -> None:
    audit = MemoryAuditSink()
    client = DeepSeekClient(
        api_key="deepseek-test-key",
        base_url="https://deepseek.local",
        model="deepseek-chat",
        audit_sink=audit,
    )
    route = respx.post("https://deepseek.local/chat/completions").mock(
        side_effect=[
            Response(
                200,
                json={
                    "choices": [{"message": {"content": "```json\nnot-json\n```"}}],
                    "usage": {"prompt_tokens": 11, "completion_tokens": 3},
                },
            ),
            Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": (
                                    '{"subject":"数学","question":"题干","my_answer":"",'
                                    '"correct_answer":"","knowledge_points":["顶点式"],'
                                    '"question_type":"","difficulty":3,'
                                    '"error_cause":"","analysis":""}'
                                )
                            }
                        }
                    ],
                    "usage": {"prompt_tokens": 12, "completion_tokens": 8},
                },
            ),
        ]
    )

    result = client.classify_mistake_text(
        user_id="00000000-0000-4000-8000-000000000001",
        ingest_session_id="00000000-0000-4000-8000-000000000002",
        ocr_text="OCR 后的题干文本",
    )

    assert result.question == "题干"
    assert route.call_count == 2
    request_payload = route.calls[0].request.content.decode("utf-8")
    assert '"response_format":{"type":"json_object"}' in request_payload.replace(" ", "")
    assert '"max_tokens":1500' in request_payload.replace(" ", "")
    assert audit.records[-1].schema_hit is True
    assert audit.records[-1].retry_count == 1
    assert audit.records[-1].prompt_version == "classify_mistake_v1"


@respx.mock
def test_note_classification_uses_note_prompt() -> None:
    audit = MemoryAuditSink()
    client = DeepSeekClient(
        api_key="deepseek-test-key",
        base_url="https://deepseek.local",
        model="deepseek-chat",
        audit_sink=audit,
    )
    route = respx.post("https://deepseek.local/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"subject":"math","content":"organized note",'
                                '"knowledge_points":["vertex form"]}'
                            )
                        }
                    }
                ],
                "usage": {"prompt_tokens": 7, "completion_tokens": 5},
            },
        )
    )

    result = client.classify_note_text(
        user_id="00000000-0000-4000-8000-000000000001",
        ingest_session_id="00000000-0000-4000-8000-000000000002",
        ocr_text="raw note text",
    )

    assert result.content == "organized note"
    assert result.knowledge_points == ["vertex form"]
    assert route.call_count == 1
    request_payload = route.calls[0].request.content.decode("utf-8")
    assert "classify_note_v1" in request_payload
    assert audit.records[-1].prompt_version == "classify_note_v1"
