from __future__ import annotations

from app.services.auth import AuthService, SupabaseSession, SupabaseUserProfile, WeChatIdentity


class FakeWeChatClient:
    def __init__(self) -> None:
        self.codes: list[str] = []

    def exchange_code(self, code: str) -> WeChatIdentity:
        self.codes.append(code)
        return WeChatIdentity(openid=f"openid-{code}")


class FakeSupabaseAuthGateway:
    def __init__(self) -> None:
        self.bootstrapped_openids: list[str] = []

    def bootstrap_wechat_user(self, identity: WeChatIdentity) -> SupabaseUserProfile:
        self.bootstrapped_openids.append(identity.openid)
        return SupabaseUserProfile(id="00000000-0000-4000-8000-000000000001")

    def issue_session(self, profile: SupabaseUserProfile) -> SupabaseSession:
        return SupabaseSession(
            access_token=f"access-for-{profile.id}",
            refresh_token=f"refresh-for-{profile.id}",
            expires_in=3600,
        )


def test_wx_login_creates_user_with_admin_only_for_bootstrap() -> None:
    wechat = FakeWeChatClient()
    gateway = FakeSupabaseAuthGateway()
    service = AuthService(wechat_client=wechat, supabase_gateway=gateway)

    result = service.login_with_wechat_code("code-a")

    assert wechat.codes == ["code-a"]
    assert gateway.bootstrapped_openids == ["openid-code-a"]
    assert result.access_token == "access-for-00000000-0000-4000-8000-000000000001"
    assert result.user_profile.id == "00000000-0000-4000-8000-000000000001"
