import { fromByteArray } from "base64-js";
import * as FileSystem from "expo-file-system/legacy";

import { encryptFile } from "@/lib/secureFiles";
import { createOralSightTempUri, removeFileIfPresent } from "@/lib/tempFiles";
import { useOralSightStore } from "@/store/useOralSightStore";
import type { PersistedAppState } from "@/types";

import { downloadVerifiedAsset } from "./assetTransfer";
import { PlatformClient } from "./client";
import {
  readCloudResourceMappings,
  type CloudResourceMapping,
} from "./productSync";

function validCaptureMapping(
  value: CloudResourceMapping | undefined,
): value is CloudResourceMapping & {
  assetId: string;
  sha256: string;
  byteSize: number;
  mimeType: string;
  uploaded: true;
} {
  return Boolean(
    value?.kind === "capture_view" &&
    value.uploaded === true &&
    value.assetId &&
    value.sha256 &&
    value.byteSize &&
    value.mimeType,
  );
}

export async function materializeRemoteCaptures(options: {
  client: PlatformClient;
  state: PersistedAppState;
}): Promise<{ state: PersistedAppState; downloaded: number }> {
  const mappings = new Map(
    (await readCloudResourceMappings()).map((value) => [value.localId, value]),
  );
  let state = options.state;
  let downloaded = 0;
  for (const capture of state.captures) {
    if (capture.encryptedUri) continue;
    const mapping = mappings.get(capture.id);
    if (!validCaptureMapping(mapping)) continue;
    const ticket = await options.client.requestAssetDownload(mapping.assetId);
    const bytes = await downloadVerifiedAsset({
      ticket,
      expectedSha256: mapping.sha256,
      expectedByteSize: mapping.byteSize,
      expectedMimeType: mapping.mimeType,
    });
    const extension = mapping.mimeType === "image/png" ? "png" : "jpg";
    const temporary = await createOralSightTempUri("capture", extension);
    try {
      await FileSystem.writeAsStringAsync(temporary, fromByteArray(bytes), {
        encoding: FileSystem.EncodingType.Base64,
      });
      const encryptedUri = await encryptFile(
        temporary,
        `capture:${capture.id}`,
      );
      state = {
        ...state,
        captures: state.captures.map((value) =>
          value.id === capture.id ? { ...value, encryptedUri } : value,
        ),
      };
      await useOralSightStore.getState().applyCloudState(state);
      downloaded += 1;
    } finally {
      bytes.fill(0);
      await removeFileIfPresent(temporary);
    }
  }
  return { state, downloaded };
}
