"""Internal HTTP client with bounded bodies, request signing, and safe errors."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx

from .auth import ServiceRequestSigner
from .models import AssetPointer


class RetryableJobError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class PermanentJobError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(slots=True)
class InternalHttpClient:
    client: httpx.AsyncClient
    signer: ServiceRequestSigner
    platform_api_url: str
    inference_api_url: str
    max_asset_bytes: int

    @staticmethod
    def _classify(response: httpx.Response) -> None:
        if response.status_code < 400:
            return
        if response.status_code in {408, 425, 429} or response.status_code >= 500:
            raise RetryableJobError(f"upstream_http_{response.status_code}")
        raise PermanentJobError(f"upstream_http_{response.status_code}")

    async def _send(self, request: httpx.Request) -> httpx.Response:
        try:
            body = await request.aread()
            request.headers.update(
                self.signer.headers(request.method, str(request.url), body)
            )
            response = await self.client.send(request, stream=True)
        except httpx.TransportError as exc:
            raise RetryableJobError("upstream_transport_error") from exc
        try:
            self._classify(response)
        except (RetryableJobError, PermanentJobError):
            await response.aclose()
            raise
        return response

    async def get_asset(self, asset: AssetPointer) -> bytes:
        url = (
            f"{self.platform_api_url.rstrip('/')}/internal/v2/assets/"
            f"{quote(str(asset.asset_id), safe='')}/content"
        )
        request = self.client.build_request("GET", url)
        response = await self._send(request)
        data = bytearray()
        try:
            content_type = response.headers.get("content-type", "").split(";", 1)[0]
            if content_type != asset.media_type:
                raise PermanentJobError("asset_media_type_mismatch")
            async for chunk in response.aiter_bytes():
                data.extend(chunk)
                if len(data) > min(self.max_asset_bytes, asset.size_bytes):
                    raise PermanentJobError("asset_size_mismatch")
        finally:
            await response.aclose()
        result = bytes(data)
        data.clear()
        if len(result) != asset.size_bytes:
            raise PermanentJobError("asset_size_mismatch")
        if hashlib.sha256(result).hexdigest() != asset.sha256:
            raise PermanentJobError("asset_hash_mismatch")
        return result

    async def post_json(
        self,
        base_url: str,
        path: str,
        payload: dict[str, Any],
        *,
        max_response_bytes: int = 1_000_000,
    ) -> dict[str, Any]:
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        url = f"{base_url.rstrip('/')}{path}"
        request = self.client.build_request(
            "POST",
            url,
            content=body,
            headers={"Content-Type": "application/json"},
        )
        return await self._json_response(request, max_response_bytes)

    async def post_multipart(
        self,
        path: str,
        *,
        data: dict[str, str],
        files: dict[str, tuple[str, bytes, str]],
        max_response_bytes: int = 1_000_000,
    ) -> dict[str, Any]:
        url = f"{self.inference_api_url.rstrip('/')}{path}"
        request = self.client.build_request("POST", url, data=data, files=files)
        return await self._json_response(request, max_response_bytes)

    async def upload_generated_artifact(
        self,
        *,
        job_id: str,
        purpose: str,
        filename: str,
        media_type: str,
        data: bytes,
        sha256: str,
        manifest: dict[str, Any],
    ) -> dict[str, Any]:
        """Publish a locally rendered artifact to the core protected asset store."""
        if not data or len(data) > self.max_asset_bytes:
            raise PermanentJobError("generated_artifact_size_invalid")
        if hashlib.sha256(data).hexdigest() != sha256:
            raise PermanentJobError("generated_artifact_hash_mismatch")
        metadata = {
            "jobId": job_id,
            "purpose": purpose,
            "filename": filename,
            "mediaType": media_type,
            "sha256": sha256,
            "sizeBytes": len(data),
            "manifest": manifest,
        }
        url = f"{self.platform_api_url.rstrip('/')}/internal/v2/assets/generated"
        request = self.client.build_request(
            "POST",
            url,
            data={"metadata": json.dumps(metadata, separators=(",", ":"))},
            files={"artifact": (filename, data, media_type)},
        )
        return await self._json_response(request, 1_000_000)

    async def _json_response(
        self, request: httpx.Request, max_response_bytes: int
    ) -> dict[str, Any]:
        response = await self._send(request)
        body = bytearray()
        try:
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body) > max_response_bytes:
                    raise PermanentJobError("upstream_response_too_large")
        finally:
            await response.aclose()
        try:
            value = json.loads(bytes(body))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PermanentJobError("invalid_upstream_json") from exc
        finally:
            body.clear()
        if not isinstance(value, dict):
            raise PermanentJobError("invalid_upstream_json")
        return value
