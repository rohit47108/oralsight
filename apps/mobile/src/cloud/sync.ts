import * as Crypto from "expo-crypto";
import * as SecureStore from "expo-secure-store";
import { Platform } from "react-native";

import {
  acknowledgeCloudOutbox,
  bindCloudAccount,
  cloudAccountRebindPending,
  cloudMetadata,
  confirmCloudAccountRebind,
  loadPersistedState,
  markCloudOutboxAttempt,
  readCloudOutbox,
  stageCloudOutbox,
  updateCloudMetadata,
  type CloudOutboxInsert,
} from "@/lib/storage";
import { useOralSightStore } from "@/store/useOralSightStore";
import type { PersistedAppState } from "@/types";

import { PlatformClient, newIdempotencyKey } from "./client";
import {
  syncOperationInputSchema,
  type MeResponse,
  type SyncOperationInput,
} from "./contracts";
import {
  decryptCloudEntity,
  encryptCloudEntity,
  loadOrCreateCloudKey,
} from "./crypto";
import {
  buildSyncEntities,
  mergeRemoteChanges,
  syncEntityFingerprint,
  syncEntityMetadataKey,
  type CloudEntityEnvelope,
  type DecryptedSyncChange,
} from "./syncModel";
import {
  cloudMappingKey,
  readCloudResourceMappings,
  syncProductResources,
  type CloudResourceMapping,
} from "./productSync";
import { materializeRemoteCaptures } from "./materialize";
import { requireActiveProductConsent } from "./consent";

const INSTALLATION_ID_KEY = "oralsight.cloud.installation-id.v1";
const DEVICE_ID_KEY_PREFIX = "oralsight.cloud.device-id.v1.";

interface EntityMarker {
  entityType: SyncOperationInput["entityType"];
  entityId: string;
  hash: string;
  version: number;
  deleted: boolean;
}

export interface CloudSyncResult {
  staged: number;
  pushed: number;
  pulled: number;
  pending: number;
  deviceId: string;
  keyId: string;
  recoveryCode: string;
  recoveryCodeWasCreated: boolean;
  completedAt: string;
  product: {
    sessionsCreated: number;
    captureSetsCreated: number;
    capturesUploaded: number;
    analysisJobsCreated: number;
    lesionsCreated: number;
    matchProposalsCreated: number;
    matchDecisionsRecorded: number;
    comparisonJobsCreated: number;
  };
  capturesDownloaded: number;
}

function accountStorageSuffix(accountId: string): string {
  return syncEntityFingerprint(accountId).slice(0, 32);
}

async function installationId(): Promise<string> {
  const stored = await SecureStore.getItemAsync(INSTALLATION_ID_KEY);
  if (stored) return stored;
  const value = Crypto.randomUUID();
  await SecureStore.setItemAsync(INSTALLATION_ID_KEY, value, {
    keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
  });
  return value;
}

export async function clearCloudInstallationIdentity(
  accountId: string,
): Promise<void> {
  await Promise.all([
    SecureStore.deleteItemAsync(INSTALLATION_ID_KEY),
    SecureStore.deleteItemAsync(
      `${DEVICE_ID_KEY_PREFIX}${accountStorageSuffix(accountId)}`,
    ),
  ]);
}

async function ensureDevice(
  client: PlatformClient,
  account: MeResponse,
): Promise<string> {
  const key = `${DEVICE_ID_KEY_PREFIX}${accountStorageSuffix(account.id)}`;
  const stored = await SecureStore.getItemAsync(key);
  if (stored) return stored;
  const installId = await installationId();
  const device = await client.registerDevice(
    {
      installationId: installId,
      platform: Platform.OS === "ios" ? "ios" : "android",
      displayName: "OralSight mobile",
    },
    `device:${installId}`,
  );
  await SecureStore.setItemAsync(key, device.deviceId, {
    keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
  });
  return device.deviceId;
}

function parseMarker(raw: string | null): EntityMarker | null {
  if (!raw) return null;
  try {
    const value = JSON.parse(raw) as Partial<EntityMarker>;
    if (
      typeof value.entityType !== "string" ||
      typeof value.entityId !== "string" ||
      typeof value.hash !== "string" ||
      !Number.isInteger(value.version) ||
      (value.version ?? 0) <= 0 ||
      typeof value.deleted !== "boolean"
    ) {
      return null;
    }
    return value as EntityMarker;
  } catch {
    return null;
  }
}

