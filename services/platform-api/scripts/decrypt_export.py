"""Decrypt one Stoma3D export without putting a private key on the command line."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
from io import BytesIO
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile

from stoma3d_platform.portable_export import (
    SCHEMA_VERSION,
    decrypt_portable_export,
)

MAX_ENCRYPTED_BYTES = 300_000_000


def _private_key_b64(path: Path) -> str:
    raw = path.read_bytes()
    if len(raw) == 32:
        return base64.b64encode(raw).decode("ascii")
    value = raw.decode("ascii").strip()
    decoded = base64.b64decode(value, validate=True)
    if len(decoded) != 32:
        raise ValueError("The private key must be exactly 32 raw bytes.")
    return value


def _encryption_metadata(path: Path) -> dict[str, str]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(value, dict) and isinstance(value.get("encryption"), dict):
        value = value["encryption"]
    if not isinstance(value, dict):
        raise ValueError("The metadata file has no encryption object.")
    return {str(key): str(item) for key, item in value.items()}


def _validate_zip(data: bytes) -> None:
    try:
        with ZipFile(BytesIO(data)) as archive:
            names = set(archive.namelist())
            for name in names:
                path = PurePosixPath(name)
                if path.is_absolute() or ".." in path.parts:
                    raise ValueError("The decrypted archive contains an unsafe path.")
            if archive.testzip() is not None:
                raise ValueError(
                    "The decrypted archive failed its ZIP integrity check."
                )
            manifest = json.loads(archive.read("portable-manifest.json"))
            if manifest.get("schemaVersion") != SCHEMA_VERSION:
                raise ValueError("The decrypted archive has an unknown schema.")
            for item in manifest.get("includedFiles", []):
                path = item.get("path")
                if path not in names:
                    raise ValueError("A manifest file is missing from the archive.")
                content = archive.read(path)
                if len(content) != item.get("sizeBytes") or (
                    hashlib.sha256(content).hexdigest() != item.get("sha256")
                ):
                    raise ValueError("A manifest file failed integrity verification.")
    except (BadZipFile, KeyError, json.JSONDecodeError) as exc:
        raise ValueError("The decrypted export is not a valid Stoma3D ZIP.") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("encrypted_export", type=Path)
    parser.add_argument("metadata_json", type=Path)
    parser.add_argument("recipient_private_key_file", type=Path)
    parser.add_argument("output_zip", type=Path)
    args = parser.parse_args()
    size = args.encrypted_export.stat().st_size
    if size <= 0 or size > MAX_ENCRYPTED_BYTES:
        raise SystemExit("Encrypted export size is invalid.")
    plaintext = decrypt_portable_export(
        args.encrypted_export.read_bytes(),
        recipient_private_key_b64=_private_key_b64(args.recipient_private_key_file),
        encryption=_encryption_metadata(args.metadata_json),
    )
    _validate_zip(plaintext)
    try:
        with args.output_zip.open("xb") as handle:
            handle.write(plaintext)
    except FileExistsError as exc:
        raise SystemExit("Output already exists; refusing to overwrite it.") from exc
    print(f"Wrote verified portable ZIP: {args.output_zip}")


if __name__ == "__main__":
    main()
