from __future__ import annotations

from pathlib import Path

from app.schemas.classify import ClassifyResult


def test_classify_result_accepts_empty_strings_and_null_difficulty() -> None:
    result = ClassifyResult.model_validate(
        {
            "subject": "",
            "question": "",
            "my_answer": "",
            "correct_answer": "",
            "knowledge_points": [],
            "question_type": "",
            "difficulty": None,
            "error_cause": "",
            "analysis": "",
        }
    )

    assert result.difficulty is None
    assert result.knowledge_points == []


def test_classify_result_out_of_range_difficulty_becomes_null() -> None:
    result = ClassifyResult.model_validate(
        {
            "subject": "数学",
            "question": "题干",
            "my_answer": "",
            "correct_answer": "",
            "knowledge_points": ["顶点式"],
            "question_type": "选择题",
            "difficulty": 9,
            "error_cause": "",
            "analysis": "",
        }
    )

    assert result.difficulty is None


def test_classify_mistake_prompt_is_versioned() -> None:
    prompt = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "services"
        / "prompts"
        / "classify_mistake_v1.md"
    )

    content = prompt.read_text(encoding="utf-8")

    assert "Prompt-Version: classify_mistake_v1" in content
    assert "JSON" in content
