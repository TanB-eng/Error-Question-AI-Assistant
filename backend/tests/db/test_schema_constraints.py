from __future__ import annotations

from .helpers import compact, read_migration


def test_tags_unique_normalized_name() -> None:
    sql = compact(read_migration("0001_init.sql"))

    assert "create unique index if not exists tags_user_subject_kind_normalized_active_uidx" in sql
    assert "on public.tags (user_id, subject_id, kind, normalized_name)" in sql
    assert "where deleted_at is null" in sql


def test_llm_calls_audit_fields_are_complete() -> None:
    sql = compact(read_migration("0001_init.sql"))
    start = sql.index("create table if not exists public.llm_calls")
    block = sql[start:]

    for field in [
        "prompt_name text not null",
        "prompt_version text not null",
        "model text not null",
        "input_tokens integer not null default 0",
        "output_tokens integer not null default 0",
        "latency_ms integer not null",
        "schema_hit boolean not null",
        "retry_count smallint not null default 0",
    ]:
        assert field in block
