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


def test_gitleaks_self_test_expects_detection_exit_code() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "--exit-code 42" in workflow
    assert "status=$?" in workflow
    assert 'if [ "$status" -ne 42 ]; then' in workflow
    assert '"AKIA" "Q3K7M9N2P5R8T1V6"' in workflow
    assert "AKIAQ3K7M9N2P5R8T1V6" not in workflow
