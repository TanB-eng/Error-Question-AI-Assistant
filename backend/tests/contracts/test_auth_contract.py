from __future__ import annotations

from app.schemas.auth import AuthSessionResponse, UserProfile, WxLoginRequest


def test_wx_login_schema_matches_openapi() -> None:
    request = WxLoginRequest(code="081abc")
    response = AuthSessionResponse(
        access_token="access.jwt",
        refresh_token="refresh.jwt",
        expires_in=3600,
        user_profile=UserProfile(id="00000000-0000-4000-8000-000000000001"),
    )

    assert request.model_dump() == {"code": "081abc"}
    assert response.model_dump()["access_token"] == "access.jwt"
    assert response.model_dump()["refresh_token"] == "refresh.jwt"
    assert response.model_dump()["user_profile"]["id"] == "00000000-0000-4000-8000-000000000001"