async function stageLocalChanges(options: {
  state: PersistedAppState;
  accountId: string;
  deviceId: string;
  key: Uint8Array;
  resourceMappings: readonly CloudResourceMapping[];
}): Promise<number> {
  const metadata = await cloudMetadata("cloud.");
  const known = Object.entries(metadata)
    .filter(([name]) => name.startsWith("cloud.entity."))
    .flatMap(([name, raw]) => {
      const marker = parseMarker(raw);
      return marker ? [{ name, marker }] : [];
    });
  const current = buildSyncEntities(options.state);
  const currentKeys = new Set(
    current.map((entity) =>
      syncEntityMetadataKey(entity.entityType, entity.entityId),
    ),
  );
  let sequence = Number(metadata["cloud.sequence"] ?? "0");
  if (!Number.isSafeInteger(sequence) || sequence < 0) sequence = 0;
  const operations: CloudOutboxInsert[] = [];
  const updates: Record<string, string | null> = {};
  const now = new Date().toISOString();
  const resourceMappings = new Map(
    options.resourceMappings.map((mapping) => [
      `${mapping.kind}:${mapping.localId}`,
      mapping,
    ]),
  );

  for (const entity of current) {
    const metadataKey = syncEntityMetadataKey(
      entity.entityType,
      entity.entityId,
    );
    const existing = parseMarker(metadata[metadataKey] ?? null);
    const mappingKind =
      entity.entityType === "scan_session"
        ? "scan_session"
        : entity.entityType === "capture_set"
          ? "capture_set"
          : entity.entityType === "capture_view"
            ? "capture_view"
            : null;
    const cloudRefs = mappingKind
      ? resourceMappings.get(`${mappingKind}:${entity.entityId}`)
      : undefined;
    const fingerprint = syncEntityFingerprint({
      record: entity.payload,
      cloudRefs,
    });
    if (existing && !existing.deleted && existing.hash === fingerprint)
      continue;
    const version = (existing?.version ?? 0) + 1;
    sequence += 1;
    const operationId = Crypto.randomUUID();
    const envelope: CloudEntityEnvelope = {
      schemaVersion: 1,
      entityType: entity.entityType,
      entityId: entity.entityId,
      record: entity.payload,
      ...(cloudRefs ? { cloudRefs: { ...cloudRefs } } : {}),
    };
    const operation: SyncOperationInput = {
      contractVersion: "2.0.0",
      operationId,
      idempotencyKey: `sync-op:${operationId}`,
      deviceId: options.deviceId,
      entityType: entity.entityType,
      entityId: entity.entityId,
      version,
      sequence,
      occurredAt: now,
      operation: "upsert",
      encryptedPayload: await encryptCloudEntity({
        accountId: options.accountId,
        entityType: entity.entityType,
        entityId: entity.entityId,
        payload: envelope,
        key: options.key,
      }),
      tombstone: false,
    };
    operations.push({
      id: operationId,
      entityType: entity.entityType,
      entityId: entity.entityId,
      operation: "upsert",
      payload: JSON.stringify(operation),
      createdAt: now,
    });
    updates[metadataKey] = JSON.stringify({
      entityType: entity.entityType,
      entityId: entity.entityId,
      hash: fingerprint,
      version,
      deleted: false,
    } satisfies EntityMarker);
  }

  for (const { name, marker } of known) {
    if (marker.deleted || currentKeys.has(name)) continue;
    const version = marker.version + 1;
    sequence += 1;
    const operationId = Crypto.randomUUID();
    const operation: SyncOperationInput = {
      contractVersion: "2.0.0",
      operationId,
      idempotencyKey: `sync-op:${operationId}`,
      deviceId: options.deviceId,
      entityType: marker.entityType,
      entityId: marker.entityId,
      version,
      sequence,
      occurredAt: now,
      operation: "delete",
      encryptedPayload: null,
      tombstone: true,
    };
    operations.push({
      id: operationId,
      entityType: marker.entityType,
      entityId: marker.entityId,
      operation: "delete",
      payload: JSON.stringify(operation),
      createdAt: now,
    });
    updates[name] = JSON.stringify({
      ...marker,
      hash: "deleted",
      version,
      deleted: true,
    } satisfies EntityMarker);
  }
  updates["cloud.sequence"] = String(sequence);
  if (operations.length > 0 || Object.keys(updates).length > 0) {
    await stageCloudOutbox(operations, updates);
  }
  return operations.length;
}

