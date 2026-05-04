from __future__ import annotations

from pydantic import BaseModel, Field


class WxLoginRequest(BaseModel):
    code: str = Field(min_length=1)


class UserProfile(BaseModel):
    id: str
    nickname: str | None = None
    avatar_url: str | None = None


class AuthSessionResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    user_profile: UserProfile
