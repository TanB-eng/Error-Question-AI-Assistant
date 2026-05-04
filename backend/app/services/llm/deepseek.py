from __future__ import annotations

import json
import re
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import httpx
from pydantic import ValidationError

from app.core.supabase import SupabaseRestClient
from app.errors import ErrorCode
from app.schemas.classify import ClassifyResult

PROMPT_NAME = "classify_mistake"
PROMPT_VERSION = "classify_mistake_v1"
MAX_TOKENS = 1500
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_USER_RATE_LIMIT_PER_MINUTE = 20


@dataclass(frozen=True)
class LLMCallRecord:
    user_id: str
    prompt_name: str
    prompt_version: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    schema_hit: bool
    retry_count: int
    mistake_id: str | None = None
    ingest_session_id: str | None = None
    error_code: ErrorCode | None = None


class LLMAuditSink(Protocol):
    def record_llm_call(self, record: LLMCallRecord) -> None: ...


class NullLLMAuditSink:
    def record_llm_call(self, record: LLMCallRecord) -> None:
        return None


class SupabaseLLMAuditSink:
    def __init__(self, *, client: SupabaseRestClient) -> None:
        self._client = client

    def record_llm_call(self, record: LLMCallRecord) -> None:
        response = self._client.request(
            "POST",
            "/llm_calls",
            headers={"Prefer": "return=minimal"},
            json={
                "user_id": record.user_id,
                "mistake_id": record.mistake_id,
                "ingest_session_id": record.ingest_session_id,
                "prompt_name": record.prompt_name,
                "prompt_version": record.prompt_version,
                "model": record.model,
                "input_tokens": record.input_tokens,
                "output_tokens": record.output_tokens,
                "latency_ms": record.latency_ms,
                "schema_hit": record.schema_hit,
                "retry_count": record.retry_count,
                "error_code": record.error_code.value if record.error_code is not None else None,
            },
        )
        response.raise_for_status()


class LLMClassificationError(RuntimeError):
    def __init__(self, error_code: ErrorCode) -> None:
        super().__init__(error_code.value)
        self.error_code = error_code


class InMemoryUserRateLimiter:
    def __init__(self, *, limit_per_minute: int = DEFAULT_USER_RATE_LIMIT_PER_MINUTE) -> None:
        self._limit = limit_per_minute
        self._calls: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, user_id: str, *, now: float | None = None) -> bool:
        current = now if now is not None else time.monotonic()
        window_start = current - 60
        user_calls = self._calls[user_id]
        while user_calls and user_calls[0] < window_start:
            user_calls.popleft()
        if len(user_calls) >= self._limit:
            return False
        user_calls.append(current)
        return True


class DeepSeekClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        audit_sink: LLMAuditSink | None = None,
        client: httpx.Client | None = None,
        rate_limiter: InMemoryUserRateLimiter | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._audit_sink = audit_sink if audit_sink is not None else NullLLMAuditSink()
        self._client = client if client is not None else httpx.Client()
        self._rate_limiter = rate_limiter if rate_limiter is not None else InMemoryUserRateLimiter()
        self._timeout_seconds = timeout_seconds

    def classify_mistake_text(
        self,
        *,
        user_id: str,
        ingest_session_id: str | None,
        ocr_text: str,
    ) -> ClassifyResult:
        if not self._rate_limiter.allow(user_id):
            self._audit_failure(
                user_id=user_id,
                ingest_session_id=ingest_session_id,
                latency_ms=0,
                retry_count=0,
                error_code=ErrorCode.RATE_LIMIT_EXCEEDED,
            )
            raise LLMClassificationError(ErrorCode.RATE_LIMIT_EXCEEDED)

        started = time.perf_counter()
        prompt = _load_prompt()
        last_input_tokens = 0
        last_output_tokens = 0
        for retry_count in range(2):
            response = self._client.post(
                f"{self._base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": ocr_text},
                    ],
                    "response_format": {"type": "json_object"},
                    "max_tokens": MAX_TOKENS,
                },
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            last_input_tokens = _token_count(payload, "prompt_tokens")
            last_output_tokens = _token_count(payload, "completion_tokens")
            content = _message_content(payload)
            try:
                result = ClassifyResult.model_validate(json.loads(_strip_markdown_fence(content)))
                self._audit_sink.record_llm_call(
                    LLMCallRecord(
                        user_id=user_id,
                        prompt_name=PROMPT_NAME,
                        prompt_version=PROMPT_VERSION,
                        model=self._model,
                        input_tokens=last_input_tokens,
                        output_tokens=last_output_tokens,
                        latency_ms=_elapsed_ms(started),
                        schema_hit=True,
                        retry_count=retry_count,
                        ingest_session_id=ingest_session_id,
                    )
                )
                return result
            except (json.JSONDecodeError, ValidationError) as exc:
                if retry_count == 1:
                    self._audit_sink.record_llm_call(
                        LLMCallRecord(
                            user_id=user_id,
                            prompt_name=PROMPT_NAME,
                            prompt_version=PROMPT_VERSION,
                            model=self._model,
                            input_tokens=last_input_tokens,
                            output_tokens=last_output_tokens,
                            latency_ms=_elapsed_ms(started),
                            schema_hit=False,
                            retry_count=retry_count,
                            ingest_session_id=ingest_session_id,
                            error_code=ErrorCode.LLM_SCHEMA_INVALID,
                        )
                    )
                    raise LLMClassificationError(ErrorCode.LLM_SCHEMA_INVALID) from exc
        raise LLMClassificationError(ErrorCode.LLM_SCHEMA_INVALID)

    def _audit_failure(
        self,
        *,
        user_id: str,
        ingest_session_id: str | None,
        latency_ms: int,
        retry_count: int,
        error_code: ErrorCode,
    ) -> None:
        self._audit_sink.record_llm_call(
            LLMCallRecord(
                user_id=user_id,
                prompt_name=PROMPT_NAME,
                prompt_version=PROMPT_VERSION,
                model=self._model,
                input_tokens=0,
                output_tokens=0,
                latency_ms=latency_ms,
                schema_hit=False,
                retry_count=retry_count,
                ingest_session_id=ingest_session_id,
                error_code=error_code,
            )
        )


def _load_prompt() -> str:
    return (
        Path(__file__).resolve().parents[1]
        / "prompts"
        / "classify_mistake_v1.md"
    ).read_text(encoding="utf-8")


def _strip_markdown_fence(content: str) -> str:
    stripped = content.strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.DOTALL)
    return match.group(1).strip() if match else stripped


def _message_content(payload: object) -> str:
    if not isinstance(payload, dict):
        return ""
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    return content if isinstance(content, str) else ""


def _token_count(payload: object, key: str) -> int:
    usage = payload.get("usage") if isinstance(payload, dict) else None
    if not isinstance(usage, dict):
        return 0
    value = usage.get(key, 0)
    return value if isinstance(value, int) else 0


def _elapsed_ms(started: float) -> int:
    return max(0, round((time.perf_counter() - started) * 1000))
