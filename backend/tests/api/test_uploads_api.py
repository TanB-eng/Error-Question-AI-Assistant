from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.uploads import get_upload_signing_service
from app.deps import CurrentUser, current_user
from app.main import app
from app.schemas.uploads import UploadSignResponse


class FakeUploadSigningService:
    def __init__(self) -> None:
        self.user_ids: list[str] = []

    def sign_upload(self, *, user_id: str, request) -> UploadSignResponse:  # type: ignore[no-untyped-def]
        self.user_ids.append(user_id)
        return UploadSignResponse(
            signed_url="https://storage.local/upload",
            object_key=f"{request.scene.value}/{user_id}/file.jpg",
            bucket="mistakes",
            expires_in=300,
            max_size_bytes=5 * 1024 * 1024,
            max_pdf_pages=None,
        )


def test_upload_sign_requires_jwt() -> None:
    client = TestClient(app)

    response = client.post("/uploads/sign", json={"mime_type": "image/jpeg", "scene": "mistake"})

    assert response.status_code == 401


def test_upload_sign_returns_signed_url_for_current_user() -> None:
    service = FakeUploadSigningService()
    app.dependency_overrides[current_user] = lambda: CurrentUser(
        id="00000000-0000-4000-8000-000000000001",
        access_token="jwt",
    )
    app.dependency_overrides[get_upload_signing_service] = lambda: service
    client = TestClient(app)

    response = client.post("/uploads/sign", json={"mime_type": "image/jpeg", "scene": "mistake"})

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["expires_in"] == 300
    assert response.json()["object_key"].startswith("mistake/00000000-0000-4000-8000-000000000001/")
    assert service.user_ids == ["00000000-0000-4000-8000-000000000001"]
