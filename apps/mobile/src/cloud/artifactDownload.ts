import { fromByteArray } from "base64-js";
import { sha256 } from "@noble/hashes/sha2.js";
import * as FileSystem from "expo-file-system/legacy";
import * as Sharing from "expo-sharing";

import type { GeneratedArtifact, ReportArtifact } from "./contracts";
import { readCloudConfig } from "./config";
import { CloudError } from "./errors";
import { cloudAccessToken } from "./session";

function hex(value: Uint8Array): string {
  return [...value].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function downloadAndShare(options: {
  path: string;
  id: string;
  filename: string;
  mediaType: string;
  sha256: string;
  sizeBytes: number;
  dialogTitle: string;
  uti: string;
}): Promise<void> {
  const config = readCloudConfig();
  if (!config) throw new Error("Account services are not configured.");
  if (!(await Sharing.isAvailableAsync())) {
    throw new Error("The system share sheet is not available on this device.");
  }
  const token = await cloudAccessToken();
  const response = await fetch(`${config.platformBaseUrl}${options.path}`, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: options.mediaType,
      "Cache-Control": "no-store",
    },
    cache: "no-store",
  });
  if (!response.ok) {
    throw new CloudError({
      code: response.status >= 500 ? "server" : "upload_unavailable",
      message: "The generated file is not available right now.",
      status: response.status,
      retryable: response.status >= 500,
    });
  }
  const bytes = new Uint8Array(await response.arrayBuffer());
  if (
    bytes.length !== options.sizeBytes ||
    hex(sha256(bytes)) !== options.sha256
  ) {
    bytes.fill(0);
    throw new CloudError({
      code: "integrity",
      message: "The generated file failed its checksum check.",
    });
  }
  if (!FileSystem.cacheDirectory)
    throw new Error("Temporary storage is unavailable.");
  const directory = `${FileSystem.cacheDirectory}stoma3d-share/`;
  await FileSystem.makeDirectoryAsync(directory, { intermediates: true }).catch(
    () => undefined,
  );
  const safeName = options.filename.replace(/[^A-Za-z0-9._-]/g, "_");
  const uri = `${directory}${options.id}-${safeName}`;
  try {
    await FileSystem.writeAsStringAsync(uri, fromByteArray(bytes), {
      encoding: FileSystem.EncodingType.Base64,
    });
    bytes.fill(0);
    await Sharing.shareAsync(uri, {
      mimeType: options.mediaType,
      dialogTitle: options.dialogTitle,
      UTI: options.uti,
    });
  } finally {
    bytes.fill(0);
    await FileSystem.deleteAsync(uri, { idempotent: true }).catch(
      () => undefined,
    );
  }
}

export async function shareGeneratedArtifact(
  artifact: GeneratedArtifact,
): Promise<void> {
  return downloadAndShare({
    path: `/v2/generated-artifacts/${encodeURIComponent(artifact.artifactId)}/content`,
    id: artifact.artifactId,
    filename: artifact.filename,
    mediaType: artifact.mediaType,
    sha256: artifact.sha256,
    sizeBytes: artifact.sizeBytes,
    dialogTitle:
      artifact.purpose === "summary_video"
        ? "Share scan summary video"
        : "Share observation surface",
    uti:
      artifact.mediaType === "video/mp4" ? "public.mpeg-4" : "org.khronos.glb",
  });
}

export async function shareReportArtifact(
  artifact: ReportArtifact,
): Promise<void> {
  if (artifact.format !== "pdf") {
    throw new Error("Only PDF cloud reports can be opened in this app.");
  }
  return downloadAndShare({
    path: `/v2/reports/${encodeURIComponent(artifact.reportArtifactId)}/content`,
    id: artifact.reportArtifactId,
    filename: `stoma3d-report-${artifact.reportArtifactId}.pdf`,
    mediaType: "application/pdf",
    sha256: artifact.sha256,
    sizeBytes: artifact.byteSize,
    dialogTitle: "Save clinician PDF",
    uti: "com.adobe.pdf",
  });
}
