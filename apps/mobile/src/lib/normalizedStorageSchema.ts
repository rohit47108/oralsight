import type {
  AnalysisResult,
  CaptureProtocol,
  ComparisonResult,
  MouthRegion,
} from "@oralsight/contracts";

import { parsePersistedAppState } from "./persistedStateSchema";
import type {
  AccessibilitySettings,
  CaptureRecord,
  IntakeProfile,
  ObservationPin,
  PersistedAppState,
  ReportRecord,
  ScanSession,
} from "../types";

/**
 * The app-state contract and encrypted SQLite layout are versioned separately.
 */
export const NORMALIZED_STORAGE_SCHEMA_VERSION = 6;
export const PREVIOUS_NORMALIZED_STORAGE_SCHEMA_VERSION = 5;
export const OLDEST_UPGRADABLE_NORMALIZED_STORAGE_SCHEMA_VERSION = 3;

export const NORMALIZED_STORAGE_TABLES = [
  "metadata",
  "settings",
  "profile",
  "sessions",
  "capture_sets",
  "capture_views",
  "analyses",
  "observations",
  "comparisons",
  "reports",
  "outbox",
  "tombstones",
] as const;

/** Child tables come first so the same order is safe with foreign keys on. */
export const NORMALIZED_STORAGE_CLEAR_ORDER = [
  "analyses",
  "comparisons",
  "capture_views",
  "capture_sets",
  "observations",
  "reports",
  "sessions",
  "outbox",
  "tombstones",
  "profile",
  "settings",
  "metadata",
] as const satisfies readonly (typeof NORMALIZED_STORAGE_TABLES)[number][];

