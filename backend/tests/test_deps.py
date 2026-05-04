from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.deps import CurrentUser, current_user, get_jwks_cache


def test_current_user_rejects_missing_token() -> None:
    app = FastAPI()

    @app.get("/me")
    def me(user: Annotated[CurrentUser, Depends(current_user)]) -> dict[str, str]:
        return {"id": user.id}

    client = TestClient(app)

    response = client.get("/me")

    assert response.status_code == 401
    assert response.json()["detail"]["error"]["code"] == "AUTH_REQUIRED"


def test_current_user_extracts_sub_from_jwks_validated_jwt() -> None:
    app = FastAPI()

    class FakeCache:
        pass

    @app.get("/me")
    def me(user: Annotated[CurrentUser, Depends(current_user)]) -> dict[str, str]:
        return {"id": user.id}

    app.dependency_overrides[get_jwks_cache] = lambda: FakeCache()
    app.dependency_overrides[current_user] = lambda: CurrentUser(
        id="00000000-0000-4000-8000-000000000001",
        access_token="jwt",
    )
    client = TestClient(app)

    response = client.get("/me", headers={"Authorization": "Bearer jwt"})

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json() == {"id": "00000000-0000-4000-8000-000000000001"}
