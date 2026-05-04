from __future__ import annotations

from pydantic import ValidationError

from app.schemas.uploads import UploadScene, UploadSignRequest, UploadSignResponse


def test_upload_sign_schema_matches_openapi() -> None:
    request = UploadSignRequest(mime_type="application/pdf", scene=UploadScene.MISTAKE)
    response = UploadSignResponse(
        signed_url="https://project.supabase.co/storage/v1/object/upload/sign/mistakes/key",
        object_key="mistake/00000000-0000-4000-8000-000000000001/file.pdf",
        bucket="mistakes",
        expires_in=300,
        max_size_bytes=10 * 1024 * 1024,
        max_pdf_pages=20,
    )

    assert request.mime_type == "application/pdf"
    assert request.scene == UploadScene.MISTAKE
    assert response.expires_in <= 300
    assert response.max_size_bytes == 10 * 1024 * 1024
    assert response.max_pdf_pages == 20


def test_upload_sign_rejects_unsupported_mime_type() -> None:
    try:
        UploadSignRequest(mime_type="image/gif", scene=UploadScene.NOTE)
    except ValidationError as exc:
        assert "mime_type" in str(exc)
    else:
        raise AssertionError("Unsupported mime_type should fail validation")