async function pushPending(client: PlatformClient): Promise<number> {
  let pushed = 0;
  for (;;) {
    const records = await readCloudOutbox(100);
    if (records.length === 0) break;
    const operations = records.map((record) =>
      syncOperationInputSchema.parse(JSON.parse(record.payload)),
    );
    await markCloudOutboxAttempt(records.map((record) => record.id));
    const batchKey = `sync-push:${syncEntityFingerprint(
      operations.map((operation) => operation.operationId),
    ).slice(0, 64)}`;
    const response = await client.pushSync(operations, batchKey);
    const acknowledged = new Set(
      response.results.map((result) => result.operationId),
    );
    if (records.some((record) => !acknowledged.has(record.id))) {
      throw new Error("The sync service did not acknowledge every operation.");
    }
    await acknowledgeCloudOutbox(records.map((record) => record.id));
    pushed += records.length;
  }
  return pushed;
}

async function pullRemote(options: {
  client: PlatformClient;
  accountId: string;
  deviceId: string;
  key: Uint8Array;
}): Promise<number> {
  const metadata = await cloudMetadata("cloud.");
  let cursor = metadata["cloud.cursor"] ?? undefined;
  let pulled = 0;
  let state = (await loadPersistedState()) ?? useOralSightStore.getState();
  const metadataUpdates: Record<string, string | null> = {};

  for (let pageNumber = 0; pageNumber < 100; pageNumber += 1) {
    const page = await options.client.pullSync(cursor, 100);
    const changes: DecryptedSyncChange[] = [];
    for (const operation of page.operations) {
      const markerKey = syncEntityMetadataKey(
        operation.entityType,
        operation.entityId,
      );
      const marker = parseMarker(
        metadataUpdates[markerKey] ?? metadata[markerKey] ?? null,
      );
      if ((marker?.version ?? 0) > operation.version) continue;
      if (operation.deviceId !== options.deviceId) {
        const decrypted =
          operation.operation === "upsert" && operation.encryptedPayload
            ? decryptCloudEntity({
                accountId: options.accountId,
                entityType: operation.entityType,
                entityId: operation.entityId,
                encryptedPayload: operation.encryptedPayload,
                key: options.key,
              })
            : null;
        changes.push({
          entityType: operation.entityType,
          entityId: operation.entityId,
          operation: operation.operation,
          payload: decrypted,
          version: operation.version,
          serverSequence: operation.serverSequence,
        });
        if (decrypted && typeof decrypted === "object") {
          const envelope = decrypted as CloudEntityEnvelope;
          const refs = envelope.cloudRefs as
            Partial<CloudResourceMapping> | undefined;
          if (
            refs?.kind &&
            refs.localId === operation.entityId &&
            typeof refs.remoteId === "string" &&
            typeof refs.updatedAt === "string"
          ) {
            metadataUpdates[cloudMappingKey(refs.kind, operation.entityId)] =
              JSON.stringify(refs);
          }
        }
      }
      const remoteEnvelope =
        operation.operation === "upsert" &&
        operation.deviceId !== options.deviceId
          ? (changes.at(-1)?.payload as CloudEntityEnvelope | undefined)
          : undefined;
      const markerFingerprint =
        operation.operation === "delete"
          ? "deleted"
          : operation.deviceId === options.deviceId
            ? (marker?.hash ?? "local")
            : remoteEnvelope
              ? syncEntityFingerprint({
                  record: remoteEnvelope.record,
                  cloudRefs: remoteEnvelope.cloudRefs,
                })
              : "unavailable";
      metadataUpdates[markerKey] = JSON.stringify({
        entityType: operation.entityType,
        entityId: operation.entityId,
        hash: markerFingerprint,
        version: operation.version,
        deleted: operation.operation === "delete",
      } satisfies EntityMarker);
    }
    if (changes.length > 0) {
      state = mergeRemoteChanges(state, changes);
      await useOralSightStore.getState().applyCloudState(state);
      pulled += changes.length;
    }
    cursor = page.cursor.cursor;
    metadataUpdates["cloud.cursor"] = cursor;
    await updateCloudMetadata(metadataUpdates);
    if (!page.hasMore) break;
    if (pageNumber === 99) {
      throw new Error(
        "Sync exceeded its safe page limit and will resume later.",
      );
    }
  }
  return pulled;
}

