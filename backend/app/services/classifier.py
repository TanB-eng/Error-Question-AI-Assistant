from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from app.errors import ErrorCode
from app.schemas.classify import ClassifyResult
from app.services.llm.deepseek import LLMClassificationError


class MistakeClassifierClient(Protocol):
    def classify_mistake_text(
        self,
        *,
        user_id: str,
        ingest_session_id: str | None,
        ocr_text: str,
    ) -> ClassifyResult: ...


@dataclass(frozen=True)
class ClassificationOutcome:
    status: Literal["ready", "pending_classification"]
    result: ClassifyResult | None
    error_code: ErrorCode | None = None


class ClassifierService:
    def __init__(self, *, deepseek_client: MistakeClassifierClient) -> None:
        self._deepseek_client = deepseek_client

    def classify(
        self,
        *,
        user_id: str,
        ingest_session_id: str | None,
        ocr_text: str,
    ) -> ClassificationOutcome:
        try:
            result = self._deepseek_client.classify_mistake_text(
                user_id=user_id,
                ingest_session_id=ingest_session_id,
                ocr_text=ocr_text,
            )
            return ClassificationOutcome(status="ready", result=result)
        except LLMClassificationError as exc:
            return ClassificationOutcome(
                status="pending_classification",
                result=None,
                error_code=exc.error_code,
            )