export const CREATE_NORMALIZED_STORAGE_SCHEMA_SQL = `
  CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY NOT NULL,
    value TEXT
  );

  CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    high_contrast INTEGER NOT NULL CHECK (high_contrast IN (0, 1)),
    large_text INTEGER NOT NULL CHECK (large_text IN (0, 1)),
    reduced_motion INTEGER NOT NULL CHECK (reduced_motion IN (0, 1)),
    animation_speed TEXT NOT NULL DEFAULT 'standard'
      CHECK (animation_speed IN ('slow', 'standard')),
    haptics INTEGER NOT NULL CHECK (haptics IN (0, 1)),
    voice_instructions INTEGER NOT NULL CHECK (voice_instructions IN (0, 1)),
    caregiver_mode INTEGER NOT NULL CHECK (caregiver_mode IN (0, 1)),
    analytics_opt_in INTEGER NOT NULL DEFAULT 0 CHECK (analytics_opt_in IN (0, 1))
  );

  CREATE TABLE IF NOT EXISTS profile (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    payload TEXT NOT NULL
  );

  CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY NOT NULL,
    ordinal INTEGER NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    demo INTEGER NOT NULL CHECK (demo IN (0, 1)),
    label TEXT NOT NULL,
    protocol TEXT NOT NULL,
    intake_profile_state TEXT NOT NULL
      CHECK (intake_profile_state IN ('missing', 'null', 'value')),
    intake_profile_payload TEXT,
    consented_at_present INTEGER NOT NULL CHECK (consented_at_present IN (0, 1)),
    consented_at TEXT
  );

  CREATE TABLE IF NOT EXISTS capture_sets (
    id TEXT PRIMARY KEY NOT NULL,
    session_id TEXT NOT NULL,
    region TEXT NOT NULL,
    protocol TEXT NOT NULL,
    ordinal INTEGER NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
  );
  CREATE INDEX IF NOT EXISTS capture_sets_session_region
    ON capture_sets(session_id, region);

  CREATE TABLE IF NOT EXISTS capture_views (
    id TEXT PRIMARY KEY NOT NULL,
    capture_set_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL UNIQUE,
    angle TEXT NOT NULL,
    media_kind TEXT NOT NULL CHECK (media_kind IN ('image', 'video_frame')),
    captured_at TEXT NOT NULL,
    encrypted_uri TEXT,
    mime_type TEXT NOT NULL,
    input_origin TEXT NOT NULL,
    fixture_sha256 TEXT,
    capture_source TEXT,
    source_video_duration_ms INTEGER,
    frame_time_ms INTEGER,
    calibration_requested INTEGER CHECK (calibration_requested IN (0, 1)),
    calibration_plane_confirmed INTEGER CHECK (calibration_plane_confirmed IN (0, 1)),
    calibration_card_version TEXT,
    calibration_payload TEXT,
    privacy_confirmed INTEGER CHECK (privacy_confirmed IN (0, 1)),
    region_confirmed INTEGER CHECK (region_confirmed IN (0, 1)),
    guidance_payload TEXT,
    quality_payload TEXT NOT NULL,
    sample_placeholder INTEGER CHECK (sample_placeholder IN (0, 1)),
    FOREIGN KEY (capture_set_id) REFERENCES capture_sets(id) ON DELETE CASCADE
  );
  CREATE INDEX IF NOT EXISTS capture_views_set
    ON capture_views(capture_set_id, ordinal);

  CREATE TABLE IF NOT EXISTS analyses (
    capture_view_id TEXT PRIMARY KEY NOT NULL,
    payload TEXT NOT NULL,
    FOREIGN KEY (capture_view_id) REFERENCES capture_views(id) ON DELETE CASCADE
  );

  CREATE TABLE IF NOT EXISTS observations (
    id TEXT PRIMARY KEY NOT NULL,
    ordinal INTEGER NOT NULL UNIQUE,
    region TEXT NOT NULL,
    mesh_id TEXT NOT NULL,
    uv_x REAL NOT NULL,
    uv_y REAL NOT NULL,
    asset_version TEXT NOT NULL,
    user_confirmed INTEGER NOT NULL CHECK (user_confirmed IN (0, 1)),
    first_observed_at TEXT NOT NULL,
    status TEXT NOT NULL,
    capture_ids_payload TEXT NOT NULL
  );

  CREATE TABLE IF NOT EXISTS comparisons (
    id TEXT PRIMARY KEY NOT NULL,
    ordinal INTEGER NOT NULL UNIQUE,
    baseline_capture_id TEXT NOT NULL,
    current_capture_id TEXT NOT NULL,
    payload TEXT NOT NULL,
    FOREIGN KEY (baseline_capture_id) REFERENCES capture_views(id) ON DELETE CASCADE,
    FOREIGN KEY (current_capture_id) REFERENCES capture_views(id) ON DELETE CASCADE
  );

  CREATE TABLE IF NOT EXISTS reports (
    id TEXT PRIMARY KEY NOT NULL,
    ordinal INTEGER NOT NULL UNIQUE,
    session_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    encrypted_uri TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
  );

  CREATE TABLE IF NOT EXISTS outbox (
    id TEXT PRIMARY KEY NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    operation TEXT NOT NULL,
    payload TEXT,
    created_at TEXT NOT NULL,
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0)
  );
  CREATE INDEX IF NOT EXISTS outbox_created_at ON outbox(created_at, id);

  CREATE TABLE IF NOT EXISTS tombstones (
    entity_type TEXT NOT NULL
      CHECK (entity_type IN ('sessions', 'capture_views', 'analyses', 'observations', 'comparisons', 'reports')),
    entity_id TEXT NOT NULL,
    deleted_at TEXT NOT NULL,
    PRIMARY KEY (entity_type, entity_id)
  );
`;

