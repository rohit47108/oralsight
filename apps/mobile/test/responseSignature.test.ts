import { ed25519 } from "@noble/curves/ed25519.js";
import { sha256 } from "@noble/hashes/sha2.js";
import { bytesToHex } from "@noble/hashes/utils.js";
import { fromByteArray } from "base64-js";
import { describe, expect, it } from "vitest";

import {
  assertEchoedRequestId,
  responseSigningMessage,
  verifyResponseSignature,
} from "../src/lib/responseSignature";

describe("Ed25519 response verification", () => {
  const privateKey = Uint8Array.from({ length: 32 }, (_, index) => index + 1);
  const publicKey = ed25519.getPublicKey(privateKey);
  const publicKeyBase64 = fromByteArray(publicKey);
  const keyId = bytesToHex(sha256(publicKey)).slice(0, 16);
  const requestId = "request-123";
  const body = '{"status":"ok"}';

  it("verifies the domain-separated request ID and exact body bytes", () => {
    const signature = ed25519.sign(
      responseSigningMessage(requestId, body),
      privateKey,
    );
    expect(() =>
      verifyResponseSignature({
        publicKeyBase64,
        signatureBase64: fromByteArray(signature),
        keyId,
        requestId,
        rawResponseBody: body,
      }),
    ).not.toThrow();
  });

  it("rejects a body or request ID substitution", () => {
    const signature = ed25519.sign(
      responseSigningMessage(requestId, body),
      privateKey,
    );
    expect(() =>
      verifyResponseSignature({
        publicKeyBase64,
        signatureBase64: fromByteArray(signature),
        keyId,
        requestId: "different-request",
        rawResponseBody: body,
      }),
    ).toThrow(/verification/i);
  });

  it("rejects replay under a different echoed request ID", () => {
    expect(() => assertEchoedRequestId(requestId, "different-request")).toThrow(
      /request ID/i,
    );
    expect(() => assertEchoedRequestId(requestId, requestId)).not.toThrow();
  });
});
