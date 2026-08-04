import {
  CONTRACT_VERSION,
  DISCLAIMER,
  type AnalysisResult,
  type ComparisonResult,
} from "@oralsight/contracts";
import { describe, expect, it } from "vitest";

import {
  CREATE_NORMALIZED_STORAGE_SCHEMA_SQL,
  NORMALIZED_STORAGE_CLEAR_ORDER,
  NORMALIZED_STORAGE_SCHEMA_VERSION,
  NORMALIZED_STORAGE_TABLES,
  entityIdentities,
  planStorageInitialization,
  reconcileNormalizedRows,
  restorePersistedState,
} from "../src/lib/normalizedStorageSchema";
import type {
  CaptureRecord,
  PersistedAppState,
  ScanSession,
} from "../src/types";

const earlierSession: ScanSession = {
  id: "session-earlier",
  createdAt: "2026-01-01T12:00:00.000Z",
  demo: false,
  label: "Earlier scan",
};

const currentSession: ScanSession = {
  id: "session-current",
  createdAt: "2026-02-01T12:00:00.000Z",
  demo: false,
  label: "Current scan",
  intakeProfile: {
    ageRange: "18_39",
    assisted: false,
    firstNoticed: "Last week",
    durationDays: 7,
    symptoms: ["sore"],
    change: "no_change",
    tobaccoExposure: "none",
    alcoholExposure: "none",
    previousConditions: "",
    professionallyExamined: false,
  },
  consentedAt: "2026-02-01T11:58:00.000Z",
};

function capture(
  id: string,
  sessionId: string,
  capturedAt: string,
): CaptureRecord {
  return {
    id,
    sessionId,
    region: "left_buccal_mucosa",
    capturedAt,
    encryptedUri: `file:///protected/${id}.orsf`,
    mimeType: "image/jpeg",
    inputOrigin: "live_capture",
    captureSource: "camera",
    privacyConfirmedByUser: true,
    regionConfirmedByUser: true,
    quality: {
      accepted: true,
      blurScore: 0.91,
      exposureScore: 0.88,
      glareScore: 0.08,
      obstructionScore: 0.05,
      faceDetected: false,
      reasons: [],
    },
  };
}

function analysis(captureId: string): AnalysisResult {
  return {
    contractVersion: CONTRACT_VERSION,
    captureId,
    region: "left_buccal_mucosa",
    quality: {
      accepted: true,
      blurScore: 0.91,
      exposureScore: 0.88,
      glareScore: 0.08,
      obstructionScore: 0.05,
      faceDetected: false,
      reasons: [],
    },
    anatomyPrediction: {
      region: "left_buccal_mucosa",
      confidence: 0.92,
      supported: true,
      selectedRegionMatches: true,
    },
    candidateMask: null,
    descriptors: null,
    appearanceOutput: null,
    diseaseResearchOutput: null,
    uncertainty: {
      overallConfidence: 0.8,
      imageQualityConfidence: 0.9,
      datasetSimilarity: 0.7,
      modelAgreement: 0.82,
      limitations: ["Research prototype"],
    },
    abstentionReasons: [],
    modelVersions: { anatomy: "test-v1" },
    inputOrigin: "live_capture",
    analysisOrigin: "live_model",
    status: "complete",
    disclaimer: DISCLAIMER,
  };
}

const comparison: ComparisonResult = {
  contractVersion: CONTRACT_VERSION,
  baselineCaptureId: "capture-earlier",
  currentCaptureId: "capture-current",
  region: "left_buccal_mucosa",
  candidateMatchScore: 0.91,
  userConfirmedMatch: true,
  registrationConfidence: 0.6,
  inlierRatio: 0.4,
  reprojectionErrorRatio: 0.05,
  normalizedChange: null,
  comparable: false,
  suppressionReasons: ["registration_gate_not_met"],
  modelVersions: { registration: "test-v1" },
  inputOrigin: "live_capture",
  analysisOrigin: "live_model",
  disclaimer: DISCLAIMER,
};