export const UPGRADE_NORMALIZED_STORAGE_V3_TO_V4_SQL = `
  ALTER TABLE sessions ADD COLUMN protocol TEXT NOT NULL DEFAULT 'standard_eight_region';
  ALTER TABLE capture_sets ADD COLUMN protocol TEXT NOT NULL DEFAULT 'standard_eight_region';
  ALTER TABLE capture_views ADD COLUMN angle TEXT NOT NULL DEFAULT 'primary';
  ALTER TABLE capture_views ADD COLUMN media_kind TEXT NOT NULL DEFAULT 'image';
  ALTER TABLE capture_views ADD COLUMN source_video_duration_ms INTEGER;
  ALTER TABLE capture_views ADD COLUMN frame_time_ms INTEGER;
  ALTER TABLE capture_views ADD COLUMN calibration_requested INTEGER;
  ALTER TABLE capture_views ADD COLUMN calibration_plane_confirmed INTEGER;
  ALTER TABLE capture_views ADD COLUMN calibration_card_version TEXT;
  ALTER TABLE capture_views ADD COLUMN calibration_payload TEXT;
  ALTER TABLE settings ADD COLUMN analytics_opt_in INTEGER NOT NULL DEFAULT 0;
`;

export const UPGRADE_NORMALIZED_STORAGE_V4_TO_V5_SQL = `
  ALTER TABLE settings ADD COLUMN animation_speed TEXT NOT NULL DEFAULT 'standard'
    CHECK (animation_speed IN ('slow', 'standard'));
`;

export const UPGRADE_NORMALIZED_STORAGE_V5_TO_V6_SQL = `
  ALTER TABLE capture_views ADD COLUMN guidance_payload TEXT;
`;

export type TombstonedEntityType =
  | "sessions"
  | "capture_views"
  | "analyses"
  | "observations"
  | "comparisons"
  | "reports";

export interface TombstoneRecord {
  entityType: TombstonedEntityType;
  entityId: string;
  deletedAt: string;
}

export interface CaptureSetRow {
  id: string;
  sessionId: string;
  region: MouthRegion;
  protocol: CaptureProtocol;
  ordinal: number;
  createdAt: string;
}

export interface CaptureViewRow {
  captureSetId: string;
  ordinal: number;
  capture: CaptureRecord;
}

export interface NormalizedStorageRows {
  statePresent: true;
  consentedAt: string | null;
  activeSessionId: string | null;
  updatedAt: string;
  settings: AccessibilitySettings;
  profile: IntakeProfile | null;
  sessions: ScanSession[];
  captureSets: CaptureSetRow[];
  captureViews: CaptureViewRow[];
  analyses: Array<{ captureId: string; analysis: AnalysisResult }>;
  observations: ObservationPin[];
  comparisons: Array<{ id: string; comparison: ComparisonResult }>;
  reports: ReportRecord[];
  tombstones: TombstoneRecord[];
}

export interface ExistingEntityIdentity {
  entityType: TombstonedEntityType;
  entityId: string;
}

export type StorageInitializationPlan =
  | { kind: "ready" }
  | { kind: "upgrade" }
  | { kind: "initialize-empty" }
  | { kind: "migrate"; rows: NormalizedStorageRows };

function comparisonId(comparison: ComparisonResult): string {
  return `${comparison.baselineCaptureId.length}:${comparison.baselineCaptureId}${comparison.currentCaptureId}`;
}

function captureSetId(sessionId: string, region: MouthRegion): string {
  return `capture-set:${sessionId}:${region}`;
}

function identityKey(identity: ExistingEntityIdentity): string {
  return `${identity.entityType}\u0000${identity.entityId}`;
}

function assertPersistedReferences(state: PersistedAppState): void {
  const sessions = new Set(state.sessions.map((session) => session.id));
  const captures = new Map(
    state.captures.map((capture) => [capture.id, capture]),
  );

  if (state.activeSessionId && !sessions.has(state.activeSessionId)) {
    throw new Error("Persisted active session is missing.");
  }
  for (const capture of state.captures) {
    if (!sessions.has(capture.sessionId)) {
      throw new Error("Persisted capture refers to a missing session.");
    }
  }
  for (const [captureId, analysis] of Object.entries(state.analyses)) {
    const capture = captures.get(captureId);
    if (
      !capture ||
      analysis.captureId !== captureId ||
      analysis.region !== capture.region ||
      analysis.inputOrigin !== capture.inputOrigin
    ) {
      throw new Error("Persisted analysis identity is inconsistent.");
    }
  }
  for (const comparison of state.comparisons) {
    const baseline = captures.get(comparison.baselineCaptureId);
    const current = captures.get(comparison.currentCaptureId);
    if (
      !baseline ||
      !current ||
      baseline.region !== comparison.region ||
      current.region !== comparison.region ||
      baseline.inputOrigin !== comparison.inputOrigin ||
      current.inputOrigin !== comparison.inputOrigin
    ) {
      throw new Error("Persisted comparison identity is inconsistent.");
    }
  }
  for (const observation of state.pins) {
    if (
      observation.captureIds.some(
        (captureId) => captures.get(captureId)?.region !== observation.region,
      )
    ) {
      throw new Error("Persisted observation identity is inconsistent.");
    }
  }
  for (const report of state.reports) {
    if (!sessions.has(report.sessionId)) {
      throw new Error("Persisted report refers to a missing session.");
    }
  }
}

