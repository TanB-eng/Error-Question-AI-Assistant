from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.auth import get_auth_service
from app.main import app
from app.schemas.auth import AuthSessionResponse, UserProfile


class FakeAuthService:
    def login_with_wechat_code(self, code: str) -> AuthSessionResponse:
        assert code == "code-ok"
        return AuthSessionResponse(
            access_token="access.jwt",
            refresh_token="refresh.jwt",
            expires_in=3600,
            user_profile=UserProfile(id="00000000-0000-4000-8000-000000000001"),
        )

    def refresh_session(self, refresh_token: str) -> AuthSessionResponse:
        assert refresh_token == "refresh.jwt"
        return AuthSessionResponse(
            access_token="new-access.jwt",
            refresh_token="new-refresh.jwt",
            expires_in=3600,
            user_profile=UserProfile(id="00000000-0000-4000-8000-000000000001"),
        )


class FailingAuthService:
    def login_with_wechat_code(self, code: str) -> AuthSessionResponse:
        raise RuntimeError("openid secret internal detail")

    def refresh_session(self, refresh_token: str) -> AuthSessionResponse:
        raise RuntimeError("refresh token internal detail")


def test_wx_login_returns_session_tokens() -> None:
    app.dependency_overrides[get_auth_service] = lambda: FakeAuthService()
    client = TestClient(app)

    response = client.post("/auth/wx-login", json={"code": "code-ok"})

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["access_token"] == "access.jwt"
    assert response.json()["refresh_token"] == "refresh.jwt"


def test_wx_login_error_does_not_expose_internal_message() -> None:
    app.dependency_overrides[get_auth_service] = lambda: FailingAuthService()
    client = TestClient(app)

    response = client.post("/auth/wx-login", json={"code": "bad-code"})

    app.dependency_overrides.clear()
    assert response.status_code == 502
    body = response.json()
    assert body["error"]["code"] == "EXTERNAL_SERVICE_ERROR"
    assert "openid" not in body["error"]["message"]
    assert "secret" not in body["error"]["message"].lower()


def test_refresh_returns_new_session_tokens() -> None:
    app.dependency_overrides[get_auth_service] = lambda: FakeAuthService()
    client = TestClient(app)

    response = client.post("/auth/refresh", headers={"Authorization": "Bearer refresh.jwt"})

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["access_token"] == "new-access.jwt"
    assert response.json()["refresh_token"] == "new-refresh.jwt"
