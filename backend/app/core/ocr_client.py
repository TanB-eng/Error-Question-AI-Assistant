from __future__ import annotations

import base64
from typing import cast

import httpx

from app.core.settings import Settings
from app.services.ocr import MockOCRProvider, OCRInput, OCRProvider

TENCENT_OCR_ENDPOINT = "https://ocr.tencentcloudapi.com/"
OCR_TIMEOUT_SECONDS = 30.0


class TencentOCRProvider(OCRProvider):
    def __init__(
        self,
        settings: Settings,
        *,
        client: httpx.Client | None = None,
        timeout_seconds: float = OCR_TIMEOUT_SECONDS,
    ) -> None:
        self._settings = settings
        self._client = client if client is not None else httpx.Client()
        self._timeout_seconds = timeout_seconds

    def extract_text(self, ocr_input: OCRInput) -> str:
        response = self._client.post(
            TENCENT_OCR_ENDPOINT,
            headers={
                "Content-Type": "application/json",
                "X-TC-Action": "GeneralBasicOCR",
                "X-TC-Region": self._settings.tencent_region,
            },
            json={"ImageBase64": base64.b64encode(ocr_input.content).decode("ascii")},
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            return ""
        response_payload = payload.get("Response")
        if not isinstance(response_payload, dict):
            return ""
        detections = response_payload.get("TextDetections", [])
        if not isinstance(detections, list):
            return ""
        lines = [
            cast(str, item["DetectedText"])
            for item in detections
            if isinstance(item, dict) and isinstance(item.get("DetectedText"), str)
        ]
        return "\n".join(lines)


def get_ocr_provider(settings: Settings) -> OCRProvider:
    if settings.ocr_provider == "mock":
        return MockOCRProvider()
    return TencentOCRProvider(settings)