function rowsFromState(
  untrustedState: PersistedAppState,
  updatedAt: string,
): NormalizedStorageRows {
  const state = parsePersistedAppState(untrustedState);
  assertPersistedReferences(state);
  const sessionsById = new Map(
    state.sessions.map((session) => [session.id, session]),
  );
  const captureSets = new Map<string, CaptureSetRow>();
  for (const [ordinal, capture] of state.captures.entries()) {
    const session = sessionsById.get(capture.sessionId);
    if (!session) throw new Error("Persisted capture session is missing.");
    const id = captureSetId(capture.sessionId, capture.region);
    if (!captureSets.has(id)) {
      captureSets.set(id, {
        id,
        sessionId: capture.sessionId,
        region: capture.region,
        protocol: session.protocol,
        ordinal,
        createdAt: capture.capturedAt,
      });
    }
  }
  return {
    statePresent: true,
    consentedAt: state.consentedAt,
    activeSessionId: state.activeSessionId,
    updatedAt,
    settings: state.settings,
    profile: state.profile,
    sessions: state.sessions,
    captureSets: [...captureSets.values()],
    captureViews: state.captures.map((capture, ordinal) => ({
      captureSetId: captureSetId(capture.sessionId, capture.region),
      ordinal,
      capture,
    })),
    analyses: Object.entries(state.analyses).map(([captureId, analysis]) => ({
      captureId,
      analysis,
    })),
    observations: state.pins,
    comparisons: state.comparisons.map((comparison) => ({
      id: comparisonId(comparison),
      comparison,
    })),
    reports: state.reports,
    tombstones: [],
  };
}

export function entityIdentities(
  rows: NormalizedStorageRows,
): ExistingEntityIdentity[] {
  return [
    ...rows.sessions.map((session) => ({
      entityType: "sessions" as const,
      entityId: session.id,
    })),
    ...rows.captureViews.map(({ capture }) => ({
      entityType: "capture_views" as const,
      entityId: capture.id,
    })),
    ...rows.analyses.map(({ captureId }) => ({
      entityType: "analyses" as const,
      entityId: captureId,
    })),
    ...rows.observations.map((observation) => ({
      entityType: "observations" as const,
      entityId: observation.id,
    })),
    ...rows.comparisons.map(({ id }) => ({
      entityType: "comparisons" as const,
      entityId: id,
    })),
    ...rows.reports.map((report) => ({
      entityType: "reports" as const,
      entityId: report.id,
    })),
  ];
}

/**
 * Reconciles a full Zustand snapshot with durable deletion records. A stale
 * snapshot cannot resurrect an identifier once it has a tombstone.
 */
