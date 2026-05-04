from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class ClassifyResult(BaseModel):
    subject: str = ""
    question: str = ""
    my_answer: str = ""
    correct_answer: str = ""
    knowledge_points: list[str] = Field(default_factory=list)
    question_type: str = ""
    difficulty: int | None = None
    error_cause: str = ""
    analysis: str = ""

    @field_validator("difficulty", mode="before")
    @classmethod
    def normalize_difficulty(cls, value: object) -> object:
        if value in (None, ""):
            return None
        if isinstance(value, int) and 1 <= value <= 5:
            return value
        return None
