"""Generate a new Stoma3D Ed25519 response-signing key pair.

Run this locally once per deployment environment. Store the private value only
in the backend secret manager. Pin only the public value in worker and mobile
configuration.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)


def main() -> None:
    private_key = Ed25519PrivateKey.generate()
    private_bytes = private_key.private_bytes(
        Encoding.Raw,
        PrivateFormat.Raw,
        NoEncryption(),
    )
    public_bytes = private_key.public_key().public_bytes(
        Encoding.Raw,
        PublicFormat.Raw,
    )
    key_id = hashlib.sha256(public_bytes).hexdigest()[:16]
    print(
        "STOMA3D_RESPONSE_SIGNING_PRIVATE_KEY_B64="
        + base64.b64encode(private_bytes).decode("ascii")
    )
    print(
        "EXPO_PUBLIC_RESPONSE_SIGNING_PUBLIC_KEY_B64="
        + base64.b64encode(public_bytes).decode("ascii")
    )
    print(
        "STOMA3D_RESPONSE_SIGNING_PUBLIC_KEY_B64="
        + base64.b64encode(public_bytes).decode("ascii")
    )
    print(
        "STOMA3D_WORKER_INFERENCE_RESPONSE_SIGNING_PUBLIC_KEY_B64="
        + base64.b64encode(public_bytes).decode("ascii")
    )
    print("STOMA3D_RESPONSE_SIGNING_KEY_ID=" + key_id)


if __name__ == "__main__":
    main()
