import { ed25519 } from "@noble/curves/ed25519.js";
import { sha256 } from "@noble/hashes/sha2.js";
import { bytesToHex, utf8ToBytes } from "@noble/hashes/utils.js";
import { toByteArray } from "base64-js";

const SIGNATURE_DOMAIN = "stoma3d-response-v1";

export function assertEchoedRequestId(
  expectedRequestId: string,
  echoedRequestId: string | null,
): void {
  if (!echoedRequestId || echoedRequestId !== expectedRequestId) {
    throw new Error(
      "Inference response request ID did not match the client request.",
    );
  }
}

function decodeStandardBase64(value: string, label: string): Uint8Array {
  const normalized = value.trim();
  if (
    normalized.length === 0 ||
    normalized.length % 4 !== 0 ||
    !/^[A-Za-z0-9+/]+={0,2}$/.test(normalized)
  ) {
    throw new Error(`${label} is not valid standard base64.`);
  }
  try {
    return toByteArray(normalized);
  } catch {
    throw new Error(`${label} is not valid standard base64.`);
  }
}

export function responseSigningMessage(
  requestId: string,
  rawResponseBody: string,
): Uint8Array {
  return utf8ToBytes(`${SIGNATURE_DOMAIN}\n${requestId}\n${rawResponseBody}`);
}

export function verifyResponseSignature(input: {
  publicKeyBase64: string;
  signatureBase64: string;
  keyId: string;
  requestId: string;
  rawResponseBody: string;
}): void {
  const publicKey = decodeStandardBase64(
    input.publicKeyBase64,
    "Response signing public key",
  );
  const signature = decodeStandardBase64(
    input.signatureBase64,
    "Response signature",
  );
  if (publicKey.length !== 32) {
    throw new Error("Response signing public key must be 32 bytes.");
  }
  if (signature.length !== 64) {
    throw new Error("Response signature must be 64 bytes.");
  }
  const expectedKeyId = bytesToHex(sha256(publicKey)).slice(0, 16);
  if (input.keyId !== expectedKeyId) {
    throw new Error(
      "Inference response signing key ID did not match the pinned public key.",
    );
  }
  const verified = ed25519.verify(
    signature,
    responseSigningMessage(input.requestId, input.rawResponseBody),
    publicKey,
  );
  if (!verified) {
    throw new Error("Inference response signature verification failed.");
  }
}
