from pathlib import Path

from app.core.settings import Settings


def test_env_example_matches_settings_fields() -> None:
    env_example = Path(__file__).resolve().parents[2] / ".env.example"
    content = env_example.read_text(encoding="utf-8")
    declared = {
        line.split("=", 1)[0]
        for line in content.splitlines()
        if line and not line.startswith("#") and "=" in line
    }
    expected = {
        field.validation_alias or field.alias or name
        for name, field in Settings.model_fields.items()
    }

    assert expected <= declared


def test_env_example_uses_only_placeholders() -> None:
    env_example = Path(__file__).resolve().parents[2] / ".env.example"
    content = env_example.read_text(encoding="utf-8")

    assert "real" not in content.lower()
    assert "your-" in content
