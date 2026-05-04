from __future__ import annotations

from app.core.settings import Settings
from app.core.supabase import create_admin_bootstrap_client, create_user_client


def test_user_client_uses_bearer_jwt() -> None:
    settings = Settings(
        SUPABASE_URL="https://project-ref.supabase.co",
        SUPABASE_ANON_KEY="anon-key",
        SUPABASE_SERVICE_ROLE_KEY="service-role-key",
        SUPABASE_JWT_JWKS_URL="https://project-ref.supabase.co/auth/v1/.well-known/jwks.json",
        WECHAT_APP_ID="wx-app-id",
        WECHAT_APP_SECRET="wx-app-secret",
        DEEPSEEK_API_KEY="deepseek-key",
        TENCENT_SECRET_ID="tencent-id",
        TENCENT_SECRET_KEY="tencent-key",
    )

    client = create_user_client(settings, access_token="user-jwt")

    assert client.base_url == "https://project-ref.supabase.co/rest/v1"
    assert client.headers["apikey"] == "anon-key"
    assert client.headers["Authorization"] == "Bearer user-jwt"


def test_admin_bootstrap_client_uses_service_role_key() -> None:
    settings = Settings(
        SUPABASE_URL="https://project-ref.supabase.co",
        SUPABASE_ANON_KEY="anon-key",
        SUPABASE_SERVICE_ROLE_KEY="service-role-key",
        SUPABASE_JWT_JWKS_URL="https://project-ref.supabase.co/auth/v1/.well-known/jwks.json",
        WECHAT_APP_ID="wx-app-id",
        WECHAT_APP_SECRET="wx-app-secret",
        DEEPSEEK_API_KEY="deepseek-key",
        TENCENT_SECRET_ID="tencent-id",
        TENCENT_SECRET_KEY="tencent-key",
    )

    client = create_admin_bootstrap_client(settings)

    assert client.headers["apikey"] == "service-role-key"
    assert client.headers["Authorization"] == "Bearer service-role-key"
    assert "bootstrap" in create_admin_bootstrap_client.__doc__.lower()
    assert "migration" in create_admin_bootstrap_client.__doc__.lower()
    assert "admin" in create_admin_bootstrap_client.__doc__.lower()
