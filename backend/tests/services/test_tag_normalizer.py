from __future__ import annotations

from app.services.tag_normalizer import InMemoryTagRepository, TagNormalizerService


def test_normalize_basic_chinese_variants() -> None:
    service = TagNormalizerService(repository=InMemoryTagRepository())

    assert service.normalize_name(" 二次函数（顶点式）。 ") == "顶点式"
    assert service.normalize_name("二次函数( 顶点式 )") == "顶点式"


def test_five_variants_merge_to_one_user_scoped_tag() -> None:
    repository = InMemoryTagRepository()
    service = TagNormalizerService(repository=repository)
    user_a = "00000000-0000-4000-8000-00000000000a"
    user_b = "00000000-0000-4000-8000-00000000000b"
    variants = [
        "二次函数顶点式",
        "顶点式",
        " 二次函数（顶点式） ",
        "二次函数(顶点式)。",
        "二次函数　顶点式！",
    ]

    user_a_tags = service.upsert_tags(
        user_id=user_a,
        subject_id=1,
        kind="knowledge_point",
        names=variants,
    )
    user_b_tags = service.upsert_tags(
        user_id=user_b,
        subject_id=1,
        kind="knowledge_point",
        names=["顶点式"],
    )

    assert len({tag.id for tag in user_a_tags}) == 1
    assert user_a_tags[0].normalized_name == "顶点式"
    assert user_b_tags[0].normalized_name == "顶点式"
    assert user_b_tags[0].id != user_a_tags[0].id
