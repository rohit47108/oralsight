import { toByteArray } from "base64-js";
import { sha256 } from "@noble/hashes/sha2.js";
import { Skia } from "@shopify/react-native-skia";

import { decryptFileBase64 } from "@/lib/secureFiles";
import type { CaptureRecord } from "@/types";

import type { AssetUploadTicket } from "./contracts";
import { CloudError } from "./errors";

export interface PreparedCloudAsset {
  bytes: Uint8Array;
  sha256: string;
  byteSize: number;
  widthPx: number;
  heightPx: number;
  mimeType: CaptureRecord["mimeType"];
}

function hex(value: Uint8Array): string {
  return [...value].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

function safeTransferUrl(raw: string): URL {
  const url = new URL(raw);
  const loopback = ["127.0.0.1", "localhost", "[::1]"].includes(url.hostname);
  if (url.protocol !== "https:" && !(url.protocol === "http:" && loopback)) {
    throw new CloudError({
      code: "invalid_response",
      message: "The asset transfer URL is not secure.",
    });
  }
  return url;
}

function safeTransferHeaders(
  headers: Record<string, string>,
): Record<string, string> {
  const forbidden = new Set([
    "authorization",
    "cookie",
    "host",
    "proxy-authorization",
  ]);
  const result: Record<string, string> = {};
  for (const [name, value] of Object.entries(headers)) {
    if (forbidden.has(name.toLowerCase()) || /[\r\n]/.test(name + value)) {
      throw new CloudError({
        code: "invalid_response",
        message: "The asset transfer instructions are invalid.",
      });
    }
    result[name] = value;
  }
  return result;
}

export async function prepareCaptureAsset(
  capture: CaptureRecord,
): Promise<PreparedCloudAsset> {
  if (!capture.encryptedUri) {
    throw new CloudError({
      code: "upload_unavailable",
      message: "This observation is not stored on this device.",
    });
  }
  const bytes = toByteArray(
    await decryptFileBase64(capture.encryptedUri, `capture:${capture.id}`),
  );
  const image = Skia.Image.MakeImageFromEncoded(Skia.Data.fromBytes(bytes));
  if (!image) {
    bytes.fill(0);
    throw new CloudError({
      code: "integrity",
      message: "The protected capture could not be decoded for upload.",
    });
  }
  const prepared = {
    bytes,
    sha256: hex(sha256(bytes)),
    byteSize: bytes.length,
    widthPx: image.width(),
    heightPx: image.height(),
    mimeType: capture.mimeType,
  };
  image.dispose();
  return prepared;
}

export async function uploadPreparedAsset(options: {
  ticket: AssetUploadTicket;
  asset: PreparedCloudAsset;
  fetchImpl?: typeof fetch;
}): Promise<void> {
  if (options.ticket.method !== "PUT") {
    throw new CloudError({
      code: "invalid_response",
      message: "The service returned an invalid upload method.",
    });
  }
  if (Date.parse(options.ticket.expiresAt) <= Date.now() + 5_000) {
    throw new CloudError({
      code: "upload_unavailable",
      message: "The upload permission expired. Request a new one.",
      retryable: true,
    });
  }
  const url = safeTransferUrl(options.ticket.url);
  const headers = safeTransferHeaders(options.ticket.headers);
  headers["Content-Type"] ??= options.asset.mimeType;
  let response: Response;
  try {
    response = await (options.fetchImpl ?? fetch)(url.toString(), {
      method: "PUT",
      headers,
      body: options.asset.bytes as unknown as BodyInit,
    });
  } catch (cause) {
    throw new CloudError({
      code: "offline",
      message: "The protected upload did not finish. It can retry safely.",
      retryable: true,
      cause,
    });
  }
  if (!response.ok) {
    throw new CloudError({
      code: response.status >= 500 ? "server" : "upload_unavailable",
      message: "The protected upload was not accepted. It can retry safely.",
      retryable:
        response.status >= 500 ||
        response.status === 408 ||
        response.status === 429,
      status: response.status,
    });
  }
}

export function clearPreparedAsset(asset: PreparedCloudAsset): void {
  asset.bytes.fill(0);
}

export async function downloadVerifiedAsset(options: {
  ticket: AssetUploadTicket;
  expectedSha256: string;
  expectedByteSize: number;
  expectedMimeType: string;
  fetchImpl?: typeof fetch;
}): Promise<Uint8Array> {
  if (options.ticket.method !== "GET") {
    throw new CloudError({
      code: "invalid_response",
      message: "The service returned an invalid download method.",
    });
  }
  if (
    options.expectedByteSize <= 0 ||
    options.expectedByteSize > 10 * 1024 * 1024
  ) {
    throw new CloudError({
      code: "integrity",
      message: "The cloud asset size is outside the mobile safety limit.",
    });
  }
  const response = await (options.fetchImpl ?? fetch)(
    safeTransferUrl(options.ticket.url).toString(),
    {
      method: "GET",
      headers: safeTransferHeaders(options.ticket.headers),
      cache: "no-store",
    },
  );
  if (!response.ok) {
    throw new CloudError({
      code: response.status >= 500 ? "server" : "upload_unavailable",
      message: "The protected cloud asset could not be downloaded.",
      retryable: response.status >= 500 || response.status === 408,
      status: response.status,
    });
  }
  const contentLength = Number(response.headers.get("content-length") ?? "0");
  if (contentLength && contentLength !== options.expectedByteSize) {
    throw new CloudError({
      code: "integrity",
      message: "The cloud asset length did not match its record.",
    });
  }
  const contentType = response.headers.get("content-type")?.split(";", 1)[0];
  if (contentType && contentType !== options.expectedMimeType) {
    throw new CloudError({
      code: "integrity",
      message: "The cloud asset type did not match its record.",
    });
  }
  const bytes = new Uint8Array(await response.arrayBuffer());
  if (
    bytes.length !== options.expectedByteSize ||
    hex(sha256(bytes)) !== options.expectedSha256
  ) {
    bytes.fill(0);
    throw new CloudError({
      code: "integrity",
      message: "The cloud asset failed its checksum check.",
    });
  }
  return bytes;
}
