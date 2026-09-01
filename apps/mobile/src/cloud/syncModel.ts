import { fromByteArray } from "base64-js";
import { sha256 } from "@noble/hashes/sha2.js";

import { parsePersistedAppState } from "../lib/persistedStateSchema";
import type {
  CaptureRecord,
  ObservationPin,
  PersistedAppState,
  ReportRecord,
  ScanSession,
} from "../types";
import type { AnalysisResult, ComparisonResult } from "@stoma3d/contracts";

import type { SyncOperationInput } from "./contracts";

export interface SyncEntitySnapshot {
  entityType: SyncOperationInput["entityType"];
  entityId: string;
  payload: unknown;
}

export interface DecryptedSyncChange {
  entityType: SyncOperationInput["entityType"];
  entityId: string;
  operation: "upsert" | "delete";
  payload: unknown | null;
  version: number;
  serverSequence: number;
}

export interface CloudEntityEnvelope {
  schemaVersion: 1;
  entityType: SyncOperationInput["entityType"];
  entityId: string;
  record: unknown;
  cloudRefs?: Record<string, unknown>;
}

export function localComparisonId(comparison: ComparisonResult): string {
  return `${comparison.baselineCaptureId.length}:${comparison.baselineCaptureId}${comparison.currentCaptureId}`;
}

export function localCaptureSetId(sessionId: string, region: string): string {
  return `capture-set:${sessionId}:${region}`;
}

export function buildSyncEntities(
  state: PersistedAppState,
): SyncEntitySnapshot[] {
  const sessions = new Map(state.sessions.map((value) => [value.id, value]));
  const captureSets = new Map<string, SyncEntitySnapshot>();
  for (const capture of state.captures) {
    const session = sessions.get(capture.sessionId);
    if (!session) continue;
    const id = localCaptureSetId(capture.sessionId, capture.region);
    captureSets.set(id, {
      entityType: "capture_set",
      entityId: id,
      payload: {
        id,
        sessionId: capture.sessionId,
        region: capture.region,
        protocol: session.protocol,
      },
    });
  }
  return [
    ...state.sessions.map((record) => ({
      entityType: "scan_session" as const,
      entityId: record.id,
      payload: record,
    })),
    ...captureSets.values(),
    ...state.captures.map((record) => ({
      entityType: "capture_view" as const,
      entityId: record.id,
      // A device-local vault URI is never uploaded. The product asset mapping
      // is stored separately and lets another device materialize the file.
      payload: { ...record, encryptedUri: null },
    })),
    ...Object.entries(state.analyses).map(([captureId, record]) => ({
      entityType: "analysis_run" as const,
      entityId: captureId,
      payload: record,
    })),
    ...state.pins.map((record) => ({
      entityType: "observation" as const,
      entityId: record.id,
      payload: record,
    })),
    ...state.comparisons.map((record) => ({
      entityType: "match_decision" as const,
      entityId: localComparisonId(record),
      payload: record,
    })),
    ...state.reports.map((record) => ({
      entityType: "report" as const,
      entityId: record.id,
      payload: { ...record, encryptedUri: null },
    })),
  ];
}

function sorted(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sorted);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, item]) => [key, sorted(item)]),
    );
  }
  return value;
}

export function stableJson(value: unknown): string {
  return JSON.stringify(sorted(value));
}

