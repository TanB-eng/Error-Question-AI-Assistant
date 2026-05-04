from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.core.settings import Settings

DEFAULT_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class SupabaseRestClient:
    base_url: str
    headers: dict[str, str]
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS

    def request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        url = f"{self.base_url}/{path.lstrip('/')}"
        headers = {**self.headers, **kwargs.pop("headers", {})}
        return httpx.request(
            method,
            url,
            headers=headers,
            timeout=self.timeout_seconds,
            **kwargs,
        )


def create_user_client(settings: Settings, *, access_token: str) -> SupabaseRestClient:
    headers = {
        "apikey": settings.supabase_anon_key,
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    return SupabaseRestClient(base_url=_rest_url(settings.supabase_url), headers=headers)


def create_admin_bootstrap_client(settings: Settings) -> SupabaseRestClient:
    """Create service-role client for auth bootstrap, migration, and admin-only jobs."""
    headers = {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": "application/json",
    }
    return SupabaseRestClient(base_url=_rest_url(settings.supabase_url), headers=headers)


def _rest_url(supabase_url: str) -> str:
    return f"{supabase_url.rstrip('/')}/rest/v1"
