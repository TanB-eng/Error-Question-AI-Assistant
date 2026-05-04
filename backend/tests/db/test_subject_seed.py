from __future__ import annotations

import re

from .helpers import compact, read_migration


def test_subject_seed_is_idempotent() -> None:
    sql = read_migration("0003_seed_subjects.sql")
    compact_sql = compact(sql)

    assert "insert into public.subjects" in compact_sql
    assert "on conflict (id) do update" in compact_sql
    assert len(re.findall(r"\(\d+,\s*'[a-z_]+',", sql)) == 10

    for code in [
        "math",
        "physics",
        "chemistry",
        "biology",
        "chinese",
        "english",
        "history",
        "geography",
        "politics",
        "specialized",
    ]:
        assert f"'{code}'" in sql
