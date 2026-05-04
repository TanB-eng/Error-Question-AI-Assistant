from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = Field(default="local", alias="APP_ENV")
    api_base_url: str = Field(default="http://localhost:8000", alias="API_BASE_URL")

    supabase_url: str = Field(alias="SUPABASE_URL")
    supabase_anon_key: str = Field(alias="SUPABASE_ANON_KEY")
    supabase_service_role_key: str = Field(alias="SUPABASE_SERVICE_ROLE_KEY")
    supabase_jwt_jwks_url: str = Field(alias="SUPABASE_JWT_JWKS_URL")
    supabase_storage_bucket: str = Field(default="user-files", alias="SUPABASE_STORAGE_BUCKET")

    wechat_app_id: str = Field(alias="WECHAT_APP_ID")
    wechat_app_secret: str = Field(alias="WECHAT_APP_SECRET")

    deepseek_api_key: str = Field(alias="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field(default="https://api.deepseek.com", alias="DEEPSEEK_BASE_URL")
    deepseek_model: str = Field(default="deepseek-chat", alias="DEEPSEEK_MODEL")

    ocr_provider: str = Field(default="tencent", alias="OCR_PROVIDER")
    tencent_secret_id: str = Field(alias="TENCENT_SECRET_ID")
    tencent_secret_key: str = Field(alias="TENCENT_SECRET_KEY")
    tencent_region: str = Field(default="ap-guangzhou", alias="TENCENT_REGION")


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
