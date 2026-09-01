import * as Crypto from "expo-crypto";
import * as FileSystem from "expo-file-system/legacy";

export type Stoma3DTempKind = "capture" | "preview" | "share";

function cacheRoot(): string {
  if (!FileSystem.cacheDirectory) {
    throw new Error("Temporary device storage is unavailable.");
  }
  return FileSystem.cacheDirectory;
}

export function stoma3DTempDirectory(kind: Stoma3DTempKind): string {
  return `${cacheRoot()}stoma3d-${kind}/`;
}

export async function ensureStoma3DTempDirectory(
  kind: Stoma3DTempKind,
): Promise<string> {
  const directory = stoma3DTempDirectory(kind);
  const info = await FileSystem.getInfoAsync(directory);
  if (!info.exists) {
    await FileSystem.makeDirectoryAsync(directory, { intermediates: true });
  }
  return directory;
}

export async function createStoma3DTempUri(
  kind: Stoma3DTempKind,
  extension: "jpg" | "png" | "pdf",
): Promise<string> {
  const directory = await ensureStoma3DTempDirectory(kind);
  return `${directory}${Crypto.randomUUID()}.${extension}`;
}

export async function removeFileIfPresent(
  uri: string | null | undefined,
): Promise<void> {
  if (!uri) return;
  const info = await FileSystem.getInfoAsync(uri);
  if (info.exists) {
    await FileSystem.deleteAsync(uri, { idempotent: true });
  }
}

export async function removePickerTemporaryCopy(
  uri: string | null | undefined,
): Promise<void> {
  if (!uri) return;
  const root = cacheRoot();
  if (!uri.startsWith(root)) {
    return;
  }
  await removeFileIfPresent(uri);
}

async function purgeDirectories(directories: string[]): Promise<void> {
  await Promise.all(
    directories.map(async (directory) => {
      const info = await FileSystem.getInfoAsync(directory);
      if (info.exists) {
        await FileSystem.deleteAsync(directory, { idempotent: true });
      }
    }),
  );
}

export async function purgeStoma3DBackgroundTemporaryFiles(): Promise<void> {
  await purgeDirectories([
    ...(["capture", "preview"] as const).map(stoma3DTempDirectory),
    `${cacheRoot()}ImagePicker/`,
  ]);
}

export async function purgeStoma3DTemporaryFiles(): Promise<void> {
  await purgeDirectories([
    ...(["capture", "preview", "share"] as const).map(stoma3DTempDirectory),
    `${cacheRoot()}ImagePicker/`,
  ]);
}