export function reconcileNormalizedRows(
  previousEntities: readonly ExistingEntityIdentity[],
  existingTombstones: readonly TombstoneRecord[],
  state: PersistedAppState,
  updatedAt: string,
): NormalizedStorageRows {
  const desired = rowsFromState(state, updatedAt);
  const desiredKeys = new Set(entityIdentities(desired).map(identityKey));
  const tombstones = new Map(
    existingTombstones.map((tombstone) => [identityKey(tombstone), tombstone]),
  );

  for (const previous of previousEntities) {
    const key = identityKey(previous);
    if (!desiredKeys.has(key) && !tombstones.has(key)) {
      tombstones.set(key, { ...previous, deletedAt: updatedAt });
    }
  }

  const isLive = (identity: ExistingEntityIdentity): boolean =>
    !tombstones.has(identityKey(identity));
  const sessions = desired.sessions.filter((session) =>
    isLive({ entityType: "sessions", entityId: session.id }),
  );
  const sessionIds = new Set(sessions.map((session) => session.id));
  const captureViews = desired.captureViews.filter(
    ({ capture }) =>
      sessionIds.has(capture.sessionId) &&
      isLive({ entityType: "capture_views", entityId: capture.id }),
  );
  const captureIds = new Set(captureViews.map(({ capture }) => capture.id));
  const captureSetIds = new Set(captureViews.map(({ captureSetId: id }) => id));

  return {
    ...desired,
    activeSessionId:
      desired.activeSessionId && sessionIds.has(desired.activeSessionId)
        ? desired.activeSessionId
        : null,
    sessions,
    captureSets: desired.captureSets.filter((row) => captureSetIds.has(row.id)),
    captureViews,
    analyses: desired.analyses.filter(
      ({ captureId }) =>
        captureIds.has(captureId) &&
        isLive({ entityType: "analyses", entityId: captureId }),
    ),
    observations: desired.observations.filter(
      (observation) =>
        observation.captureIds.every((captureId) =>
          captureIds.has(captureId),
        ) &&
        isLive({
          entityType: "observations",
          entityId: observation.id,
        }),
    ),
    comparisons: desired.comparisons.filter(
      ({ id, comparison }) =>
        captureIds.has(comparison.baselineCaptureId) &&
        captureIds.has(comparison.currentCaptureId) &&
        isLive({ entityType: "comparisons", entityId: id }),
    ),
    reports: desired.reports.filter(
      (report) =>
        sessionIds.has(report.sessionId) &&
        isLive({ entityType: "reports", entityId: report.id }),
    ),
    tombstones: [...tombstones.values()],
  };
}

export function restorePersistedState(
  rows: NormalizedStorageRows,
): PersistedAppState {
  const state: PersistedAppState = {
    schemaVersion: 4,
    consentedAt: rows.consentedAt,
    profile: rows.profile,
    settings: rows.settings,
    sessions: rows.sessions,
    captures: rows.captureViews.map(({ capture }) => capture),
    analyses: Object.fromEntries(
      rows.analyses.map(({ captureId, analysis }) => [captureId, analysis]),
    ),
    comparisons: rows.comparisons.map(({ comparison }) => comparison),
    pins: rows.observations,
    reports: rows.reports,
    activeSessionId: rows.activeSessionId,
  };
  const parsed = parsePersistedAppState(state);
  assertPersistedReferences(parsed);
  return parsed;
}

/** Pure decision helper used by the transactional database initializer. */
export function planStorageInitialization(
  storedVersion: number | null,
  legacyPayload: string | null,
  updatedAt: string,
): StorageInitializationPlan {
  if (storedVersion === NORMALIZED_STORAGE_SCHEMA_VERSION) {
    return { kind: "ready" };
  }
  if (
    storedVersion !== null &&
    storedVersion >= OLDEST_UPGRADABLE_NORMALIZED_STORAGE_SCHEMA_VERSION &&
    storedVersion < NORMALIZED_STORAGE_SCHEMA_VERSION
  ) {
    return { kind: "upgrade" };
  }
  if (storedVersion !== null) {
    throw new Error(`Unsupported protected storage version: ${storedVersion}`);
  }
  if (legacyPayload === null) {
    return { kind: "initialize-empty" };
  }
  const parsedJson = JSON.parse(legacyPayload) as unknown;
  const migratedState = parsePersistedAppState(parsedJson);
  return {
    kind: "migrate",
    rows: reconcileNormalizedRows([], [], migratedState, updatedAt),
  };
}
