from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from typing import Any, Protocol, cast

import httpx
import jwt

ALLOWED_SUPABASE_ALGORITHMS = ("ES256", "RS256")
DEFAULT_JWKS_TTL_SECONDS = 3600
DEFAULT_JWKS_TIMEOUT_SECONDS = 30.0


class JwksFetchError(RuntimeError):
    """Raised when the Supabase JWKS endpoint cannot provide usable keys."""


class JwtValidationError(RuntimeError):
    """Raised when a Supabase JWT cannot be validated."""


class HttpResponse(Protocol):
    def raise_for_status(self) -> None: ...

    def json(self) -> object: ...


class HttpClient(Protocol):
    def get(self, url: str, *, timeout: float) -> HttpResponse: ...


class JwksCache:
    def __init__(
        self,
        jwks_url: str,
        *,
        client: HttpClient | None = None,
        now: Callable[[], float] = time.time,
        ttl_seconds: int = DEFAULT_JWKS_TTL_SECONDS,
        timeout_seconds: float = DEFAULT_JWKS_TIMEOUT_SECONDS,
    ) -> None:
        self._jwks_url = jwks_url
        self._client = client if client is not None else httpx.Client()
        self._now = now
        self._ttl_seconds = ttl_seconds
        self._timeout_seconds = timeout_seconds
        self._jwks: Mapping[str, object] | None = None
        self._expires_at = 0.0

    def get_jwks(self) -> Mapping[str, object]:
        if self._jwks is None or self._now() >= self._expires_at:
            self._jwks = self._fetch_jwks()
            self._expires_at = self._now() + self._ttl_seconds
        return self._jwks

    def get_key_for_token(self, token: str) -> Mapping[str, object]:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise JwtValidationError("Invalid JWT header") from exc

        kid = header.get("kid")
        if not isinstance(kid, str) or not kid:
            raise JwtValidationError("JWT header does not include a key id")

        for key in _get_jwk_keys(self.get_jwks()):
            if key.get("kid") == kid:
                return key

        raise JwtValidationError("JWT signing key was not found in JWKS")

    def _fetch_jwks(self) -> Mapping[str, object]:
        try:
            response = self._client.get(self._jwks_url, timeout=self._timeout_seconds)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise JwksFetchError("Failed to fetch Supabase JWKS") from exc

        if not isinstance(payload, Mapping):
            raise JwksFetchError("Supabase JWKS response must be a JSON object")
        _get_jwk_keys(payload)
        return cast(Mapping[str, object], payload)


def choose_jwt_algorithms(jwks: Mapping[str, object]) -> list[str]:
    algorithms: list[str] = []
    for key in _get_jwk_keys(jwks):
        alg = key.get("alg")
        if isinstance(alg, str) and alg in ALLOWED_SUPABASE_ALGORITHMS and alg not in algorithms:
            algorithms.append(alg)

    if algorithms:
        return algorithms
    return list(ALLOWED_SUPABASE_ALGORITHMS)


def decode_supabase_jwt(
    token: str,
    *,
    cache: JwksCache,
    audience: str | None = None,
    issuer: str | None = None,
) -> Mapping[str, Any]:
    jwk = cache.get_key_for_token(token)
    algorithms = choose_jwt_algorithms(cache.get_jwks())

    try:
        signing_key = jwt.PyJWK.from_dict(dict(jwk), algorithm=algorithms[0]).key
        payload = jwt.decode(
            token,
            key=signing_key,
            algorithms=algorithms,
            audience=audience,
            issuer=issuer,
            options={"verify_aud": audience is not None},
        )
    except jwt.PyJWTError as exc:
        raise JwtValidationError("JWT validation failed") from exc

    if not isinstance(payload, Mapping):
        raise JwtValidationError("JWT payload must be a JSON object")
    return cast(Mapping[str, Any], payload)


def _get_jwk_keys(jwks: Mapping[str, object]) -> list[Mapping[str, object]]:
    keys = jwks.get("keys")
    if not isinstance(keys, list):
        raise JwksFetchError("Supabase JWKS response must include a keys array")

    parsed_keys: list[Mapping[str, object]] = []
    for key in keys:
        if not isinstance(key, Mapping):
            raise JwksFetchError("Supabase JWKS keys must be JSON objects")
        parsed_keys.append(cast(Mapping[str, object], key))

    return parsed_keys
