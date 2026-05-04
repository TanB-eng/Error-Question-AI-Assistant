from __future__ import annotations

from app.schemas.uploads import UploadScene, UploadSignRequest
from app.services.uploads import SignedUpload, StorageGateway, UploadSigningService


class FakeStorageGateway(StorageGateway):
    def __init__(self) -> None:
        self.ensured_buckets: list[tuple[str, bool]] = []
        self.signed: list[tuple[str, str, int]] = []

    def ensure_private_bucket(self, bucket: str) -> None:
        self.ensured_buckets.append((bucket, False))

    def create_signed_put_url(self, bucket: str, object_key: str, expires_in: int) -> SignedUpload:
        self.signed.append((bucket, object_key, expires_in))
        return SignedUpload(
            signed_url=f"https://storage.local/{bucket}/{object_key}?token=upload",
            object_key=object_key,
            bucket=bucket,
            expires_in=expires_in,
        )


def test_signed_object_key_is_namespaced_by_user() -> None:
    gateway = FakeStorageGateway()
    service = UploadSigningService(storage_gateway=gateway)

    result = service.sign_upload(
        user_id="00000000-0000-4000-8000-000000000001",
        request=UploadSignRequest(
            mime_type="image/jpeg",
            scene=UploadScene.MISTAKE,
            filename="photo.jpg",
        ),
    )

    assert result.bucket == "mistakes"
    assert result.object_key.startswith("mistake/00000000-0000-4000-8000-000000000001/")
    assert result.object_key.endswith(".jpg")
    assert result.expires_in <= 300
    assert gateway.ensured_buckets == [("mistakes", False)]
    assert gateway.signed == [("mistakes", result.object_key, 300)]


def test_note_pdf_uses_notes_bucket_and_pdf_limits() -> None:
    gateway = FakeStorageGateway()
    service = UploadSigningService(storage_gateway=gateway)

    result = service.sign_upload(
        user_id="00000000-0000-4000-8000-000000000001",
        request=UploadSignRequest(
            mime_type="application/pdf",
            scene=UploadScene.NOTE,
            filename="paper.pdf",
        ),
    )

    assert result.bucket == "notes"
    assert result.object_key.startswith("note/00000000-0000-4000-8000-000000000001/")
    assert result.object_key.endswith(".pdf")
    assert result.max_size_bytes == 10 * 1024 * 1024
    assert result.max_pdf_pages == 20
