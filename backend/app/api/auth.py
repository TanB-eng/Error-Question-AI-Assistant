from __future__ import annotations

from typing import Annotated, Protocol

from fastapi import APIRouter, Depends, Header

from app.core.settings import Settings, get_settings
from app.core.wechat import WeChatClient
from app.errors import ErrorCode, api_error
from app.schemas.auth import AuthSessionResponse, WxLoginRequest
from app.services.auth import AuthService, SupabaseWechatAuthGateway

router = APIRouter(prefix="/auth", tags=["Auth"])


class AuthServiceProtocol(Protocol):
    def login_with_wechat_code(self, code: str) -> AuthSessionResponse: ...

    def refresh_session(self, refresh_token: str) -> AuthSessionResponse: ...


def get_auth_service(settings: Annotated[Settings, Depends(get_settings)]) -> AuthServiceProtocol:
    return AuthService(
        wechat_client=WeChatClient(settings),
        supabase_gateway=SupabaseWechatAuthGateway(settings),
    )


@router.post("/wx-login", response_model=AuthSessionResponse)
def wx_login(
    request: WxLoginRequest,
    auth_service: Annotated[AuthServiceProtocol, Depends(get_auth_service)],
) -> AuthSessionResponse:
    try:
        return auth_service.login_with_wechat_code(request.code)
    except Exception as exc:
        raise api_error(
            502,
            ErrorCode.EXTERNAL_SERVICE_ERROR,
            "登录服务暂时不可用",
        ) from exc


@router.post("/refresh", response_model=AuthSessionResponse)
def refresh(
    auth_service: Annotated[AuthServiceProtocol, Depends(get_auth_service)],
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> AuthSessionResponse:
    if authorization is None or not authorization.startswith("Bearer "):
        raise api_error(401, ErrorCode.AUTH_REQUIRED, "请先登录")
    refresh_token = authorization.removeprefix("Bearer ").strip()
    if not refresh_token:
        raise api_error(401, ErrorCode.AUTH_REQUIRED, "请先登录")
    try:
        return auth_service.refresh_session(refresh_token)
    except Exception as exc:
        raise api_error(401, ErrorCode.TOKEN_EXPIRED, "登录已过期") from exc
