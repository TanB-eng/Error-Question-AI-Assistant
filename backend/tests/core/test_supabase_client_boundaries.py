from __future__ import annotations

from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[2] / "app"
SERVICES_DIR = APP_DIR / "services"


def test_services_do_not_use_admin_client() -> None:
    if not SERVICES_DIR.exists():
        return

    offenders: list[str] = []
    for path in SERVICES_DIR.rglob("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        if "service_role" in text or "create_admin_bootstrap_client" in text:
            offenders.append(str(path.relative_to(APP_DIR)))

    assert offenders == []


def test_admin_client_factory_is_not_exported_from_services() -> None:
    if not SERVICES_DIR.exists():
        return

    init_file = SERVICES_DIR / "__init__.py"
    if not init_file.exists():
        return

    text = init_file.read_text(encoding="utf-8")
    assert "create_admin_bootstrap_client" not in text
