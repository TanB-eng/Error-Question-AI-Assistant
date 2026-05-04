from __future__ import annotations

import json

import pytest

from app.core.auth_jwt import JwksCache, JwksFetchError, choose_jwt_algorithms


class FakeClock:
    def __init__(self) -> None:
        self.value = 1_000.0

    def __call__(self) -> float:
        return self.value


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self._payload


class FakeHttpClient:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.calls = 0

    def get(self, url: str, *, timeout: float) -> FakeResponse:
        assert url == "https://example.supabase.co/auth/v1/.well-known/jwks.json"
        assert timeout == 30.0
        self.calls += 1
        return FakeResponse(self.payload)


def test_jwks_cache_reuses_response_until_ttl_expires() -> None:
    clock = FakeClock()
    client = FakeHttpClient({"keys": [{"kid": "kid-1", "kty": "RSA", "alg": "RS256"}]})
    cache = JwksCache(
        "https://example.supabase.co/auth/v1/.well-known/jwks.json",
        client=client,
        now=clock,
        ttl_seconds=3600,
    )

    assert cache.get_jwks() == client.payload
    assert cache.get_jwks() == client.payload
    assert client.calls == 1

    clock.value += 3601

    assert cache.get_jwks() == client.payload
    assert client.calls == 2


@pytest.mark.parametrize(
    ("jwks", "expected"),
    [
        ({"keys": [{"alg": "ES256"}]}, ["ES256"]),
        ({"keys": [{"alg": "RS256"}]}, ["RS256"]),
        ({"keys": [{"alg": "HS256"}, {"alg": "ES256"}]}, ["HS256", "ES256"]),
        ({"keys": [{"kty": "RSA"}]}, ["RS256"]),
    ],
)
def test_choose_jwt_algorithms_uses_jwks_alg_or_kty_fallback(
    jwks: dict[str, object], expected: list[str]
) -> None:
    assert choose_jwt_algorithms(jwks) == expected


def test_jwks_cache_rejects_payload_without_keys() -> None:
    client = FakeHttpClient({"not_keys": []})
    cache = JwksCache(
        "https://example.supabase.co/auth/v1/.well-known/jwks.json",
        client=client,
    )

    with pytest.raises(JwksFetchError):
        cache.get_jwks()


def test_jwks_cache_rejects_non_json_object_keys() -> None:
    client = FakeHttpClient(json.loads('{"keys": "bad"}'))
    cache = JwksCache(
        "https://example.supabase.co/auth/v1/.well-known/jwks.json",
        client=client,
    )

    with pytest.raises(JwksFetchError):
        cache.get_jwks()
