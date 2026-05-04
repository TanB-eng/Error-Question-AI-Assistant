from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx

from app.core.settings import Settings

WECHAT_CODE2SESSION_URL = "https://api.weixin.qq.com/sns/jscode2session"
DEFAULT_WECHAT_TIMEOUT_SECONDS = 30.0


class WeChatExchangeError(RuntimeError):
    """Raised when WeChat code exchange fails."""


@dataclass(frozen=True)
class WeChatIdentity:
    openid: str
    unionid: str | None = None


class WeChatCodeExchanger(Protocol):
    def exchange_code(self, code: str) -> WeChatIdentity: ...


class WeChatClient:
    def __init__(
        self,
        settings: Settings,
        *,
        client: httpx.Client | None = None,
        timeout_seconds: float = DEFAULT_WECHAT_TIMEOUT_SECONDS,
    ) -> None:
        self._settings = settings
        self._client = client if client is not None else httpx.Client()
        self._timeout_seconds = timeout_seconds

    def exchange_code(self, code: str) -> WeChatIdentity:
        response = self._client.get(
            WECHAT_CODE2SESSION_URL,
            params={
                "appid": self._settings.wechat_app_id,
                "secret": self._settings.wechat_app_secret,
                "js_code": code,
                "grant_type": "authorization_code",
            },
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise WeChatExchangeError("Invalid WeChat response")
        if "errcode" in payload:
            raise WeChatExchangeError("WeChat code exchange failed")
        openid = payload.get("openid")
        if not isinstance(openid, str) or not openid:
            raise WeChatExchangeError("WeChat response missing openid")
        unionid = payload.get("unionid")
        return WeChatIdentity(openid=openid, unionid=unionid if isinstance(unionid, str) else None)
