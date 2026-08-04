import { describe, expect, it } from "vitest";

import { parsePersistedAppState } from "../src/lib/persistedStateSchema";

const validState = {
  schemaVersion: 2 as const,
  consentedAt: null,
  profile: null,
  settings: {
    highContrast: false,
    largeText: false,
    reducedMotion: false,
    haptics: true,
    voiceInstructions: false,
    caregiverMode: false,
  },
  sessions: [],
  captures: [],
  analyses: {},
  comparisons: [],
  pins: [],
  reports: [],
  activeSessionId: null,
};

describe("persisted state validation", () => {
  it("accepts the current empty state", () => {
    expect(parsePersistedAppState(validState)).toEqual(validState);
  });

  it("rejects unknown schema versions and partial settings", () => {
    expect(() =>
      parsePersistedAppState({ ...validState, schemaVersion: 3 }),
    ).toThrow();
    expect(() =>
      parsePersistedAppState({
        ...validState,
        settings: { ...validState.settings, haptics: undefined },
      }),
    ).toThrow();
  });

  it("rejects unknown persisted fields instead of silently trusting them", () => {
    expect(() =>
      parsePersistedAppState({ ...validState, unexpected: true }),
    ).toThrow();
  });

  it("migrates version 1 live analyses without retaining invented uncertainty scores", () => {
    const legacyAnalysis = {
      contractVersion: "1.0.0",
      captureId: "capture-1",
      region: "left_buccal_mucosa",
      quality: {
        accepted: true,
        blurScore: 0.9,
        exposureScore: 0.9,
        glareScore: 0.1,
        obstructionScore: 0.1,
        faceDetected: false,
        reasons: [],
      },
      anatomyPrediction: {
        region: "left_buccal_mucosa",
        confidence: 0.9,
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
        datasetSimilarity: 0,
        modelAgreement: 0.87,
        limitations: ["Legacy analysis"],
      },
      abstentionReasons: [],
      modelVersions: { anatomy: "legacy-test" },
      inputOrigin: "live_capture",
      analysisOrigin: "live_model",
      status: "complete",
      disclaimer: "This result is not a diagnosis.",
    };
    const migrated = parsePersistedAppState({
      ...validState,
      schemaVersion: 1,
      analyses: { "capture-1": legacyAnalysis },
    });

    expect(migrated.schemaVersion).toBe(2);
    expect(migrated.analyses["capture-1"]?.contractVersion).toBe("1.1.0");
    expect(
      migrated.analyses["capture-1"]?.uncertainty.datasetSimilarity,
    ).toBeNull();
    expect(
      migrated.analyses["capture-1"]?.uncertainty.modelAgreement,
    ).toBeNull();
  });
});
