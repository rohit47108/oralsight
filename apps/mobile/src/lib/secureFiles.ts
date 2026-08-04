import { fromByteArray, toByteArray } from "base64-js";
import * as Crypto from "expo-crypto";
import * as FileSystem from "expo-file-system/legacy";
import * as SecureStore from "expo-secure-store";

import {
  AES_GCM_NONCE_LENGTH,
  openAesGcm,
  sealAesGcm,
} from "@/lib/cryptoContainer";
import {
  createOralSightTempUri,
  ensureOralSightTempDirectory,
  purgeOralSightTemporaryFiles,
  removeFileIfPresent,
} from "@/lib/tempFiles";

const VAULT_KEY_NAME = "oralsight.vault-key.v1";

function recordBinding(binding: string): Uint8Array {
  if (!binding.trim())
    throw new Error("Protected files require a record binding.");
  return new TextEncoder().encode(`oralsight-vault-v2:${binding}`);
}

function vaultDirectory(): string {
  if (!FileSystem.documentDirectory)
    throw new Error("Protected device storage is unavailable.");
  return `${FileSystem.documentDirectory}oralsight-vault/`;
}

async function ensureDirectory(uri: string): Promise<void> {
  const info = await FileSystem.getInfoAsync(uri);
  if (!info.exists)
    await FileSystem.makeDirectoryAsync(uri, { intermediates: true });
}

async function getVaultKey(): Promise<Uint8Array> {
  const stored = await SecureStore.getItemAsync(VAULT_KEY_NAME);
  if (stored) return toByteArray(stored);
  const key = await Crypto.getRandomBytesAsync(32);
  await SecureStore.setItemAsync(VAULT_KEY_NAME, fromByteArray(key), {
    keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
  });
  return key;
}

async function encryptBytes(
  bytes: Uint8Array,
  binding: string,
): Promise<Uint8Array> {
  const key = await getVaultKey();
  const nonce = await Crypto.getRandomBytesAsync(AES_GCM_NONCE_LENGTH);
  return sealAesGcm(key, nonce, bytes, recordBinding(binding));
}

async function decryptBytes(
  packed: Uint8Array,
  binding: string,
): Promise<Uint8Array> {
  const key = await getVaultKey();
  return openAesGcm(key, packed, recordBinding(binding));
}

export async function encryptFile(
  sourceUri: string,
  binding: string,
): Promise<string> {
  await ensureDirectory(vaultDirectory());
  const plainBase64 = await FileSystem.readAsStringAsync(sourceUri, {
    encoding: FileSystem.EncodingType.Base64,
  });
  const encrypted = await encryptBytes(toByteArray(plainBase64), binding);
  const destination = `${vaultDirectory()}${Crypto.randomUUID()}.osv`;
  await FileSystem.writeAsStringAsync(destination, fromByteArray(encrypted), {
    encoding: FileSystem.EncodingType.Base64,
  });
  return destination;
}

export async function decryptFileBase64(
  encryptedUri: string,
  binding: string,
): Promise<string> {
  const encryptedBase64 = await FileSystem.readAsStringAsync(encryptedUri, {
    encoding: FileSystem.EncodingType.Base64,
  });
  return fromByteArray(
    await decryptBytes(toByteArray(encryptedBase64), binding),
  );
}

export async function decryptToTemporaryFile(
  encryptedUri: string,
  extension: "jpg" | "png" | "pdf",
  binding: string,
): Promise<string> {
  const tempKind = extension === "pdf" ? "share" : "preview";
  await ensureOralSightTempDirectory(tempKind);
  const destination = await createOralSightTempUri(tempKind, extension);
  await FileSystem.writeAsStringAsync(
    destination,
    await decryptFileBase64(encryptedUri, binding),
    {
      encoding: FileSystem.EncodingType.Base64,
    },
  );
  return destination;
}

export async function removeTemporaryFile(
  uri: string | null | undefined,
): Promise<void> {
  await removeFileIfPresent(uri);
}

export async function removeProtectedFile(
  uri: string | null | undefined,
): Promise<void> {
  if (!uri) return;
  if (!uri.startsWith(vaultDirectory())) {
    throw new Error("Refusing to delete a file outside the OralSight vault.");
  }
  await removeFileIfPresent(uri);
}

export async function removeUnreferencedProtectedFiles(
  referencedUris: Iterable<string | null>,
): Promise<void> {
  const directory = vaultDirectory();
  const info = await FileSystem.getInfoAsync(directory);
  if (!info.exists) return;
  const referenced = new Set(
    [...referencedUris].filter(
      (uri): uri is string => uri !== null && uri.startsWith(directory),
    ),
  );
  const entries = await FileSystem.readDirectoryAsync(directory);
  await Promise.all(
    entries
      .filter((name) => name.endsWith(".osv"))
      .map((name) => `${directory}${name}`)
      .filter((uri) => !referenced.has(uri))
      .map((uri) => removeFileIfPresent(uri)),
  );
}

export async function deleteProtectedFilesAndRotateKey(): Promise<void> {
  const failures: string[] = [];
  const directory = vaultDirectory();
  try {
    const info = await FileSystem.getInfoAsync(directory);
    if (info.exists)
      await FileSystem.deleteAsync(directory, { idempotent: true });
  } catch {
    failures.push("FILES_DELETE");
  }
  try {
    await purgeOralSightTemporaryFiles();
  } catch {
    failures.push("TEMP_DELETE");
  }
  try {
    await SecureStore.deleteItemAsync(VAULT_KEY_NAME);
  } catch {
    failures.push("KEY_DELETE");
  }
  try {
    await getVaultKey();
  } catch {
    failures.push("KEY_ROTATE");
  }
  if (failures.length > 0) {
    throw new Error(`ORALSIGHT_VAULT_RESET_INCOMPLETE:${failures.join(",")}`);
  }
}
