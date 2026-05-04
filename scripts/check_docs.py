from pathlib import Path


def test_quickstart_references_frontend_path() -> None:
    quickstart = Path("specs/001-mvp-mistake-notes/quickstart.md").read_text(encoding="utf-8")
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "frontend/" in quickstart
    assert "frontend/" in readme


def test_docs_mention_required_quality_gates() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    for token in ["ruff", "mypy strict", "pytest", "gitleaks"]:
        assert token in readme
