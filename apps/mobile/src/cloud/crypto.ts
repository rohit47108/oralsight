import { fromByteArray, toByteArray } from "base64-js";
import { sha256 } from "@noble/hashes/sha2.js";
import * as Crypto from "expo-crypto";
import * as SecureStore from "expo-secure-store";
import { z } from "zod";

import {
  AES_GCM_NONCE_LENGTH,
  openAesGcm,
  sealAesGcm,
} from "@/lib/cryptoContainer";

const KEY_BYTES = 32;
const RECOVERY_PREFIX = "OSK1";

const envelopeSchema = z
  .object({
    version: z.literal(1),
    keyId: z.string().regex(/^[a-f0-9]{16}$/),
    ciphertext: z.string().min(24),
  })
  .strict();

function hex(value: Uint8Array): string {
  return [...value].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

function base64Url(value: Uint8Array): string {
  return fromByteArray(value)
    .replace(/=/g, "")
    .replace(/\+/g, "-")
    .replace(/\//g, "_");
}

function fromBase64Url(value: string): Uint8Array {
  const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
  return toByteArray(
    normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "="),
  );
}

function accountKeyName(accountId: string): string {
  return `stoma3d.cloud.sync-key.v1.${hex(sha256(new TextEncoder().encode(accountId))).slice(0, 32)}`;
}

function keyId(key: Uint8Array): string {
  return hex(sha256(key)).slice(0, 16);
}

function recoveryChecksum(key: Uint8Array): string {
  return hex(sha256(new Uint8Array([...key, 79, 83, 75, 49]))).slice(0, 8);
}

function aad(
  accountId: string,
  entityType: string,
  entityId: string,
): Uint8Array {
  return new TextEncoder().encode(
    `stoma3d-cloud-sync-v1:${accountId}:${entityType}:${entityId}`,
  );
}

export interface CloudKeyMaterial {
  key: Uint8Array;
  keyId: string;
  recoveryCode: string;
  created: boolean;
}

export function formatRecoveryCode(key: Uint8Array): string {
  if (key.length !== KEY_BYTES) throw new Error("A sync key must be 32 bytes.");
  return `${RECOVERY_PREFIX}-${base64Url(key)}-${recoveryChecksum(key)}`;
}

export function parseRecoveryCode(value: string): Uint8Array {
  const normalized = value.trim().replace(/\s+/g, "");
  const parts = normalized.split("-");
  if (parts.length !== 3 || parts[0] !== RECOVERY_PREFIX) {
    throw new Error("This recovery code is not valid.");
  }
  let key: Uint8Array;
  try {
    key = fromBase64Url(parts[1] ?? "");
  } catch {
    throw new Error("This recovery code is not valid.");
  }
  if (key.length !== KEY_BYTES || recoveryChecksum(key) !== parts[2]) {
    throw new Error("This recovery code is not valid.");
  }
  return key;
}

export async function loadOrCreateCloudKey(
  accountId: string,
): Promise<CloudKeyMaterial> {
  const name = accountKeyName(accountId);
  const stored = await SecureStore.getItemAsync(name);
  if (stored) {
    const key = fromBase64Url(stored);
    if (key.length !== KEY_BYTES) {
      throw new Error("The protected cloud sync key is invalid.");
    }
    return {
      key,
      keyId: keyId(key),
      recoveryCode: formatRecoveryCode(key),
      created: false,
    };
  }
  const key = await Crypto.getRandomBytesAsync(KEY_BYTES);
  await SecureStore.setItemAsync(name, base64Url(key), {
    keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
  });
  return {
    key,
    keyId: keyId(key),
    recoveryCode: formatRecoveryCode(key),
    created: true,
  };
}

export async function importCloudRecoveryCode(
  accountId: string,
  recoveryCode: string,
): Promise<CloudKeyMaterial> {
  const key = parseRecoveryCode(recoveryCode);
  await SecureStore.setItemAsync(accountKeyName(accountId), base64Url(key), {
    keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
  });
  return {
    key,
    keyId: keyId(key),
    recoveryCode: formatRecoveryCode(key),
    created: false,
  };
}

export async function deleteCloudSyncKey(accountId: string): Promise<void> {
  await SecureStore.deleteItemAsync(accountKeyName(accountId));
}

export async function encryptCloudEntity(options: {
  accountId: string;
  entityType: string;
  entityId: string;
  payload: unknown;
  key: Uint8Array;
}): Promise<string> {
  const nonce = await Crypto.getRandomBytesAsync(AES_GCM_NONCE_LENGTH);
  const plaintext = new TextEncoder().encode(JSON.stringify(options.payload));
  try {
    const ciphertext = sealAesGcm(
      options.key,
      nonce,
      plaintext,
      aad(options.accountId, options.entityType, options.entityId),
    );
    return JSON.stringify({
      version: 1,
      keyId: keyId(options.key),
      ciphertext: base64Url(ciphertext),
    });
  } finally {
    plaintext.fill(0);
  }
}

export function decryptCloudEntity(options: {
  accountId: string;
  entityType: string;
  entityId: string;
  encryptedPayload: string;
  key: Uint8Array;
}): unknown {
  const envelope = envelopeSchema.parse(JSON.parse(options.encryptedPayload));
  if (envelope.keyId !== keyId(options.key)) {
    throw new Error("This data was protected with a different recovery key.");
  }
  const plaintext = openAesGcm(
    options.key,
    fromBase64Url(envelope.ciphertext),
    aad(options.accountId, options.entityType, options.entityId),
  );
  try {
    return JSON.parse(new TextDecoder().decode(plaintext)) as unknown;
  } finally {
    plaintext.fill(0);
  }
}
