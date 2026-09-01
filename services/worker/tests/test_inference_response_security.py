from __future__ import annotations

import base64
import hashlib
import json
from uuid import UUID

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from pydantic import ValidationError

from stoma3d_worker.auth import ServiceRequestSigner
from stoma3d_worker.http_client import InternalHttpClient, PermanentJobError
from stoma3d_worker.response_verification import InferenceResponseVerifier
from stoma3d_worker.settings import Settings

PRIVATE_KEY = Ed25519PrivateKey.from_private_bytes(b"\x17" * 32)
PUBLIC_KEY_BYTES = PRIVATE_KEY.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
PUBLIC_KEY_B64 = base64.b64encode(PUBLIC_KEY_BYTES).decode("ascii")


def _client(
    handler,
    *,
    verifier: InferenceResponseVerifier | None,
) -> tuple[InternalHttpClient, httpx.AsyncClient]:
    raw = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return (
        InternalHttpClient(
            client=raw,
            signer=ServiceRequestSigner("stoma3d-worker", b"x" * 32),
            platform_api_url="https://platform.internal",
            inference_api_url="https://inference.internal",
            max_asset_bytes=8_000_000,
            inference_response_verifier=verifier,
        ),
        raw,
    )


def _signed_response(
    request: httpx.Request,
    body: bytes,
    *,
    private_key: Ed25519PrivateKey = PRIVATE_KEY,
    echoed_request_id: str | None = None,
    key_id: str | None = None,
    include_key_id: bool = True,
    include_signature: bool = True,
    cache_control: str | None = "private, no-store",
    signed_body: bytes | None = None,
) -> httpx.Response:
    request_id = request.headers["X-Request-ID"]
    signed_request_id = echoed_request_id or request_id
    signature = private_key.sign(
        b"stoma3d-response-v1\n"
        + signed_request_id.encode("ascii")
        + b"\n"
        + (body if signed_body is None else signed_body)
    )
    headers = {"X-Request-ID": signed_request_id}
    if include_key_id:
        headers["X-Stoma3D-Key-Id"] = key_id or (
            InferenceResponseVerifier.from_standard_base64(PUBLIC_KEY_B64).key_id
        )
    if cache_control is not None:
        headers["Cache-Control"] = cache_control
    if include_signature:
        headers["X-Stoma3D-Signature"] = base64.b64encode(signature).decode("ascii")
    return httpx.Response(200, content=body, headers=headers)


async def _post(
    handler,
    *,
    verifier: InferenceResponseVerifier | None = None,
) -> dict[str, object]:
    internal, raw = _client(
        handler,
        verifier=verifier
        or InferenceResponseVerifier.from_standard_base64(PUBLIC_KEY_B64),
    )
    try:
        return await internal.post_multipart(
            "/v1/analyze",
            data={"metadata": "{}"},
            files={"image": ("capture", b"image", "image/jpeg")},
        )
    finally:
        await raw.aclose()


async def test_valid_signed_inference_response_is_verified_before_use() -> None:
    body = json.dumps({"status": "abstained"}, separators=(",", ":")).encode()

    async def handler(request: httpx.Request) -> httpx.Response:
        request_id = request.headers["X-Request-ID"]
        parsed_request_id = UUID(request_id)
        assert parsed_request_id.version == 4
        assert str(parsed_request_id) == request_id
        assert request.headers["Accept-Encoding"] == "identity"
        return _signed_response(request, body)

    assert await _post(handler) == {"status": "abstained"}


@pytest.mark.parametrize(
    ("case", "error_code"),
    [
        ("forged_body", "inference_response_signature_invalid"),
        ("missing_signature", "inference_response_signature_missing"),
        ("missing_key_id", "inference_response_signature_missing"),
        ("wrong_request_id", "inference_response_request_id_mismatch"),
        ("wrong_key_id", "inference_response_signing_key_mismatch"),
        ("missing_no_store", "inference_response_cache_control_invalid"),
    ],
)
async def test_inference_response_security_failures_are_rejected(
    case: str, error_code: str
) -> None:
    valid_body = b'{"status":"abstained"}'

    async def handler(request: httpx.Request) -> httpx.Response:
        if case == "forged_body":
            return _signed_response(
                request,
                b'{"status":"complete"}',
                signed_body=valid_body,
            )
        if case == "missing_signature":
            return _signed_response(request, valid_body, include_signature=False)
        if case == "missing_key_id":
            return _signed_response(request, valid_body, include_key_id=False)
        if case == "wrong_request_id":
            return _signed_response(
                request,
                valid_body,
                echoed_request_id="00000000-0000-4000-8000-000000000099",
            )
        if case == "wrong_key_id":
            return _signed_response(request, valid_body, key_id="0" * 16)
        return _signed_response(request, valid_body, cache_control=None)

    with pytest.raises(PermanentJobError, match=error_code):
        await _post(handler)


async def test_signature_failure_wins_over_invalid_json_parsing() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return _signed_response(
            request,
            b"not-json",
            signed_body=b'{"valid":true}',
        )

    with pytest.raises(PermanentJobError, match="inference_response_signature_invalid"):
        await _post(handler)


async def test_configured_key_requires_signature_in_loopback_development() -> None:
    settings = Settings(
        environment="development",
        inference_response_signing_public_key_b64=PUBLIC_KEY_B64,
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"status": "abstained"},
            headers={
                "Cache-Control": "no-store",
                "X-Request-ID": request.headers["X-Request-ID"],
            },
        )

    internal, raw = _client(
        handler,
        verifier=settings.inference_response_verifier,
    )
    try:
        with pytest.raises(
            PermanentJobError, match="inference_response_signature_missing"
        ):
            await internal.post_multipart(
                "/v1/compare",
                data={"metadata": "{}"},
                files={
                    "baseline_image": ("baseline", b"one", "image/jpeg"),
                    "current_image": ("current", b"two", "image/jpeg"),
                },
            )
    finally:
        await raw.aclose()


def test_protected_worker_requires_a_valid_pinned_public_key() -> None:
    common = {
        "service_hmac_secret": "x" * 32,
        "redis_url": "rediss://redis.internal:6379/0",
        "platform_api_url": "https://platform.internal",
        "inference_api_url": "https://inference.internal",
    }
    with pytest.raises(ValidationError, match="public key"):
        Settings(environment="production", **common)
    with pytest.raises(ValidationError, match="standard base64"):
        Settings(
            environment="staging",
            inference_response_signing_public_key_b64="not-base64url_",
            **common,
        )

    settings = Settings(
        environment="production",
        inference_response_signing_public_key_b64=PUBLIC_KEY_B64,
        **common,
    )
    assert settings.inference_response_verifier is not None
    assert (
        settings.inference_response_verifier.key_id
        == hashlib.sha256(PUBLIC_KEY_BYTES).hexdigest()[:16]
    )


def test_unsigned_development_is_limited_to_loopback_inference() -> None:
    assert Settings(environment="development").inference_response_verifier is None
    with pytest.raises(ValidationError, match="loopback"):
        Settings(
            environment="development",
            inference_api_url="https://inference.example.org",
        )
