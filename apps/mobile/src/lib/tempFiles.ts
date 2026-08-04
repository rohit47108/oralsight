import * as Crypto from "expo-crypto";
import * as FileSystem from "expo-file-system/legacy";

export type OralSightTempKind = "capture" | "preview" | "share";

function cacheRoot(): string {
  if (!FileSystem.cacheDirectory) {
    throw new Error("Temporary device storage is unavailable.");
  }
  return FileSystem.cacheDirectory;
}

export function oralSightTempDirectory(kind: OralSightTempKind): string {
  return `${cacheRoot()}oralsight-${kind}/`;
}

export async function ensureOralSightTempDirectory(
  kind: OralSightTempKind,
): Promise<string> {
  const directory = oralSightTempDirectory(kind);
  const info = await FileSystem.getInfoAsync(directory);
  if (!info.exists) {
    await FileSystem.makeDirectoryAsync(directory, { intermediates: true });
  }
  return directory;
}

export async function createOralSightTempUri(
  kind: OralSightTempKind,
  extension: "jpg" | "png" | "pdf",
): Promise<string> {
  const directory = await ensureOralSightTempDirectory(kind);
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

export async function purgeOralSightBackgroundTemporaryFiles(): Promise<void> {
  await purgeDirectories([
    ...(["capture", "preview"] as const).map(oralSightTempDirectory),
    `${cacheRoot()}ImagePicker/`,
  ]);
}

export async function purgeOralSightTemporaryFiles(): Promise<void> {
  await purgeDirectories([
    ...(["capture", "preview", "share"] as const).map(oralSightTempDirectory),
    `${cacheRoot()}ImagePicker/`,
  ]);
}
