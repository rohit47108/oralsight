import { describe, expect, it } from "vitest";

import { parsePersistedAppState } from "../src/lib/persistedStateSchema";

const validState = {
  schemaVersion: 4 as const,
  consentedAt: null,
  profile: null,
  settings: {
    highContrast: false,
    largeText: false,
    reducedMotion: false,
    animationSpeed: "standard" as const,
    haptics: true,
    voiceInstructions: false,
    caregiverMode: false,
    analyticsOptIn: false,
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

  it("migrates version 3 settings to safe analytics and motion defaults", () => {
    const {
      analyticsOptIn: _analyticsRemoved,
      animationSpeed: _speedRemoved,
      ...olderSettings
    } = validState.settings;
    const migrated = parsePersistedAppState({
      ...validState,
      schemaVersion: 3,
      settings: olderSettings,
    });
    expect(migrated.schemaVersion).toBe(4);
    expect(migrated.settings.analyticsOptIn).toBe(false);
    expect(migrated.settings.animationSpeed).toBe("standard");
  });

  it("adds fail-closed repeatability evidence to saved version 4 comparisons", () => {
    const migrated = parsePersistedAppState({
      ...validState,
      comparisons: [
        {
          contractVersion: "1.1.0",
          baselineCaptureId: "baseline",
          currentCaptureId: "current",
          region: "left_buccal_mucosa",
          candidateMatchScore: null,
          userConfirmedMatch: true,
          registrationConfidence: 0.9,
          inlierRatio: 0.8,
          reprojectionErrorRatio: 0.02,
          normalizedChange: null,
          descriptorChanges: null,
          calibratedMeasurementChanges: null,
          calibrationSuppressionReasons: [],
          comparable: false,
          suppressionReasons: ["repeated_capture_area_error_gate_unmet"],
          modelVersions: { registration: "registration-test-v1" },
          inputOrigin: "live_capture",
          analysisOrigin: "live_model",
          disclaimer: "This result is not a diagnosis.",
        },
      ],
    });

    expect(migrated.comparisons[0]).toMatchObject({
      repeatedCaptureAreaError: null,
      repeatabilityGatePassed: false,
      registrationAlignment: null,
      comparable: false,
    });
  });

  it("suppresses legacy comparable measurements that lack repeatability evidence", () => {
    const migrated = parsePersistedAppState({
      ...validState,
      comparisons: [
        {
          contractVersion: "1.1.0",
          baselineCaptureId: "baseline",
          currentCaptureId: "current",
          region: "left_buccal_mucosa",
          candidateMatchScore: 0.96,
          userConfirmedMatch: true,
          registrationConfidence: 0.9,
          inlierRatio: 0.8,
          reprojectionErrorRatio: 0.02,
          normalizedChange: 0.25,
          descriptorChanges: {
            normalizedWidthChange: 0.1,
            normalizedHeightChange: 0.2,
            normalizedPerimeterChange: 0.3,
            borderIrregularityChange: 0.04,
            meanRednessChange: 0.05,
            meanBrightnessChange: -0.05,
            textureContrastChange: 0.03,
            ulcerationLikeContrastChange: null,
            measurementLabel: "approximate image-normalized change",
          },
          calibratedMeasurementChanges: {
            cardVersion: "oralsight-calibration-v1",
            markerId: 17,
            markerSideMm: 20,
            baselineWidthMm: 8,
            currentWidthMm: 9,
            widthChangeMm: 1,
            baselineHeightMm: 5,
            currentHeightMm: 6,
            heightChangeMm: 1,
            baselineAreaMm2: 40,
            currentAreaMm2: 54,
            areaChangeMm2: 14,
            baselineConfidence: 0.9,
            currentConfidence: 0.9,
            measurementLabel: "calibrated estimate",
          },
          calibrationSuppressionReasons: [],
          comparable: true,
          suppressionReasons: [],
          modelVersions: { registration: "registration-test-v1" },
          inputOrigin: "live_capture",
          analysisOrigin: "live_model",
          disclaimer: "This result is not a diagnosis.",
        },
      ],
    });

    expect(migrated.comparisons[0]).toMatchObject({
      repeatedCaptureAreaError: null,
      repeatabilityGatePassed: false,
      normalizedChange: null,
      descriptorChanges: null,
      calibratedMeasurementChanges: null,
      calibrationSuppressionReasons: ["repeated_capture_area_error_gate_unmet"],
      comparable: false,
      suppressionReasons: ["repeated_capture_area_error_gate_unmet"],
    });
  });

  it("rejects unknown schema versions and partial settings", () => {
    expect(() =>
      parsePersistedAppState({ ...validState, schemaVersion: 5 }),
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

    expect(migrated.schemaVersion).toBe(4);
    expect(migrated.analyses["capture-1"]?.contractVersion).toBe("1.1.0");
    expect(
      migrated.analyses["capture-1"]?.uncertainty.datasetSimilarity,
    ).toBeNull();
    expect(
      migrated.analyses["capture-1"]?.uncertainty.modelAgreement,
    ).toBeNull();
  });

  it("migrates version 2 sessions and captures into the standard single-view protocol", () => {
    const migrated = parsePersistedAppState({
      ...validState,
      schemaVersion: 2,
      sessions: [
        {
          id: "session-1",
          createdAt: "2026-07-21T00:00:00.000Z",
          demo: false,
          label: "Earlier scan",
        },
      ],
      captures: [
        {
          id: "capture-1",
          sessionId: "session-1",
          region: "upper_lip",
          capturedAt: "2026-07-21T00:00:01.000Z",
          encryptedUri: null,
          mimeType: "image/jpeg",
          inputOrigin: "live_capture",
          quality: {
            accepted: true,
            blurScore: 0.9,
            exposureScore: 0.9,
            glareScore: 0.1,
            obstructionScore: 0.1,
            faceDetected: false,
            reasons: [],
          },
        },
      ],
    });

    expect(migrated.schemaVersion).toBe(4);
    expect(migrated.sessions[0]?.protocol).toBe("standard_eight_region");
    expect(migrated.captures[0]).toMatchObject({
      angle: "primary",
      mediaKind: "image",
    });
  });

  it("rejects incomplete sweep-frame provenance", () => {
    expect(() =>
      parsePersistedAppState({
        ...validState,
        sessions: [
          {
            id: "session-1",
            createdAt: "2026-07-21T00:00:00.000Z",
            demo: false,
            label: "Sweep",
            protocol: "guided_video_sweep",
          },
        ],
        captures: [
          {
            id: "capture-1",
            sessionId: "session-1",
            region: "upper_lip",
            angle: "straight",
            mediaKind: "video_frame",
            capturedAt: "2026-07-21T00:00:01.000Z",
            encryptedUri: null,
            mimeType: "image/jpeg",
            inputOrigin: "live_capture",
            captureSource: "video_sweep",
            quality: {
              accepted: true,
              blurScore: 0.9,
              exposureScore: 0.9,
              glareScore: 0.1,
              obstructionScore: 0.1,
              faceDetected: false,
              reasons: [],
            },
          },
        ],
      }),
    ).toThrow(/Video frames require/i);
  });

  it("requires versioned same-plane evidence for a calibration request", () => {
    const baseCapture = {
      id: "capture-calibrated",
      sessionId: "session-1",
      region: "lower_lip",
      angle: "primary",
      mediaKind: "image",
      capturedAt: "2026-07-21T00:00:01.000Z",
      encryptedUri: null,
      mimeType: "image/jpeg",
      inputOrigin: "live_capture",
      calibrationRequested: true,
      quality: {
        accepted: true,
        blurScore: 0.9,
        exposureScore: 0.9,
        glareScore: 0.1,
        obstructionScore: 0.1,
        faceDetected: false,
        reasons: [],
      },
    };
    const stateWithCapture = (capture: object) => ({
      ...validState,
      sessions: [
        {
          id: "session-1",
          createdAt: "2026-07-21T00:00:00.000Z",
          demo: false,
          label: "Calibrated scan",
          protocol: "standard_eight_region",
        },
      ],
      captures: [capture],
    });

    expect(() => parsePersistedAppState(stateWithCapture(baseCapture))).toThrow(
      /same-plane/i,
    );
    expect(
      parsePersistedAppState(
        stateWithCapture({
          ...baseCapture,
          calibrationPlaneConfirmed: true,
          calibrationCardVersion: "oralsight-calibration-v1",
        }),
      ).captures[0],
    ).toMatchObject({
      calibrationRequested: true,
      calibrationPlaneConfirmed: true,
      calibrationCardVersion: "oralsight-calibration-v1",
    });
  });
});
