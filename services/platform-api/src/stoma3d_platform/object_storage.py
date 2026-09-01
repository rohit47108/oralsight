"""Private object storage with an S3 production backend and local test adapter."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import quote

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError

from .config import ObjectStorageBackend, Settings


class StorageError(RuntimeError):
    """Base storage failure with a log-safe error code."""


class StorageNotFound(StorageError):
    pass


class StorageIntegrityError(StorageError):
    pass


@dataclass(frozen=True, slots=True)
class StoredObject:
    size_bytes: int
    sha256: str
    media_type: str


@dataclass(frozen=True, slots=True)
class TransferIntent:
    method: str
    url: str
    headers: dict[str, str]
    expires_at_epoch: int


class ObjectStorage(Protocol):
    async def ping(self) -> bool: ...

    async def put_bytes(
        self, object_key: str, data: bytes, *, media_type: str, sha256: str
    ) -> StoredObject: ...

    async def get_bytes(self, object_key: str, *, max_bytes: int) -> bytes: ...

    async def stat(self, object_key: str) -> StoredObject: ...

    async def delete(self, object_key: str) -> None: ...

    async def list_prefix(self, prefix: str) -> list[str]: ...

    async def presign_upload(
        self,
        object_key: str,
        *,
        media_type: str,
        sha256: str,
        size_bytes: int,
        lifetime_seconds: int,
    ) -> TransferIntent: ...

    async def presign_download(
        self, object_key: str, *, lifetime_seconds: int
    ) -> TransferIntent: ...

    async def close(self) -> None: ...


def _safe_target(root: Path, object_key: str) -> Path:
    resolved_root = root.resolve()
    target = resolved_root.joinpath(*object_key.split("/")).resolve()
    if not target.is_relative_to(resolved_root):
        raise StorageIntegrityError("invalid_object_key")
    return target


def _atomic_write(target: Path, data: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{os.getpid()}.{time.time_ns()}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


class TransferTokenCodec:
    """Short-lived stateless local-transfer capabilities; tokens are never logged."""

    def __init__(self, secret: bytes) -> None:
        self._secret = secret

    def issue(self, payload: dict[str, object]) -> str:
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        encoded = base64.urlsafe_b64encode(raw).rstrip(b"=")
        signature = hmac.new(self._secret, encoded, hashlib.sha256).digest()
        return f"{encoded.decode()}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode()}"

    def verify(self, token: str, *, operation: str) -> dict[str, object]:
        encoded, separator, raw_signature = token.partition(".")
        if not separator or len(token) > 2048:
            raise StorageIntegrityError("invalid_transfer_token")
        try:
            padding = "=" * (-len(raw_signature) % 4)
            signature = base64.urlsafe_b64decode(raw_signature + padding)
            expected = hmac.new(
                self._secret, encoded.encode("ascii"), hashlib.sha256
            ).digest()
            if not hmac.compare_digest(signature, expected):
                raise ValueError
            payload_padding = "=" * (-len(encoded) % 4)
            payload = json.loads(base64.urlsafe_b64decode(encoded + payload_padding))
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise StorageIntegrityError("invalid_transfer_token") from exc
        if (
            not isinstance(payload, dict)
            or payload.get("op") != operation
            or not isinstance(payload.get("exp"), int)
            or payload["exp"] < int(time.time())
        ):
            raise StorageIntegrityError("invalid_transfer_token")
        return payload


class LocalObjectStorage:
    def __init__(self, settings: Settings) -> None:
        self.root = settings.object_storage_root
        self.base_url = settings.object_storage_public_base_url.rstrip("/")
        secret = settings.share_secret_derivation_key.get_secret_value().encode()
        self.tokens = TransferTokenCodec(secret)

    async def put_bytes(
        self, object_key: str, data: bytes, *, media_type: str, sha256: str
    ) -> StoredObject:
        if hashlib.sha256(data).hexdigest() != sha256:
            raise StorageIntegrityError("object_hash_mismatch")
        target = _safe_target(self.root, object_key)
        await asyncio.to_thread(_atomic_write, target, data)
        metadata = {
            "sha256": sha256,
            "mediaType": media_type,
            "sizeBytes": len(data),
        }
        await asyncio.to_thread(
            _atomic_write,
            target.with_suffix(target.suffix + ".metadata.json"),
            json.dumps(metadata, separators=(",", ":")).encode(),
        )
        return StoredObject(len(data), sha256, media_type)

    async def ping(self) -> bool:
        try:
            await asyncio.to_thread(self.root.mkdir, parents=True, exist_ok=True)
            return self.root.is_dir() and os.access(self.root, os.R_OK | os.W_OK)
        except OSError:
            return False

    async def get_bytes(self, object_key: str, *, max_bytes: int) -> bytes:
        target = _safe_target(self.root, object_key)
        if not target.is_file():
            raise StorageNotFound("object_not_found")
        size = target.stat().st_size
        if size > max_bytes:
            raise StorageIntegrityError("object_too_large")
        return await asyncio.to_thread(target.read_bytes)

    async def stat(self, object_key: str) -> StoredObject:
        target = _safe_target(self.root, object_key)
        metadata_target = target.with_suffix(target.suffix + ".metadata.json")
        if not target.is_file() or not metadata_target.is_file():
            raise StorageNotFound("object_not_found")
        try:
            metadata = json.loads(await asyncio.to_thread(metadata_target.read_text))
            return StoredObject(
                size_bytes=int(metadata["sizeBytes"]),
                sha256=str(metadata["sha256"]),
                media_type=str(metadata["mediaType"]),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise StorageIntegrityError("invalid_object_metadata") from exc

    async def delete(self, object_key: str) -> None:
        target = _safe_target(self.root, object_key)
        await asyncio.to_thread(target.unlink, missing_ok=True)
        await asyncio.to_thread(
            target.with_suffix(target.suffix + ".metadata.json").unlink,
            missing_ok=True,
        )

    async def list_prefix(self, prefix: str) -> list[str]:
        root = _safe_target(self.root, prefix.rstrip("/"))
        if not root.exists():
            return []
        files = await asyncio.to_thread(lambda: list(root.rglob("*")))
        return sorted(
            path.relative_to(self.root).as_posix()
            for path in files
            if path.is_file() and not path.name.endswith(".metadata.json")
        )

    async def presign_upload(
        self,
        object_key: str,
        *,
        media_type: str,
        sha256: str,
        size_bytes: int,
        lifetime_seconds: int,
    ) -> TransferIntent:
        expires = int(time.time()) + lifetime_seconds
        token = self.tokens.issue(
            {
                "op": "put",
                "key": object_key,
                "type": media_type,
                "sha": sha256,
                "size": size_bytes,
                "exp": expires,
            }
        )
        return TransferIntent(
            method="PUT",
            url=f"{self.base_url}/v2/storage/uploads/{quote(token, safe='')}",
            headers={"Content-Type": media_type, "Content-Length": str(size_bytes)},
            expires_at_epoch=expires,
        )

    async def presign_download(
        self, object_key: str, *, lifetime_seconds: int
    ) -> TransferIntent:
        expires = int(time.time()) + lifetime_seconds
        token = self.tokens.issue({"op": "get", "key": object_key, "exp": expires})
        return TransferIntent(
            method="GET",
            url=f"{self.base_url}/v2/storage/downloads/{quote(token, safe='')}",
            headers={},
            expires_at_epoch=expires,
        )

    async def close(self) -> None:
        return None


class S3ObjectStorage:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        kwargs: dict[str, object] = {
            "region_name": settings.object_storage_region,
            "config": BotoConfig(
                signature_version="s3v4",
                connect_timeout=2,
                read_timeout=3,
                retries={"max_attempts": 2, "mode": "standard"},
            ),
        }
        if settings.object_storage_endpoint_url:
            kwargs["endpoint_url"] = settings.object_storage_endpoint_url
        if settings.object_storage_access_key_id:
            kwargs["aws_access_key_id"] = (
                settings.object_storage_access_key_id.get_secret_value()
            )
        if settings.object_storage_secret_access_key:
            kwargs["aws_secret_access_key"] = (
                settings.object_storage_secret_access_key.get_secret_value()
            )
        if settings.object_storage_session_token:
            kwargs["aws_session_token"] = (
                settings.object_storage_session_token.get_secret_value()
            )
        self.client = boto3.client("s3", **kwargs)
        self.bucket = settings.object_storage_bucket

    def _encryption(self) -> dict[str, str]:
        values = {"ServerSideEncryption": self.settings.object_storage_sse}
        if self.settings.object_storage_kms_key_id:
            values["SSEKMSKeyId"] = self.settings.object_storage_kms_key_id
        return values

    @staticmethod
    def _checksum_sha256(sha256: str) -> str:
        """Return the S3 checksum form for a validated hexadecimal digest."""

        try:
            raw = bytes.fromhex(sha256)
        except ValueError as exc:
            raise StorageIntegrityError("invalid_object_hash") from exc
        if len(raw) != hashlib.sha256().digest_size:
            raise StorageIntegrityError("invalid_object_hash")
        return base64.b64encode(raw).decode("ascii")

    @staticmethod
    def _translate(exc: Exception) -> StorageError:
        if isinstance(exc, ClientError):
            code = str(exc.response.get("Error", {}).get("Code", ""))
            if code in {"404", "NoSuchKey", "NotFound"}:
                return StorageNotFound("object_not_found")
        return StorageError("object_storage_unavailable")

    async def put_bytes(
        self, object_key: str, data: bytes, *, media_type: str, sha256: str
    ) -> StoredObject:
        if hashlib.sha256(data).hexdigest() != sha256:
            raise StorageIntegrityError("object_hash_mismatch")
        try:
            await asyncio.to_thread(
                self.client.put_object,
                Bucket=self.bucket,
                Key=object_key,
                Body=data,
                ContentType=media_type,
                Metadata={"sha256": sha256},
                ChecksumSHA256=self._checksum_sha256(sha256),
                **self._encryption(),
            )
        except (BotoCoreError, ClientError) as exc:
            raise self._translate(exc) from exc
        return StoredObject(len(data), sha256, media_type)

    async def ping(self) -> bool:
        try:
            await asyncio.to_thread(self.client.head_bucket, Bucket=self.bucket)
        except (BotoCoreError, ClientError):
            return False
        return True

    async def get_bytes(self, object_key: str, *, max_bytes: int) -> bytes:
        try:
            response = await asyncio.to_thread(
                self.client.get_object, Bucket=self.bucket, Key=object_key
            )
            length = int(response.get("ContentLength", 0))
            if length <= 0 or length > max_bytes:
                response["Body"].close()
                raise StorageIntegrityError("object_size_invalid")
            data = await asyncio.to_thread(response["Body"].read, max_bytes + 1)
            response["Body"].close()
        except StorageError:
            raise
        except (BotoCoreError, ClientError) as exc:
            raise self._translate(exc) from exc
        if len(data) != length:
            raise StorageIntegrityError("object_size_mismatch")
        return data

    async def stat(self, object_key: str) -> StoredObject:
        try:
            response = await asyncio.to_thread(
                self.client.head_object,
                Bucket=self.bucket,
                Key=object_key,
                ChecksumMode="ENABLED",
            )
        except (BotoCoreError, ClientError) as exc:
            raise self._translate(exc) from exc
        metadata = response.get("Metadata") or {}
        sha256 = metadata.get("sha256")
        if not isinstance(sha256, str) or len(sha256) != 64:
            raise StorageIntegrityError("object_hash_metadata_missing")
        checksum = response.get("ChecksumSHA256")
        if not isinstance(checksum, str) or not hmac.compare_digest(
            checksum,
            self._checksum_sha256(sha256),
        ):
            raise StorageIntegrityError("object_checksum_mismatch")
        return StoredObject(
            size_bytes=int(response["ContentLength"]),
            sha256=sha256,
            media_type=str(response.get("ContentType") or "application/octet-stream"),
        )

    async def delete(self, object_key: str) -> None:
        try:
            await asyncio.to_thread(
                self.client.delete_object, Bucket=self.bucket, Key=object_key
            )
        except (BotoCoreError, ClientError) as exc:
            raise self._translate(exc) from exc

    async def list_prefix(self, prefix: str) -> list[str]:
        def _list() -> list[str]:
            paginator = self.client.get_paginator("list_objects_v2")
            keys: list[str] = []
            for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
                for value in page.get("Contents", []):
                    key = value.get("Key")
                    if isinstance(key, str):
                        keys.append(key)
            return sorted(set(keys))

        try:
            return await asyncio.to_thread(_list)
        except (BotoCoreError, ClientError) as exc:
            raise self._translate(exc) from exc

    async def presign_upload(
        self,
        object_key: str,
        *,
        media_type: str,
        sha256: str,
        size_bytes: int,
        lifetime_seconds: int,
    ) -> TransferIntent:
        params = {
            "Bucket": self.bucket,
            "Key": object_key,
            "ContentType": media_type,
            "ContentLength": size_bytes,
            "Metadata": {"sha256": sha256},
            "ChecksumSHA256": self._checksum_sha256(sha256),
            **self._encryption(),
        }
        try:
            url = await asyncio.to_thread(
                self.client.generate_presigned_url,
                "put_object",
                Params=params,
                ExpiresIn=lifetime_seconds,
                HttpMethod="PUT",
            )
        except (BotoCoreError, ClientError) as exc:
            raise self._translate(exc) from exc
        headers = {
            "Content-Type": media_type,
            "Content-Length": str(size_bytes),
            "x-amz-meta-sha256": sha256,
            "x-amz-checksum-sha256": self._checksum_sha256(sha256),
            "x-amz-server-side-encryption": self.settings.object_storage_sse,
        }
        if self.settings.object_storage_kms_key_id:
            headers["x-amz-server-side-encryption-aws-kms-key-id"] = (
                self.settings.object_storage_kms_key_id
            )
        return TransferIntent(
            method="PUT",
            url=url,
            headers=headers,
            expires_at_epoch=int(time.time()) + lifetime_seconds,
        )

    async def presign_download(
        self, object_key: str, *, lifetime_seconds: int
    ) -> TransferIntent:
        try:
            url = await asyncio.to_thread(
                self.client.generate_presigned_url,
                "get_object",
                Params={"Bucket": self.bucket, "Key": object_key},
                ExpiresIn=lifetime_seconds,
                HttpMethod="GET",
            )
        except (BotoCoreError, ClientError) as exc:
            raise self._translate(exc) from exc
        return TransferIntent(
            method="GET",
            url=url,
            headers={},
            expires_at_epoch=int(time.time()) + lifetime_seconds,
        )

    async def close(self) -> None:
        return None


def create_object_storage(settings: Settings) -> ObjectStorage:
    if settings.object_storage_backend is ObjectStorageBackend.S3:
        return S3ObjectStorage(settings)
    return LocalObjectStorage(settings)
