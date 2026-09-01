"""Short-lived HMAC authentication for worker-to-service requests."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True, slots=True)
class ServiceRequestSigner:
    service_id: str
    secret: bytes | None

    def headers(
        self,
        method: str,
        url: str,
        body: bytes = b"",
        *,
        timestamp: int | None = None,
        nonce: str | None = None,
    ) -> dict[str, str]:
        if self.secret is None:
            return {}
        now = int(time.time()) if timestamp is None else timestamp
        request_nonce = secrets.token_hex(16) if nonce is None else nonce
        path = urlsplit(url).path or "/"
        query = urlsplit(url).query
        if query:
            path = f"{path}?{query}"
        body_digest = hashlib.sha256(body).hexdigest()
        canonical = "\n".join(
            [method.upper(), path, str(now), request_nonce, body_digest]
        ).encode()
        signature = hmac.new(self.secret, canonical, hashlib.sha256).hexdigest()
        return {
            "X-Stoma3D-Service": self.service_id,
            "X-Stoma3D-Timestamp": str(now),
            "X-Stoma3D-Nonce": request_nonce,
            "X-Stoma3D-Content-SHA256": body_digest,
            "X-Stoma3D-Signature": signature,
        }
