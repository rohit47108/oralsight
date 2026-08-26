"""Fail-closed verification for exact inference response bytes."""

from __future__ import annotations

import base64
import binascii
import hashlib
from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

SIGNATURE_CONTEXT = b"oralsight-response-v1\n"


class InferenceResponseVerificationError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _decode_standard_base64(value: str, *, expected_bytes: int) -> bytes:
    normalized = value.strip()
    try:
        decoded = base64.b64decode(normalized, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("value must be valid standard base64") from exc
    if base64.b64encode(decoded).decode("ascii") != normalized:
        raise ValueError("value must use canonical standard base64")
    if len(decoded) != expected_bytes:
        raise ValueError(f"value must decode to exactly {expected_bytes} bytes")
    return decoded


@dataclass(frozen=True, slots=True)
class InferenceResponseVerifier:
    """A verifier pinned to one raw Ed25519 public key."""

    public_key: Ed25519PublicKey
    public_key_bytes: bytes
    key_id: str

    @classmethod
    def from_standard_base64(cls, encoded_public_key: str) -> InferenceResponseVerifier:
        public_key_bytes = _decode_standard_base64(
            encoded_public_key,
            expected_bytes=32,
        )
        return cls(
            public_key=Ed25519PublicKey.from_public_bytes(public_key_bytes),
            public_key_bytes=public_key_bytes,
            key_id=hashlib.sha256(public_key_bytes).hexdigest()[:16],
        )

    @staticmethod
    def message(request_id: str, raw_response_body: bytes) -> bytes:
        return (
            SIGNATURE_CONTEXT + request_id.encode("ascii") + b"\n" + raw_response_body
        )

    def verify(
        self,
        *,
        request_id: str,
        raw_response_body: bytes,
        key_id: str,
        signature_base64: str,
    ) -> None:
        if key_id != self.key_id:
            raise InferenceResponseVerificationError(
                "inference_response_signing_key_mismatch"
            )
        try:
            signature = _decode_standard_base64(
                signature_base64,
                expected_bytes=64,
            )
        except ValueError as exc:
            raise InferenceResponseVerificationError(
                "inference_response_signature_invalid"
            ) from exc
        try:
            self.public_key.verify(
                signature,
                self.message(request_id, raw_response_body),
            )
        except InvalidSignature as exc:
            raise InferenceResponseVerificationError(
                "inference_response_signature_invalid"
            ) from exc
