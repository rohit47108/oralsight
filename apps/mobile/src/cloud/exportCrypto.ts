import { fromByteArray, toByteArray } from "base64-js";
import { gcm } from "@noble/ciphers/aes.js";
import { x25519 } from "@noble/curves/ed25519.js";
import { hkdf } from "@noble/hashes/hkdf.js";
import { sha256 } from "@noble/hashes/sha2.js";
import * as Crypto from "expo-crypto";
import * as FileSystem from "expo-file-system/legacy";
import * as Sharing from "expo-sharing";

import { cloudMetadata, updateCloudMetadata } from "../lib/storage";

import type { DataExportArtifact } from "./contracts";
import { readCloudConfig } from "./config";
import { CloudError } from "./errors";
import { cloudAccessToken } from "./session";

const EXPORT_AAD = new TextEncoder().encode("stoma3d-portable-export-v1");

function hex(value: Uint8Array): string {
  return [...value].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

function exportKeyMetadataName(exportRequestId: string): string {
  return `cloud.export_key.${exportRequestId}`;
}

export async function createDataExportPayload(): Promise<{
  payload: Record<string, unknown>;
  exportRequestId: string;
}> {
  const exportRequestId = Crypto.randomUUID();
  const privateKey = await Crypto.getRandomBytesAsync(32);
  const publicKey = x25519.getPublicKey(privateKey);
  try {
    await updateCloudMetadata({
      [exportKeyMetadataName(exportRequestId)]: fromByteArray(privateKey),
    });
    return {
      exportRequestId,
      payload: {
        kind: "data_export",
        exportRequestId,
        scope: "all_portable_data",
        format: "zip",
        encryption: {
          scheme: "x25519-hkdf-sha256-aes-256-gcm",
          recipientPublicKeyB64: fromByteArray(publicKey),
        },
        includeFiles: true,
        disclaimer: "This result is not a diagnosis.",
      },
    };
  } finally {
    privateKey.fill(0);
    publicKey.fill(0);
  }
}

export async function shareDataExportArtifact(
  artifact: DataExportArtifact,
): Promise<void> {
  const config = readCloudConfig();
  if (!config) throw new Error("Account services are not configured.");
  if (!(await Sharing.isAvailableAsync())) {
    throw new Error("The system share sheet is not available on this device.");
  }
  const keyValues = await cloudMetadata(
    exportKeyMetadataName(artifact.exportRequestId),
  );
  const stored = keyValues[exportKeyMetadataName(artifact.exportRequestId)];
  if (!stored) {
    throw new Error(
      "The export key is not on this device. Create a new export here to open it.",
    );
  }
  const privateKey = toByteArray(stored);
  const token = await cloudAccessToken();
  const response = await fetch(
    `${config.platformBaseUrl}/v2/data-exports/${encodeURIComponent(artifact.artifactId)}/content`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: artifact.mediaType,
        "Cache-Control": "no-store",
      },
      cache: "no-store",
    },
  );
  if (!response.ok) {
    privateKey.fill(0);
    throw new CloudError({
      code: response.status >= 500 ? "server" : "upload_unavailable",
      message: "The account export is not available right now.",
      status: response.status,
      retryable: response.status >= 500,
    });
  }
  const encrypted = new Uint8Array(await response.arrayBuffer());
  if (
    encrypted.length !== artifact.byteSize ||
    hex(sha256(encrypted)) !== artifact.sha256
  ) {
    encrypted.fill(0);
    privateKey.fill(0);
    throw new CloudError({
      code: "integrity",
      message: "The account export failed its checksum check.",
    });
  }
  const ephemeral = toByteArray(artifact.encryption.ephemeralPublicKeyB64);
  const salt = toByteArray(artifact.encryption.saltB64);
  const nonce = toByteArray(artifact.encryption.nonceB64);
  const shared = x25519.getSharedSecret(privateKey, ephemeral);
  const key = hkdf(sha256, shared, salt, EXPORT_AAD, 32);
  let plaintext: Uint8Array;
  try {
    plaintext = gcm(key, nonce, EXPORT_AAD).decrypt(encrypted);
  } catch (cause) {
    throw new CloudError({
      code: "integrity",
      message: "The account export could not be unlocked on this device.",
      cause,
    });
  } finally {
    encrypted.fill(0);
    privateKey.fill(0);
    ephemeral.fill(0);
    shared.fill(0);
    key.fill(0);
  }
  if (!FileSystem.cacheDirectory) {
    plaintext.fill(0);
    throw new Error("Temporary storage is unavailable.");
  }
  const directory = `${FileSystem.cacheDirectory}stoma3d-share/`;
  await FileSystem.makeDirectoryAsync(directory, { intermediates: true }).catch(
    () => undefined,
  );
  const uri = `${directory}stoma3d-export-${artifact.exportRequestId}.zip`;
  try {
    await FileSystem.writeAsStringAsync(uri, fromByteArray(plaintext), {
      encoding: FileSystem.EncodingType.Base64,
    });
    plaintext.fill(0);
    await Sharing.shareAsync(uri, {
      mimeType: "application/zip",
      dialogTitle: "Save Stoma3D account export",
      UTI: "public.zip-archive",
    });
  } finally {
    plaintext.fill(0);
    await FileSystem.deleteAsync(uri, { idempotent: true }).catch(
      () => undefined,
    );
  }
}
