from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header

from app.core.auth_jwt import JwksCache, JwtExpiredError, JwtValidationError, decode_supabase_jwt
from app.core.settings import Settings, get_settings
from app.errors import ErrorCode, api_error


@dataclass(frozen=True)
class CurrentUser:
    id: str
    access_token: str


@lru_cache
def _cached_jwks_cache(jwks_url: str) -> JwksCache:
    return JwksCache(jwks_url)


def get_jwks_cache(settings: Annotated[Settings, Depends(get_settings)]) -> JwksCache:
    return _cached_jwks_cache(settings.supabase_jwt_jwks_url)


def current_user(
    cache: Annotated[JwksCache, Depends(get_jwks_cache)],
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> CurrentUser:
    if authorization is None or not authorization.startswith("Bearer "):
        raise api_error(401, ErrorCode.AUTH_REQUIRED, "请先登录")

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise api_error(401, ErrorCode.AUTH_REQUIRED, "请先登录")

    try:
        payload = decode_supabase_jwt(token, cache=cache)
    except JwtExpiredError as exc:
        raise api_error(401, ErrorCode.TOKEN_EXPIRED, "登录已过期") from exc
    except JwtValidationError as exc:
        raise api_error(401, ErrorCode.AUTH_REQUIRED, "请先登录") from exc

    user_id = payload.get("sub")
    if not isinstance(user_id, str) or not user_id:
        raise api_error(401, ErrorCode.AUTH_REQUIRED, "请先登录")

    return CurrentUser(id=user_id, access_token=token)