function fullState(): PersistedAppState {
  const earlier = capture(
    "capture-earlier",
    earlierSession.id,
    "2026-01-01T12:01:00.000Z",
  );
  const current = capture(
    "capture-current",
    currentSession.id,
    "2026-02-01T12:01:00.000Z",
  );
  return {
    schemaVersion: 2,
    consentedAt: "2026-02-01T11:58:00.000Z",
    profile: currentSession.intakeProfile ?? null,
    settings: {
      highContrast: true,
      largeText: false,
      reducedMotion: true,
      haptics: true,
      voiceInstructions: false,
      caregiverMode: false,
    },
    sessions: [earlierSession, currentSession],
    captures: [earlier, current],
    analyses: {
      [earlier.id]: analysis(earlier.id),
      [current.id]: analysis(current.id),
    },
    comparisons: [comparison],
    pins: [
      {
        id: "observation-1",
        region: "left_buccal_mucosa",
        meshId: "left-cheek",
        uvX: 0.4,
        uvY: 0.6,
        assetVersion: "mouth-v1",
        userConfirmed: true,
        firstObservedAt: earlier.capturedAt,
        status: "stable",
        captureIds: [earlier.id, current.id],
      },
    ],
    reports: [
      {
        id: "report-1",
        createdAt: "2026-02-01T13:00:00.000Z",
        encryptedUri: "file:///protected/report-1.orsf",
        sessionId: currentSession.id,
      },
    ],
    activeSessionId: currentSession.id,
  };
}

describe("normalized encrypted storage planning", () => {
  it("preserves every public schema-version 2 field during one-time migration", () => {
    const state = fullState();
    const plan = planStorageInitialization(
      null,
      JSON.stringify(state),
      "2026-03-01T00:00:00.000Z",
    );

    expect(plan.kind).toBe("migrate");
    if (plan.kind !== "migrate") throw new Error("Expected migration plan");
    expect(restorePersistedState(plan.rows)).toEqual(state);
    expect(plan.rows.captureSets).toHaveLength(state.captures.length);
    expect(plan.rows.captureViews).toHaveLength(state.captures.length);
  });

  it("is idempotent once the normalized schema version is recorded", () => {
    expect(
      planStorageInitialization(
        NORMALIZED_STORAGE_SCHEMA_VERSION,
        "not valid JSON and must not be re-read",
        "2026-03-02T00:00:00.000Z",
      ),
    ).toEqual({ kind: "ready" });
  });

  it("rejects invalid legacy data without mutating the prior snapshot", () => {
    const state = fullState();
    const migrated = planStorageInitialization(
      null,
      JSON.stringify(state),
      "2026-03-01T00:00:00.000Z",
    );
    if (migrated.kind !== "migrate") throw new Error("Expected migration");
    const before = structuredClone(migrated.rows);
    const invalid = {
      ...state,
      sessions: [],
    } as PersistedAppState;

    expect(() =>
      reconcileNormalizedRows(
        entityIdentities(migrated.rows),
        migrated.rows.tombstones,
        invalid,
        "2026-03-03T00:00:00.000Z",
      ),
    ).toThrow(/session is missing/i);
    expect(migrated.rows).toEqual(before);
  });

  it("keeps deletions authoritative over a stale snapshot", () => {
    const state = fullState();
    const initial = planStorageInitialization(
      null,
      JSON.stringify(state),
      "2026-03-01T00:00:00.000Z",
    );
    if (initial.kind !== "migrate") throw new Error("Expected migration");
    const empty: PersistedAppState = {
      ...state,
      sessions: [],
      captures: [],
      analyses: {},
      comparisons: [],
      pins: [],
      reports: [],
      activeSessionId: null,
    };
    const deleted = reconcileNormalizedRows(
      entityIdentities(initial.rows),
      initial.rows.tombstones,
      empty,
      "2026-03-03T00:00:00.000Z",
    );
    const staleRetry = reconcileNormalizedRows(
      entityIdentities(deleted),
      deleted.tombstones,
      state,
      "2026-03-04T00:00:00.000Z",
    );

    expect(staleRetry.sessions).toEqual([]);
    expect(staleRetry.captureViews).toEqual([]);
    expect(staleRetry.analyses).toEqual([]);
    expect(staleRetry.observations).toEqual([]);
    expect(staleRetry.comparisons).toEqual([]);
    expect(staleRetry.reports).toEqual([]);
    expect(staleRetry.activeSessionId).toBeNull();
    expect(deleted.tombstones.length).toBeGreaterThan(0);
  });

  it("includes every normalized table in the destructive clear order", () => {
    expect(new Set(NORMALIZED_STORAGE_CLEAR_ORDER)).toEqual(
      new Set(NORMALIZED_STORAGE_TABLES),
    );
    for (const table of NORMALIZED_STORAGE_TABLES) {
      expect(CREATE_NORMALIZED_STORAGE_SCHEMA_SQL).toContain(
        `CREATE TABLE IF NOT EXISTS ${table}`,
      );
    }
  });
});
