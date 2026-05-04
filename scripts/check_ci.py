from pathlib import Path


def test_ci_contains_required_jobs() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    required = [
        "uv sync",
        "ruff check",
        "mypy app --strict",
        "pytest",
        "gitleaks",
        "check_no_raw_getenv.py",
    ]

    for token in required:
        assert token in workflow
