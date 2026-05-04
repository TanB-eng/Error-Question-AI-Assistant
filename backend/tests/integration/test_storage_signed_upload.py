from __future__ import annotations

import httpx
import pytest

from app.core.settings import Settings
from app.schemas.uploads import UploadScene, UploadSignRequest
from app.services.uploads import (
    SignedDownload,
    SignedUpload,
    StorageGateway,
    SupabaseStorageGateway,
    UploadSigningService,
)


def _settings_or_skip() -> Settings:
    try:
        return Settings()  # type: ignore[call-arg]
    except Exception as exc:
        pytest.skip(f"Supabase .env is not configured: {exc}")


class FakeRoundTripStorageGateway(StorageGateway):
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}

    def ensure_private_bucket(self, bucket: str) -> None:
        return None

    def create_signed_put_url(self, bucket: str, object_key: str, expires_in: int) -> SignedUpload:
        self.objects[(bucket, object_key)] = b"fake-image"
        return SignedUpload(
            signed_url=f"https://storage.local/put/{bucket}/{object_key}",
            object_key=object_key,
            bucket=bucket,
            expires_in=expires_in,
        )

    def create_signed_get_url(
        self, bucket: str, object_key: str, expires_in: int
    ) -> SignedDownload:
        assert (bucket, object_key) in self.objects
        return SignedDownload(
            signed_url=f"https://storage.local/get/{bucket}/{object_key}",
            object_key=object_key,
            bucket=bucket,
            expires_in=expires_in,
        )


def test_upload_then_signed_get_owner_only() -> None:
    service = UploadSigningService(storage_gateway=FakeRoundTripStorageGateway())
    user_a = "00000000-0000-4000-8000-00000000000a"
    user_b = "00000000-0000-4000-8000-00000000000b"

    upload = service.sign_upload(
        user_id=user_a,
        request=UploadSignRequest(mime_type="image/png", scene=UploadScene.MISTAKE),
    )
    download = service.sign_download(
        user_id=user_a,
        bucket=upload.bucket,
        object_key=upload.object_key,
    )

    assert download.signed_url.startswith("https://storage.local/get/")
    with pytest.raises(PermissionError):
        service.sign_download(user_id=user_b, bucket=upload.bucket, object_key=upload.object_key)


def test_live_signed_put_then_signed_get_owner_only() -> None:
    settings = _settings_or_skip()
    service = UploadSigningService(storage_gateway=SupabaseStorageGateway(settings))
    user_a = "00000000-0000-4000-8000-0000000000aa"
    user_b = "00000000-0000-4000-8000-0000000000bb"

    upload = service.sign_upload(
        user_id=user_a,
        request=UploadSignRequest(mime_type="image/png", scene=UploadScene.MISTAKE),
    )

    with httpx.Client(timeout=30.0) as client:
        uploaded = client.put(
            upload.signed_url,
            content=b"fake-image",
            headers={"Content-Type": "image/png"},
        )
        assert uploaded.status_code in {200, 201}

        download = service.sign_download(
            user_id=user_a,
            bucket=upload.bucket,
            object_key=upload.object_key,
        )
        fetched = client.get(download.signed_url)
        assert fetched.status_code == 200
        assert fetched.content == b"fake-image"

    with pytest.raises(PermissionError):
        service.sign_download(user_id=user_b, bucket=upload.bucket, object_key=upload.object_key)
