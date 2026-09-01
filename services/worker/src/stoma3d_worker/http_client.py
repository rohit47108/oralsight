"""Internal HTTP client with bounded bodies, request signing, and safe errors."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote
from uuid import uuid4

import httpx

from .auth import ServiceRequestSigner
from .models import AssetPointer
from .response_verification import (
    InferenceResponseVerificationError,
    InferenceResponseVerifier,
)


class RetryableJobError(Exception):
    def __init__(self, code: str, *, retry_after_seconds: float | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.retry_after_seconds = retry_after_seconds


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
    inference_response_verifier: InferenceResponseVerifier | None = None

    @staticmethod
    def _classify(response: httpx.Response) -> None:
        if response.status_code < 400:
            return
        if response.status_code in {408, 425, 429} or response.status_code >= 500:
            retry_after: float | None = None
            raw_retry_after = response.headers.get("Retry-After")
            if raw_retry_after is not None:
                try:
                    parsed = float(raw_retry_after)
                except ValueError:
                    parsed = 0
                if 0 < parsed <= 86_400:
                    retry_after = parsed
            raise RetryableJobError(
                f"upstream_http_{response.status_code}",
                retry_after_seconds=retry_after,
            )
        raise PermanentJobError(f"upstream_http_{response.status_code}")

    async def _send(
        self, request: httpx.Request, *, classify: bool = True
    ) -> httpx.Response:
        try:
            body = await request.aread()
            request.headers.update(
                self.signer.headers(request.method, str(request.url), body)
            )
            response = await self.client.send(request, stream=True)
        except httpx.TransportError as exc:
            raise RetryableJobError("upstream_transport_error") from exc
        if classify:
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
        request_id = str(uuid4())
        request = self.client.build_request(
            "POST",
            url,
            data=data,
            files=files,
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "identity",
                "X-Request-ID": request_id,
            },
        )
        return await self._inference_json_response(
            request,
            max_response_bytes,
            request_id=request_id,
        )

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

    async def _inference_json_response(
        self,
        request: httpx.Request,
        max_response_bytes: int,
        *,
        request_id: str,
    ) -> dict[str, Any]:
        response = await self._send(request, classify=False)
        body = bytearray()
        try:
            try:
                content_encoding = response.headers.get("Content-Encoding", "")
                if content_encoding.casefold() not in {"", "identity"}:
                    raise PermanentJobError(
                        "inference_response_content_encoding_invalid"
                    )
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > max_response_bytes:
                        raise PermanentJobError("upstream_response_too_large")
            except Exception:
                body.clear()
                raise
        finally:
            await response.aclose()

        raw_body = bytes(body)
        body.clear()
        try:
            self._verify_inference_response(
                response,
                request_id=request_id,
                raw_body=raw_body,
            )
            self._classify(response)
            try:
                value = json.loads(raw_body)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise PermanentJobError("invalid_upstream_json") from exc
            if not isinstance(value, dict):
                raise PermanentJobError("invalid_upstream_json")
            return value
        finally:
            raw_body = b""

    def _verify_inference_response(
        self,
        response: httpx.Response,
        *,
        request_id: str,
        raw_body: bytes,
    ) -> None:
        cache_control = response.headers.get("Cache-Control", "")
        if not any(
            directive.strip().casefold() == "no-store"
            for directive in cache_control.split(",")
        ):
            raise PermanentJobError("inference_response_cache_control_invalid")
        if response.headers.get("X-Request-ID") != request_id:
            raise PermanentJobError("inference_response_request_id_mismatch")

        verifier = self.inference_response_verifier
        if verifier is None:
            return
        key_id = response.headers.get("X-Stoma3D-Key-Id")
        signature = response.headers.get("X-Stoma3D-Signature")
        if not key_id or not signature:
            raise PermanentJobError("inference_response_signature_missing")
        try:
            verifier.verify(
                request_id=request_id,
                raw_response_body=raw_body,
                key_id=key_id,
                signature_base64=signature,
            )
        except InferenceResponseVerificationError as exc:
            raise PermanentJobError(exc.code) from exc
