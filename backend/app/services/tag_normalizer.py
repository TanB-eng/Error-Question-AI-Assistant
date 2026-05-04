from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import uuid4

from app.core.supabase import SupabaseRestClient

TagKind = Literal["knowledge_point", "question_type", "error_cause"]

TRAILING_PUNCTUATION = ".,，。;；:：!！?？、"
SYNONYM_RULES = {
    "二次函数顶点式": "顶点式",
    "二次函数(顶点式)": "顶点式",
}


@dataclass(frozen=True)
class TagRecord:
    id: str
    user_id: str
    subject_id: int
    kind: TagKind
    name: str
    normalized_name: str


class TagRepository(Protocol):
    def upsert_tag(
        self,
        *,
        user_id: str,
        subject_id: int,
        kind: TagKind,
        name: str,
        normalized_name: str,
    ) -> TagRecord: ...


class InMemoryTagRepository:
    def __init__(self) -> None:
        self._tags: dict[tuple[str, int, TagKind, str], TagRecord] = {}

    def upsert_tag(
        self,
        *,
        user_id: str,
        subject_id: int,
        kind: TagKind,
        name: str,
        normalized_name: str,
    ) -> TagRecord:
        key = (user_id, subject_id, kind, normalized_name)
        existing = self._tags.get(key)
        if existing is not None:
            return existing
        tag = TagRecord(
            id=str(uuid4()),
            user_id=user_id,
            subject_id=subject_id,
            kind=kind,
            name=name,
            normalized_name=normalized_name,
        )
        self._tags[key] = tag
        return tag


class SupabaseTagRepository:
    def __init__(self, *, client: SupabaseRestClient) -> None:
        self._client = client

    def upsert_tag(
        self,
        *,
        user_id: str,
        subject_id: int,
        kind: TagKind,
        name: str,
        normalized_name: str,
    ) -> TagRecord:
        response = self._client.request(
            "POST",
            "/tags",
            headers={
                "Prefer": "resolution=merge-duplicates,return=representation",
            },
            params={"on_conflict": "user_id,subject_id,kind,normalized_name"},
            json={
                "user_id": user_id,
                "subject_id": subject_id,
                "kind": kind,
                "name": name,
                "normalized_name": normalized_name,
            },
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list) or not payload or not isinstance(payload[0], dict):
            raise RuntimeError("Invalid tag upsert response")
        row = payload[0]
        return TagRecord(
            id=str(row["id"]),
            user_id=str(row["user_id"]),
            subject_id=int(row["subject_id"]),
            kind=kind,
            name=str(row["name"]),
            normalized_name=str(row["normalized_name"]),
        )


class TagNormalizerService:
    def __init__(self, *, repository: TagRepository) -> None:
        self._repository = repository

    def normalize_name(self, name: str) -> str:
        normalized = unicodedata.normalize("NFKC", name)
        normalized = normalized.replace("（", "(").replace("）", ")")
        normalized = re.sub(r"\s+", "", normalized)
        normalized = normalized.strip(TRAILING_PUNCTUATION)
        return SYNONYM_RULES.get(normalized, normalized)

    def upsert_tags(
        self,
        *,
        user_id: str,
        subject_id: int,
        kind: TagKind,
        names: list[str],
    ) -> list[TagRecord]:
        records: list[TagRecord] = []
        seen: set[str] = set()
        for name in names:
            normalized_name = self.normalize_name(name)
            if not normalized_name or normalized_name in seen:
                continue
            seen.add(normalized_name)
            records.append(
                self._repository.upsert_tag(
                    user_id=user_id,
                    subject_id=subject_id,
                    kind=kind,
                    name=name.strip(),
                    normalized_name=normalized_name,
                )
            )
        return records
