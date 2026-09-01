"""Detached Ed25519 signing for exact JSON response bytes."""

from __future__ import annotations

import base64
import binascii
import hashlib
import os
from dataclasses import dataclass
from typing import Mapping

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

SIGNATURE_CONTEXT = b"stoma3d-response-v1\n"
PRIVATE_KEY_ENV = "STOMA3D_RESPONSE_SIGNING_PRIVATE_KEY_B64"
REQUIRE_SIGNING_ENV = "STOMA3D_REQUIRE_RESPONSE_SIGNING"
KEY_ID_ENV = "STOMA3D_RESPONSE_SIGNING_KEY_ID"


@dataclass(frozen=True, slots=True)
class ResponseSigner:
    private_key: Ed25519PrivateKey
    public_key_bytes: bytes
    key_id: str

    @classmethod
    def from_environment(
        cls, environment: Mapping[str, str] | None = None
    ) -> "ResponseSigner | None":
        env = os.environ if environment is None else environment
        encoded_key = env.get(PRIVATE_KEY_ENV, "").strip()
        require_signing_value = env.get(REQUIRE_SIGNING_ENV, "false").strip().lower()
        if require_signing_value not in {"true", "false"}:
            raise RuntimeError(f"{REQUIRE_SIGNING_ENV} must be exactly true or false.")
        require_signing = require_signing_value == "true"
        if not encoded_key:
            if require_signing:
                raise RuntimeError(
                    f"{PRIVATE_KEY_ENV} is required when {REQUIRE_SIGNING_ENV}=true."
                )
            return None

        try:
            private_key_bytes = base64.b64decode(encoded_key, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise RuntimeError(
                f"{PRIVATE_KEY_ENV} must be valid standard base64."
            ) from exc
        if len(private_key_bytes) != 32:
            raise RuntimeError(
                f"{PRIVATE_KEY_ENV} must decode to a raw 32-byte Ed25519 private key."
            )

        private_key = Ed25519PrivateKey.from_private_bytes(private_key_bytes)
        public_key_bytes = private_key.public_key().public_bytes(
            Encoding.Raw, PublicFormat.Raw
        )
        derived_key_id = hashlib.sha256(public_key_bytes).hexdigest()[:16]
        explicit_key_id = env.get(KEY_ID_ENV, "").strip()
        if explicit_key_id and explicit_key_id != derived_key_id:
            raise RuntimeError(
                f"{KEY_ID_ENV} must equal the derived Ed25519 key id {derived_key_id}."
            )
        return cls(
            private_key=private_key,
            public_key_bytes=public_key_bytes,
            key_id=derived_key_id,
        )

    @staticmethod
    def message(request_id: str, response_body: bytes) -> bytes:
        return SIGNATURE_CONTEXT + request_id.encode("utf-8") + b"\n" + response_body

    def sign(self, request_id: str, response_body: bytes) -> str:
        signature = self.private_key.sign(self.message(request_id, response_body))
        return base64.b64encode(signature).decode("ascii")
