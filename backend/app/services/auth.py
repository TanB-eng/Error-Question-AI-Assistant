from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from typing import Protocol, cast

import httpx

from app.core.settings import Settings
from app.core.wechat import WeChatCodeExchanger, WeChatIdentity
from app.schemas.auth import AuthSessionResponse, UserProfile


class AuthServiceError(RuntimeError):
    """Raised when login cannot be completed."""


@dataclass(frozen=True)
class SupabaseUserProfile:
    id: str
    nickname: str | None = None
    avatar_url: str | None = None


@dataclass(frozen=True)
class SupabaseSession:
    access_token: str
    refresh_token: str
    expires_in: int


class SupabaseAuthGateway(Protocol):
    def bootstrap_wechat_user(self, identity: WeChatIdentity) -> SupabaseUserProfile: ...

    def issue_session(self, profile: SupabaseUserProfile) -> SupabaseSession: ...

    def refresh_session(
        self, refresh_token: str
    ) -> tuple[SupabaseSession, SupabaseUserProfile]: ...


class AuthService:
    def __init__(
        self,
        *,
        wechat_client: WeChatCodeExchanger,
        supabase_gateway: SupabaseAuthGateway,
    ) -> None:
        self._wechat_client = wechat_client
        self._supabase_gateway = supabase_gateway

    def login_with_wechat_code(self, code: str) -> AuthSessionResponse:
        identity = self._wechat_client.exchange_code(code)
        profile = self._supabase_gateway.bootstrap_wechat_user(identity)
        session = self._supabase_gateway.issue_session(profile)
        return AuthSessionResponse(
            access_token=session.access_token,
            refresh_token=session.refresh_token,
            expires_in=session.expires_in,
            user_profile=UserProfile(
                id=profile.id,
                nickname=profile.nickname,
                avatar_url=profile.avatar_url,
            ),
        )

    def refresh_session(self, refresh_token: str) -> AuthSessionResponse:
        session, profile = self._supabase_gateway.refresh_session(refresh_token)
        return AuthSessionResponse(
            access_token=session.access_token,
            refresh_token=session.refresh_token,
            expires_in=session.expires_in,
            user_profile=UserProfile(
                id=profile.id,
                nickname=profile.nickname,
                avatar_url=profile.avatar_url,
            ),
        )


class SupabaseHttpAuthGateway:
    def __init__(
        self,
        settings: Settings,
        *,
        client: httpx.Client | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._settings = settings
        self._client = client if client is not None else httpx.Client()
        self._timeout_seconds = timeout_seconds

    def bootstrap_wechat_user(self, identity: WeChatIdentity) -> SupabaseUserProfile:
        email = _email_for_openid(identity.openid)
        password = _password_for_openid(identity.openid, self._settings.supabase_service_role_key)
        user_id = self._create_or_reuse_auth_user(email=email, password=password)
        self._upsert_public_user(user_id)
        return SupabaseUserProfile(id=user_id)

    def issue_session(self, profile: SupabaseUserProfile) -> SupabaseSession:
        raise AuthServiceError("Default session issuing requires the original WeChat identity")

    def issue_session_for_identity(self, identity: WeChatIdentity) -> SupabaseSession:
        email = _email_for_openid(identity.openid)
        password = _password_for_openid(identity.openid, self._settings.supabase_service_role_key)
        response = self._client.post(
            f"{self._settings.supabase_url.rstrip('/')}/auth/v1/token?grant_type=password",
            headers={
                "apikey": self._settings.supabase_anon_key,
                "Content-Type": "application/json",
            },
            json={"email": email, "password": password},
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise AuthServiceError("Invalid Supabase session response")
        return SupabaseSession(
            access_token=str(payload["access_token"]),
            refresh_token=str(payload["refresh_token"]),
            expires_in=int(payload.get("expires_in", 3600)),
        )

    def refresh_session(self, refresh_token: str) -> tuple[SupabaseSession, SupabaseUserProfile]:
        response = self._client.post(
            f"{self._settings.supabase_url.rstrip('/')}/auth/v1/token?grant_type=refresh_token",
            headers={
                "apikey": self._settings.supabase_anon_key,
                "Content-Type": "application/json",
            },
            json={"refresh_token": refresh_token},
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise AuthServiceError("Invalid Supabase refresh response")
        user = payload.get("user")
        if not isinstance(user, dict) or not isinstance(user.get("id"), str):
            raise AuthServiceError("Invalid Supabase refresh user")
        return (
            SupabaseSession(
                access_token=str(payload["access_token"]),
                refresh_token=str(payload["refresh_token"]),
                expires_in=int(payload.get("expires_in", 3600)),
            ),
            SupabaseUserProfile(id=cast(str, user["id"])),
        )

    def _create_or_reuse_auth_user(self, *, email: str, password: str) -> str:
        response = self._client.post(
            f"{self._settings.supabase_url.rstrip('/')}/auth/v1/admin/users",
            headers=_service_headers(self._settings),
            json={"email": email, "password": password, "email_confirm": True},
            timeout=self._timeout_seconds,
        )
        if response.status_code == 422:
            return self._lookup_user_id_by_email(email)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("id"), str):
            raise AuthServiceError("Invalid Supabase user response")
        user_id = cast(str, payload["id"])
        return user_id

    def _lookup_user_id_by_email(self, email: str) -> str:
        response = self._client.get(
            f"{self._settings.supabase_url.rstrip('/')}/auth/v1/admin/users",
            headers=_service_headers(self._settings),
            params={"page": 1, "per_page": 1000},
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        users = payload.get("users") if isinstance(payload, dict) else None
        if not isinstance(users, list):
            raise AuthServiceError("Invalid Supabase users response")
        for user in users:
            if (
                isinstance(user, dict)
                and user.get("email") == email
                and isinstance(user.get("id"), str)
            ):
                user_id = cast(str, user["id"])
                return user_id
        raise AuthServiceError("Supabase user was not found")

    def _upsert_public_user(self, user_id: str) -> None:
        response = self._client.post(
            f"{self._settings.supabase_url.rstrip('/')}/rest/v1/users",
            headers={
                **_service_headers(self._settings),
                "Prefer": "resolution=merge-duplicates",
            },
            json={"id": user_id},
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()


class SupabaseWechatAuthGateway(SupabaseHttpAuthGateway):
    def __init__(self, settings: Settings, *, client: httpx.Client | None = None) -> None:
        super().__init__(settings, client=client)
        self._last_identity: WeChatIdentity | None = None

    def bootstrap_wechat_user(self, identity: WeChatIdentity) -> SupabaseUserProfile:
        self._last_identity = identity
        return super().bootstrap_wechat_user(identity)

    def issue_session(self, profile: SupabaseUserProfile) -> SupabaseSession:
        if self._last_identity is None:
            raise AuthServiceError("WeChat identity missing for session issue")
        return self.issue_session_for_identity(self._last_identity)


def _service_headers(settings: Settings) -> dict[str, str]:
    return {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": "application/json",
    }


def _email_for_openid(openid: str) -> str:
    digest = hashlib.sha256(openid.encode("utf-8")).hexdigest()
    return f"wx-{digest}@wechat.local"


def _password_for_openid(openid: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), openid.encode("utf-8"), hashlib.sha256).hexdigest()
