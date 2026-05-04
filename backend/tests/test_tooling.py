import tomllib
from pathlib import Path


def test_pyproject_enables_strict_checks() -> None:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))

    assert data["project"]["requires-python"] == ">=3.11"
    dev_dependencies = data["dependency-groups"]["dev"]
    assert any(dependency.startswith("ruff") for dependency in dev_dependencies)
    assert any(dependency.startswith("mypy") for dependency in dev_dependencies)
    assert data["tool"]["mypy"]["strict"] is True
    assert data["tool"]["ruff"]["line-length"] == 100
