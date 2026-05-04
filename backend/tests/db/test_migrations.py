from __future__ import annotations

from .helpers import compact, read_migration


def test_0001_init_schema_applies() -> None:
    sql = read_migration("0001_init.sql")
    compact_sql = compact(sql)

    required_tables = [
        "users",
        "subjects",
        "tags",
        "mistakes",
        "notes",
        "mistake_tags",
        "note_tags",
        "ingest_sessions",
        "llm_calls",
    ]
    for table in required_tables:
        assert f"create table if not exists public.{table}" in compact_sql

    user_owned_tables = [
        "tags",
        "mistakes",
        "notes",
        "mistake_tags",
        "note_tags",
        "ingest_sessions",
        "llm_calls",
    ]
    for table in user_owned_tables:
        start = compact_sql.index(f"create table if not exists public.{table}")
        end = compact_sql.find("create table if not exists", start + 1)
        block = compact_sql[start:] if end == -1 else compact_sql[start:end]
        assert "user_id uuid not null references public.users(id)" in block
        assert "created_at timestamptz not null default now()" in block

    soft_delete_tables = [
        "users",
        "tags",
        "mistakes",
        "notes",
        "mistake_tags",
        "note_tags",
        "ingest_sessions",
    ]
    for table in soft_delete_tables:
        start = compact_sql.index(f"create table if not exists public.{table}")
        end = compact_sql.find("create table if not exists", start + 1)
        block = compact_sql[start:] if end == -1 else compact_sql[start:end]
        assert "deleted_at timestamptz" in block
