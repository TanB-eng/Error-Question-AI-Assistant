from __future__ import annotations

import logging

from fastapi.testclient import TestClient

from app.api.auth import get_auth_service
from app.main import app
from app.schemas.auth import AuthSessionResponse, UserProfile


class RepeatableAuthService:
    def __init__(self) -> None:
        self.calls = 0

    def login_with_wechat_code(self, code: str) -> AuthSessionResponse:
        self.calls += 1
        return AuthSessionResponse(
            access_token=f"access-{self.calls}",
            refresh_token=f"refresh-{self.calls}",
            expires_in=3600,
            user_profile=UserProfile(id="00000000-0000-4000-8000-000000000001"),
        )


def test_wx_login_e2e_with_mock_wechat(caplog) -> None:  # type: ignore[no-untyped-def]
    service = RepeatableAuthService()
    app.dependency_overrides[get_auth_service] = lambda: service
    client = TestClient(app)

    with caplog.at_level(logging.INFO):
        first = client.post("/auth/wx-login", json={"code": "code-a"})
        second = client.post("/auth/wx-login", json={"code": "code-a"})

    app.dependency_overrides.clear()
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["access_token"] == "access-1"
    assert second.json()["refresh_token"] == "refresh-2"
    assert service.calls == 2

    logs = caplog.text.lower()
    for sensitive in ["openid", "appsecret", "access-1", "refresh-1", "access-2", "refresh-2"]:
        assert sensitive not in logs
