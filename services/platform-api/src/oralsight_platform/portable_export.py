"""In-memory portable ZIP assembly and recipient-key encryption."""

from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from io import BytesIO
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

DISCLAIMER = "This result is not a diagnosis."
SCHEMA_VERSION = "oralsight.portable-export.v1"
SCHEME = "x25519-hkdf-sha256-aes-256-gcm"
AAD = b"oralsight-portable-export-v1"


@dataclass(slots=True)
class ExportFile:
    path: str
    data: bytearray
    media_type: str
    sha256: str


@dataclass(frozen=True, slots=True)
class EncryptedExport:
    ciphertext: bytes
    sha256: str
    encryption: dict[str, str]


def decrypt_portable_export(
    ciphertext: bytes,
    *,
    recipient_private_key_b64: str,
    encryption: dict[str, str],
) -> bytes:
    """Decrypt an export using the private half of its recipient key pair."""

    if encryption.get("scheme") != SCHEME:
        raise ValueError("unsupported_export_encryption_scheme")
    try:
        private_key = base64.b64decode(recipient_private_key_b64, validate=True)
        ephemeral_public = base64.b64decode(
            encryption["ephemeralPublicKeyB64"], validate=True
        )
        salt = base64.b64decode(encryption["saltB64"], validate=True)
        nonce = base64.b64decode(encryption["nonceB64"], validate=True)
        if len(private_key) != 32 or len(ephemeral_public) != 32:
            raise ValueError
        if len(salt) != 16 or len(nonce) != 12:
            raise ValueError
        recipient = X25519PrivateKey.from_private_bytes(private_key)
        shared_secret = recipient.exchange(
            X25519PublicKey.from_public_bytes(ephemeral_public)
        )
        key = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            info=AAD,
        ).derive(shared_secret)
        return AESGCM(key).decrypt(nonce, ciphertext, AAD)
    except (KeyError, TypeError, ValueError, InvalidTag) as exc:
        raise ValueError("portable_export_decryption_failed") from exc


def _json_default(value: Any):
    if isinstance(value, datetime):
        normalized = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return normalized.astimezone(UTC).isoformat()
    if isinstance(value, Enum):
        return value.value
    raise TypeError(f"Unsupported portable value: {type(value).__name__}")


def _json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        default=_json_default,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _zip_info(path: str) -> ZipInfo:
    value = ZipInfo(path, date_time=(2026, 1, 1, 0, 0, 0))
    value.compress_type = ZIP_DEFLATED
    value.external_attr = 0o600 << 16
    return value


def build_portable_zip(
    *,
    export_request_id: str,
    generated_at: datetime,
    records: dict[str, Any],
    files: list[ExportFile],
    skipped_files: list[dict[str, str]],
) -> bytearray:
    buffer = BytesIO()
    manifest_files: list[dict[str, Any]] = []
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
        archive.writestr(
            _zip_info("README.txt"),
            (
                "OralSight portable data export\n\n"
                f"{DISCLAIMER}\n"
                "The decrypted file is a standard ZIP archive. JSON records use "
                "oralsight.portable-export.v1. Measurements remain approximate unless "
                "their calibration evidence says valid.\n"
            ).encode("utf-8"),
        )
        for name, value in sorted(records.items()):
            archive.writestr(_zip_info(f"records/{name}.json"), _json_bytes(value))
        for item in files:
            archive.writestr(_zip_info(item.path), item.data)
            manifest_files.append(
                {
                    "path": item.path,
                    "mediaType": item.media_type,
                    "sha256": item.sha256,
                    "sizeBytes": len(item.data),
                }
            )
            item.data[:] = b"\x00" * len(item.data)
        manifest = {
            "schemaVersion": SCHEMA_VERSION,
            "exportRequestId": export_request_id,
            "generatedAt": generated_at,
            "disclaimer": DISCLAIMER,
            "recordFiles": [f"records/{name}.json" for name in sorted(records)],
            "includedFiles": manifest_files,
            "skippedFiles": skipped_files,
            "plaintextFormat": "application/zip",
        }
        archive.writestr(_zip_info("portable-manifest.json"), _json_bytes(manifest))
    result = bytearray(buffer.getvalue())
    buffer.close()
    return result


def encrypt_portable_zip(
    plaintext: bytearray, *, recipient_public_key_b64: str
) -> EncryptedExport:
    recipient = X25519PublicKey.from_public_bytes(
        base64.b64decode(recipient_public_key_b64, validate=True)
    )
    ephemeral = X25519PrivateKey.generate()
    shared_secret = ephemeral.exchange(recipient)
    salt = os.urandom(16)
    key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=AAD,
    ).derive(shared_secret)
    nonce = os.urandom(12)
    try:
        ciphertext = AESGCM(key).encrypt(nonce, bytes(plaintext), AAD)
    finally:
        plaintext[:] = b"\x00" * len(plaintext)
        shared_secret = b"\x00" * len(shared_secret)
        key = b"\x00" * len(key)
    ephemeral_public = ephemeral.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    return EncryptedExport(
        ciphertext=ciphertext,
        sha256=hashlib.sha256(ciphertext).hexdigest(),
        encryption={
            "scheme": SCHEME,
            "ephemeralPublicKeyB64": base64.b64encode(ephemeral_public).decode(),
            "saltB64": base64.b64encode(salt).decode(),
            "nonceB64": base64.b64encode(nonce).decode(),
        },
    )
