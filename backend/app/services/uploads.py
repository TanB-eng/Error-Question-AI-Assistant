from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import uuid4

import httpx

from app.core.settings import Settings
from app.schemas.uploads import (
    IMAGE_MAX_SIZE_BYTES,
    PDF_MAX_PAGES,
    PDF_MAX_SIZE_BYTES,
    SIGNED_UPLOAD_TTL_SECONDS,
    UploadScene,
    UploadSignRequest,
    UploadSignResponse,
)


@dataclass(frozen=True)
class SignedUpload:
    signed_url: str
    object_key: str
    bucket: str
    expires_in: int


@dataclass(frozen=True)
class SignedDownload:
    signed_url: str
    object_key: str
    bucket: str
    expires_in: int


class StorageGateway(Protocol):
    def ensure_private_bucket(self, bucket: str) -> None: ...

    def create_signed_put_url(
        self, bucket: str, object_key: str, expires_in: int
    ) -> SignedUpload: ...

    def create_signed_get_url(
        self, bucket: str, object_key: str, expires_in: int
    ) -> SignedDownload: ...


class UploadSigningService:
    def __init__(self, *, storage_gateway: StorageGateway) -> None:
        self._storage_gateway = storage_gateway

    def sign_upload(self, *, user_id: str, request: UploadSignRequest) -> UploadSignResponse:
        bucket = _bucket_for_scene(request.scene)
        object_key = _object_key_for_upload(
            scene=request.scene,
            user_id=user_id,
            mime_type=request.mime_type,
            filename=request.filename,
        )
        self._storage_gateway.ensure_private_bucket(bucket)
        signed = self._storage_gateway.create_signed_put_url(
            bucket,
            object_key,
            SIGNED_UPLOAD_TTL_SECONDS,
        )
        return UploadSignResponse(
            signed_url=signed.signed_url,
            object_key=signed.object_key,
            bucket=signed.bucket,
            expires_in=signed.expires_in,
            max_size_bytes=_max_size_for_mime(request.mime_type),
            max_pdf_pages=PDF_MAX_PAGES if request.mime_type == "application/pdf" else None,
        )

    def sign_download(self, *, user_id: str, bucket: str, object_key: str) -> SignedDownload:
        parts = object_key.split("/")
        if len(parts) < 3 or parts[1] != user_id:
            raise PermissionError("Object is not owned by current user")
        return self._storage_gateway.create_signed_get_url(
            bucket,
            object_key,
            SIGNED_UPLOAD_TTL_SECONDS,
        )


class SupabaseStorageGateway:
    def __init__(
        self,
        settings: Settings,
        *,
        client: httpx.Client | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._settings = settings
        self._client = client if client is not None else httpx.Client()
        self._timeout_seconds = timeout_seconds

    def ensure_private_bucket(self, bucket: str) -> None:
        response = self._client.post(
            f"{self._settings.supabase_url.rstrip('/')}/storage/v1/bucket",
            headers=_service_headers(self._settings),
            json={"id": bucket, "name": bucket, "public": False},
            timeout=self._timeout_seconds,
        )
        if response.status_code in {200, 201, 409}:
            return
        payload = _json_object(response)
        if response.status_code == 400 and payload.get("statusCode") == "409":
            return
        response.raise_for_status()

    def create_signed_put_url(self, bucket: str, object_key: str, expires_in: int) -> SignedUpload:
        response = self._client.post(
            f"{self._settings.supabase_url.rstrip('/')}/storage/v1/object/upload/sign/{bucket}/{object_key}",
            headers=_service_headers(self._settings),
            json={"expiresIn": expires_in, "upsert": False},
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        payload = _json_object(response)
        signed_path = payload.get("signedURL", payload.get("url"))
        if not isinstance(signed_path, str):
            raise RuntimeError("Invalid Supabase signed upload response")
        return SignedUpload(
            signed_url=f"{self._settings.supabase_url.rstrip('/')}/storage/v1{signed_path}",
            object_key=object_key,
            bucket=bucket,
            expires_in=expires_in,
        )

    def create_signed_get_url(
        self, bucket: str, object_key: str, expires_in: int
    ) -> SignedDownload:
        response = self._client.post(
            f"{self._settings.supabase_url.rstrip('/')}/storage/v1/object/sign/{bucket}/{object_key}",
            headers=_service_headers(self._settings),
            json={"expiresIn": expires_in},
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        payload = _json_object(response)
        signed_path = payload.get("signedURL", payload.get("url"))
        if not isinstance(signed_path, str):
            raise RuntimeError("Invalid Supabase signed download response")
        return SignedDownload(
            signed_url=f"{self._settings.supabase_url.rstrip('/')}/storage/v1{signed_path}",
            object_key=object_key,
            bucket=bucket,
            expires_in=expires_in,
        )


def _service_headers(settings: Settings) -> dict[str, str]:
    return {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": "application/json",
    }


def _json_object(response: httpx.Response) -> dict[str, object]:
    payload = response.json()
    if not isinstance(payload, dict):
        return {}
    return payload


def _bucket_for_scene(scene: UploadScene) -> str:
    return "mistakes" if scene == UploadScene.MISTAKE else "notes"


def _object_key_for_upload(
    *,
    scene: UploadScene,
    user_id: str,
    mime_type: str,
    filename: str | None,
) -> str:
    ext = _extension_for_upload(mime_type=mime_type, filename=filename)
    return f"{scene.value}/{user_id}/{uuid4().hex}{ext}"


def _extension_for_upload(*, mime_type: str, filename: str | None) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".pdf"}:
        return suffix
    return {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "application/pdf": ".pdf",
    }[mime_type]


def _max_size_for_mime(mime_type: str) -> int:
    return PDF_MAX_SIZE_BYTES if mime_type == "application/pdf" else IMAGE_MAX_SIZE_BYTES
