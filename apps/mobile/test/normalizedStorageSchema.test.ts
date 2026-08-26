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
  OLDEST_UPGRADABLE_NORMALIZED_STORAGE_SCHEMA_VERSION,
  PREVIOUS_NORMALIZED_STORAGE_SCHEMA_VERSION,
  UPGRADE_NORMALIZED_STORAGE_V3_TO_V4_SQL,
  UPGRADE_NORMALIZED_STORAGE_V4_TO_V5_SQL,
  UPGRADE_NORMALIZED_STORAGE_V5_TO_V6_SQL,
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
  protocol: "standard_eight_region",
};

const currentSession: ScanSession = {
  id: "session-current",
  createdAt: "2026-02-01T12:00:00.000Z",
  demo: false,
  label: "Current scan",
  protocol: "standard_eight_region",
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
    angle: "primary",
    mediaKind: "image",
    capturedAt,
    encryptedUri: `file:///protected/${id}.orsf`,
    mimeType: "image/jpeg",
    inputOrigin: "live_capture",
    captureSource: "camera",
    privacyConfirmedByUser: true,
    regionConfirmedByUser: true,
    captureGuidance: {
      stabilityPercent: 96,
      tiltDegrees: -4.2,
      rotationDegrees: 1.8,
      targetWidthPercent: 53,
      source: "live_camera",
    },
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
  repeatedCaptureAreaError: null,
  repeatabilityGatePassed: false,
  registrationAlignment: null,
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
    schemaVersion: 4,
    consentedAt: "2026-02-01T11:58:00.000Z",
    profile: currentSession.intakeProfile ?? null,
    settings: {
      highContrast: true,
      largeText: false,
      reducedMotion: true,
      animationSpeed: "slow",
      haptics: true,
      voiceInstructions: false,
      caregiverMode: false,
      analyticsOptIn: false,
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
        comparisonStatus: "stable",
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
  it("preserves every app schema-version 4 field during one-time migration", () => {
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

  it("plans the current additive normalized schema upgrade without reading legacy JSON", () => {
    expect(
      planStorageInitialization(
        PREVIOUS_NORMALIZED_STORAGE_SCHEMA_VERSION,
        "not valid JSON",
        "2026-03-02T00:00:00.000Z",
      ),
    ).toEqual({ kind: "upgrade" });
    expect(UPGRADE_NORMALIZED_STORAGE_V5_TO_V6_SQL).toContain(
      "ADD COLUMN guidance_payload",
    );
  });

  it("keeps a sequential upgrade path from normalized schema version 4", () => {
    expect(
      planStorageInitialization(
        4,
        "not valid JSON",
        "2026-03-02T00:00:00.000Z",
      ),
    ).toEqual({ kind: "upgrade" });
    expect(UPGRADE_NORMALIZED_STORAGE_V4_TO_V5_SQL).toContain(
      "ADD COLUMN animation_speed",
    );
    expect(UPGRADE_NORMALIZED_STORAGE_V5_TO_V6_SQL).toContain(
      "ADD COLUMN guidance_payload",
    );
  });

  it("keeps a sequential upgrade path from normalized schema version 3", () => {
    expect(
      planStorageInitialization(
        OLDEST_UPGRADABLE_NORMALIZED_STORAGE_SCHEMA_VERSION,
        "not valid JSON",
        "2026-03-02T00:00:00.000Z",
      ),
    ).toEqual({ kind: "upgrade" });
    expect(UPGRADE_NORMALIZED_STORAGE_V3_TO_V4_SQL).toContain(
      "ADD COLUMN protocol",
    );
    expect(UPGRADE_NORMALIZED_STORAGE_V3_TO_V4_SQL).toContain(
      "ADD COLUMN media_kind",
    );
    expect(UPGRADE_NORMALIZED_STORAGE_V3_TO_V4_SQL).toContain(
      "ADD COLUMN calibration_payload",
    );
    expect(UPGRADE_NORMALIZED_STORAGE_V3_TO_V4_SQL).toContain(
      "ADD COLUMN analytics_opt_in",
    );
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

  it("groups three angles for one region into one capture set without losing views", () => {
    const state = fullState();
    const session = {
      ...currentSession,
      protocol: "detailed_multi_angle" as const,
    };
    const angles = ["straight", "left_oblique", "right_oblique"] as const;
    const captures = angles.map((angle, index) => ({
      ...capture(
        `view-${angle}`,
        session.id,
        `2026-02-01T12:0${index + 1}:00.000Z`,
      ),
      angle,
    }));
    const multiView: PersistedAppState = {
      ...state,
      sessions: [session],
      captures,
      analyses: Object.fromEntries(
        captures.map((item) => [item.id, analysis(item.id)]),
      ),
      comparisons: [],
      pins: [],
      reports: [],
      activeSessionId: session.id,
    };
    const migrated = planStorageInitialization(
      null,
      JSON.stringify(multiView),
      "2026-03-01T00:00:00.000Z",
    );
    if (migrated.kind !== "migrate") throw new Error("Expected migration");

    expect(migrated.rows.captureSets).toHaveLength(1);
    expect(migrated.rows.captureViews.map((row) => row.capture.angle)).toEqual(
      angles,
    );
    expect(restorePersistedState(migrated.rows)).toEqual(multiView);
  });
});
