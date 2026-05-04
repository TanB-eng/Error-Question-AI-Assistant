from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS_DIR = REPO_ROOT / "supabase" / "migrations"


def read_migration(name: str) -> str:
    return (MIGRATIONS_DIR / name).read_text(encoding="utf-8").lower()


def compact(sql: str) -> str:
    return " ".join(sql.split())
