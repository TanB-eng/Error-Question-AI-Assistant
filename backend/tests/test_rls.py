from __future__ import annotations

from pathlib import Path

from tests.db.helpers import compact, read_migration

USER_OWNED_TABLES = [
    "mistakes",
    "notes",
    "tags",
    "mistake_tags",
    "note_tags",
    "ingest_sessions",
    "llm_calls",
]


def test_all_business_tables_enable_rls() -> None:
    sql = compact(read_migration("0002_rls.sql"))

    for table in ["users", *USER_OWNED_TABLES]:
        assert f"alter table public.{table} enable row level security" in sql


def test_two_users_cannot_read_each_other_business_rows() -> None:
    sql = compact(read_migration("0002_rls.sql"))

    for table in USER_OWNED_TABLES:
        assert f"create policy {table}_select_own on public.{table}" in sql
        assert "for select using (auth.uid() = user_id)" in sql
        assert f"create policy {table}_insert_own on public.{table}" in sql
        assert "for insert with check (auth.uid() = user_id)" in sql
        assert f"create policy {table}_update_own on public.{table}" in sql
        assert "for update using (auth.uid() = user_id) with check (auth.uid() = user_id)" in sql

    fixtures = Path(__file__).parent / "fixtures" / "supabase_tokens.py"
    assert fixtures.exists()
