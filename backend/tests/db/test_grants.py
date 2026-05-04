from __future__ import annotations

from tests.db.helpers import compact, read_migration


def test_0004_grants_postgrest_roles() -> None:
    sql = compact(read_migration("0004_grants.sql"))

    assert "grant usage on schema public to authenticated, service_role" in sql
    assert "grant select on public.subjects to authenticated" in sql
    assert "grant select, insert, update on public.users to service_role" in sql
    for table in ["mistakes", "notes", "tags", "mistake_tags", "note_tags", "ingest_sessions"]:
        assert f"grant select, insert, update on public.{table} to authenticated" in sql
        assert f"grant select, insert, update, delete on public.{table} to service_role" in sql
