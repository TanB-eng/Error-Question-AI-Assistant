from __future__ import annotations

from typing import Annotated, Protocol

from fastapi import APIRouter, Depends

from app.core.settings import Settings, get_settings
from app.deps import CurrentUser, current_user
from app.schemas.uploads import UploadSignRequest, UploadSignResponse
from app.services.uploads import SupabaseStorageGateway, UploadSigningService

router = APIRouter(prefix="/uploads", tags=["Uploads"])


class UploadSigningServiceProtocol(Protocol):
    def sign_upload(self, *, user_id: str, request: UploadSignRequest) -> UploadSignResponse: ...


def get_upload_signing_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> UploadSigningServiceProtocol:
    return UploadSigningService(storage_gateway=SupabaseStorageGateway(settings))


@router.post("/sign", response_model=UploadSignResponse)
def sign_upload(
    request: UploadSignRequest,
    user: Annotated[CurrentUser, Depends(current_user)],
    service: Annotated[UploadSigningServiceProtocol, Depends(get_upload_signing_service)],
) -> UploadSignResponse:
    return service.sign_upload(user_id=user.id, request=request)