async function performCloudSync(
  client = new PlatformClient(),
  options: { confirmAccountRebind?: boolean } = {},
): Promise<CloudSyncResult> {
  const account = await client.account();
  if (account.deletionPending) {
    throw new Error(
      "Cloud deletion is pending. New uploads and processing are paused.",
    );
  }
  const productConsent = await requireActiveProductConsent(client);
  await bindCloudAccount(account.id);
  if (await cloudAccountRebindPending()) {
    if (!options.confirmAccountRebind) {
      throw new Error(
        "This device was linked to another account. Review the local records, then tap Sync now if you want to copy this workspace into the newly signed-in account.",
      );
    }
    await confirmCloudAccountRebind();
  }
  const deviceId = await ensureDevice(client, account);
  const keyMaterial = await loadOrCreateCloudKey(account.id);
  const initialPull = await pullRemote({
    client,
    accountId: account.id,
    deviceId,
    key: keyMaterial.key,
  });
  const afterPull = await loadPersistedState();
  const materialized = afterPull
    ? await materializeRemoteCaptures({ client, state: afterPull })
    : { state: afterPull, downloaded: 0 };
  const persisted = materialized.state;
  const product = persisted
    ? await syncProductResources({
        client,
        state: persisted,
        deviceId,
        consentRecordId: productConsent.consentRecordId,
      })
    : {
        sessionsCreated: 0,
        captureSetsCreated: 0,
        capturesUploaded: 0,
        analysisJobsCreated: 0,
        lesionsCreated: 0,
        matchProposalsCreated: 0,
        matchDecisionsRecorded: 0,
        comparisonJobsCreated: 0,
      };
  const resourceMappings = await readCloudResourceMappings();
  const staged = persisted
    ? await stageLocalChanges({
        state: persisted,
        accountId: account.id,
        deviceId,
        key: keyMaterial.key,
        resourceMappings,
      })
    : 0;
  const pushed = await pushPending(client);
  const finalPull = await pullRemote({
    client,
    accountId: account.id,
    deviceId,
    key: keyMaterial.key,
  });
  const pending = (await readCloudOutbox(100)).length;
  const completedAt = new Date().toISOString();
  await updateCloudMetadata({
    "cloud.last_sync_at": completedAt,
    "cloud.last_sync_error": null,
  });
  return {
    staged,
    pushed,
    pulled: initialPull + finalPull,
    pending,
    deviceId,
    keyId: keyMaterial.keyId,
    recoveryCode: keyMaterial.recoveryCode,
    recoveryCodeWasCreated: keyMaterial.created,
    completedAt,
    product,
    capturesDownloaded: materialized.downloaded,
  };
}

let activeSync: Promise<CloudSyncResult> | null = null;

/** Coalesces foreground, manual, and background triggers into one sync run. */
export function runCloudSync(
  client = new PlatformClient(),
  options: { confirmAccountRebind?: boolean } = {},
): Promise<CloudSyncResult> {
  activeSync ??= performCloudSync(client, options).finally(() => {
    activeSync = null;
  });
  return activeSync;
}

export async function rememberCloudSyncError(error: unknown): Promise<void> {
  await updateCloudMetadata({
    "cloud.last_sync_error":
      error instanceof Error ? error.message.slice(0, 500) : "Sync failed.",
  });
}

export async function cloudSyncSummary(): Promise<{
  pending: number;
  lastSyncAt: string | null;
  lastError: string | null;
}> {
  const metadata = await cloudMetadata("cloud.");
  return {
    pending: (await readCloudOutbox(100)).length,
    lastSyncAt: metadata["cloud.last_sync_at"] ?? null,
    lastError: metadata["cloud.last_sync_error"] ?? null,
  };
}
