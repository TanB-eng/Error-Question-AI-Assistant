from __future__ import annotations

from collections.abc import Iterator
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.auth import get_auth_service
from app.core.settings import Settings
from app.core.wechat import WeChatIdentity
from app.main import app
from app.services.auth import AuthService, SupabaseWechatAuthGateway


class FakeWeChatClient:
    def exchange_code(self, code: str) -> WeChatIdentity:
        return WeChatIdentity(openid=f"test-openid-{code}-{uuid4().hex}")


def _settings_or_skip() -> Settings:
    try:
        return Settings()  # type: ignore[call-arg]
    except Exception as exc:
        pytest.skip(f"Supabase .env is not configured: {exc}")


def _service_headers(settings: Settings) -> dict[str, str]:
    return {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": "application/json",
    }


def _user_headers(settings: Settings, token: str) -> dict[str, str]:
    return {
        "apikey": settings.supabase_anon_key,
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


@pytest.fixture
def live_auth_client() -> Iterator[TestClient]:
    settings = _settings_or_skip()
    app.dependency_overrides[get_auth_service] = lambda: AuthService(
        wechat_client=FakeWeChatClient(),
        supabase_gateway=SupabaseWechatAuthGateway(settings),
    )
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_two_real_users_rls_isolation(live_auth_client: TestClient) -> None:
    settings = _settings_or_skip()
    login_a = live_auth_client.post("/auth/wx-login", json={"code": "a"})
    login_b = live_auth_client.post("/auth/wx-login", json={"code": "b"})
    assert login_a.status_code == 200
    assert login_b.status_code == 200
    token_a = login_a.json()["access_token"]
    token_b = login_b.json()["access_token"]
    user_a = login_a.json()["user_profile"]["id"]
    user_b = login_b.json()["user_profile"]["id"]

    base = settings.supabase_url.rstrip()
    rest = f"{base}/rest/v1"
    with httpx.Client(timeout=30.0) as client:
        rows = _seed_user_rows(client, rest, settings, user_a=user_a, user_b=user_b)

        for table in ["mistakes", "notes", "tags", "ingest_sessions"]:
            own = client.get(
                f"{rest}/{table}",
                headers=_user_headers(settings, token_a),
                params={"id": f"eq.{rows[table]['a']}", "select": "id"},
            )
            other = client.get(
                f"{rest}/{table}",
                headers=_user_headers(settings, token_a),
                params={"id": f"eq.{rows[table]['b']}", "select": "id"},
            )
            b_own = client.get(
                f"{rest}/{table}",
                headers=_user_headers(settings, token_b),
                params={"id": f"eq.{rows[table]['b']}", "select": "id"},
            )
            assert own.status_code == 200
            assert own.json() == [{"id": rows[table]["a"]}]
            assert other.status_code == 200
            assert other.json() == []
            assert b_own.status_code == 200
            assert b_own.json() == [{"id": rows[table]["b"]}]


def _seed_user_rows(
    client: httpx.Client,
    rest: str,
    settings: Settings,
    *,
    user_a: str,
    user_b: str,
) -> dict[str, dict[str, str]]:
    headers = {
        **_service_headers(settings),
        "Prefer": "return=representation",
    }

    def insert(table: str, payload: dict[str, object]) -> str:
        response = client.post(f"{rest}/{table}", headers=headers, json=payload)
        response.raise_for_status()
        body = response.json()
        assert isinstance(body, list)
        return str(body[0]["id"])

    rows: dict[str, dict[str, str]] = {}
    for table, factory in {
        "mistakes": lambda user_id: {
            "user_id": user_id,
            "subject_id": 1,
            "source_type": "photo",
            "object_key": f"mistake/{user_id}/{uuid4().hex}.jpg",
        },
        "notes": lambda user_id: {
            "user_id": user_id,
            "subject_id": 1,
            "source_type": "photo",
            "object_key": f"note/{user_id}/{uuid4().hex}.jpg",
        },
        "tags": lambda user_id: {
            "user_id": user_id,
            "subject_id": 1,
            "kind": "knowledge_point",
            "name": f"测试标签 {uuid4().hex}",
            "normalized_name": f"test-tag-{uuid4().hex}",
        },
        "ingest_sessions": lambda user_id: {
            "user_id": user_id,
            "scene": "mistake",
            "source_type": "photo",
            "mime_type": "image/jpeg",
        },
    }.items():
        rows[table] = {
            "a": insert(table, factory(user_a)),
            "b": insert(table, factory(user_b)),
        }
    return rows