export function syncEntityFingerprint(value: unknown): string {
  return [...sha256(new TextEncoder().encode(stableJson(value)))]
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

export function syncMetadataComponent(value: string): string {
  return fromByteArray(new TextEncoder().encode(value))
    .replace(/=/g, "")
    .replace(/\+/g, "-")
    .replace(/\//g, "_");
}

export function syncEntityMetadataKey(
  entityType: string,
  entityId: string,
): string {
  return `cloud.entity.${syncMetadataComponent(entityType)}.${syncMetadataComponent(entityId)}`;
}

function isObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

export function parseCloudEnvelope(
  value: unknown,
  expectedType: SyncOperationInput["entityType"],
  expectedId: string,
): CloudEntityEnvelope {
  if (
    !isObject(value) ||
    value.schemaVersion !== 1 ||
    value.entityType !== expectedType ||
    value.entityId !== expectedId ||
    !("record" in value) ||
    (value.cloudRefs !== undefined && !isObject(value.cloudRefs))
  ) {
    throw new Error("The encrypted sync record is invalid.");
  }
  return value as unknown as CloudEntityEnvelope;
}

function removeCapture(
  state: PersistedAppState,
  captureId: string,
): PersistedAppState {
  const captures = state.captures.filter((value) => value.id !== captureId);
  const analyses = { ...state.analyses };
  delete analyses[captureId];
  return {
    ...state,
    captures,
    analyses,
    comparisons: state.comparisons.filter(
      (value) =>
        value.baselineCaptureId !== captureId &&
        value.currentCaptureId !== captureId,
    ),
    pins: state.pins.flatMap((pin) => {
      const captureIds = pin.captureIds.filter((id) => id !== captureId);
      return captureIds.length > 0 ? [{ ...pin, captureIds }] : [];
    }),
  };
}

function removeSession(
  state: PersistedAppState,
  sessionId: string,
): PersistedAppState {
  const captureIds = state.captures
    .filter((value) => value.sessionId === sessionId)
    .map((value) => value.id);
  let next = state;
  for (const captureId of captureIds) next = removeCapture(next, captureId);
  return {
    ...next,
    sessions: next.sessions.filter((value) => value.id !== sessionId),
    reports: next.reports.filter((value) => value.sessionId !== sessionId),
    activeSessionId:
      next.activeSessionId === sessionId ? null : next.activeSessionId,
  };
}

function replaceById<T extends { id: string }>(values: T[], record: T): T[] {
  return [...values.filter((value) => value.id !== record.id), record];
}

function applyChange(
  state: PersistedAppState,
  change: DecryptedSyncChange,
): PersistedAppState {
  if (change.operation === "delete") {
    switch (change.entityType) {
      case "scan_session":
        return removeSession(state, change.entityId);
      case "capture_set": {
        const [sessionId, region] =
          state.captures
            .filter(
              (capture) =>
                localCaptureSetId(capture.sessionId, capture.region) ===
                change.entityId,
            )
            .map(
              (capture) => [capture.sessionId, capture.region] as const,
            )[0] ?? [];
        if (!sessionId || !region) return state;
        return state.captures
          .filter(
            (capture) =>
              capture.sessionId === sessionId && capture.region === region,
          )
          .reduce(
            (current, capture) => removeCapture(current, capture.id),
            state,
          );
      }
      case "capture_view":
        return removeCapture(state, change.entityId);
      case "analysis_run": {
        const analyses = { ...state.analyses };
        delete analyses[change.entityId];
        return { ...state, analyses };
      }
      case "observation":
      case "lesion":
        return {
          ...state,
          pins: state.pins.filter((value) => value.id !== change.entityId),
        };
      case "match_decision":
        return {
          ...state,
          comparisons: state.comparisons.filter(
            (value) => localComparisonId(value) !== change.entityId,
          ),
        };
      case "report":
        return {
          ...state,
          reports: state.reports.filter(
            (value) => value.id !== change.entityId,
          ),
        };
    }
  }

  const envelope = parseCloudEnvelope(
    change.payload,
    change.entityType,
    change.entityId,
  );
  switch (change.entityType) {
    case "scan_session": {
      const record = envelope.record as ScanSession;
      return { ...state, sessions: replaceById(state.sessions, record) };
    }
    case "capture_set":
      return state;
    case "capture_view": {
      const incoming = envelope.record as CaptureRecord;
      const local = state.captures.find((value) => value.id === incoming.id);
      const record: CaptureRecord = {
        ...incoming,
        encryptedUri: local?.encryptedUri ?? null,
      };
      return { ...state, captures: replaceById(state.captures, record) };
    }
    case "analysis_run": {
      const record = envelope.record as AnalysisResult;
      return {
        ...state,
        analyses: { ...state.analyses, [change.entityId]: record },
      };
    }
    case "observation":
    case "lesion": {
      const record = envelope.record as ObservationPin;
      return { ...state, pins: replaceById(state.pins, record) };
    }
    case "match_decision": {
      const record = envelope.record as ComparisonResult;
      return {
        ...state,
        comparisons: [
          ...state.comparisons.filter(
            (value) => localComparisonId(value) !== change.entityId,
          ),
          record,
        ],
      };
    }
    case "report": {
      const incoming = envelope.record as ReportRecord;
      const local = state.reports.find((value) => value.id === incoming.id);
      if (!local?.encryptedUri) return state;
      return {
        ...state,
        reports: replaceById(state.reports, {
          ...incoming,
          encryptedUri: local.encryptedUri,
        }),
      };
    }
  }
}

/** Applies relation-producing records before their children, then validates the whole graph. */
export function mergeRemoteChanges(
  state: PersistedAppState,
  changes: readonly DecryptedSyncChange[],
): PersistedAppState {
  const priority: Record<SyncOperationInput["entityType"], number> = {
    scan_session: 0,
    capture_set: 1,
    capture_view: 2,
    analysis_run: 3,
    observation: 4,
    lesion: 4,
    match_decision: 5,
    report: 6,
  };
  const ordered = [...changes].sort(
    (left, right) =>
      priority[left.entityType] - priority[right.entityType] ||
      left.serverSequence - right.serverSequence,
  );
  let next = state;
  for (const change of ordered) next = applyChange(next, change);
  return parsePersistedAppState(next);
}
