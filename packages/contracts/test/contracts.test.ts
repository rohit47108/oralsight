import { describe, expect, it } from "vitest";
import {
  ANALYSIS_ORIGIN_FIXTURE,
  CONTRACT_VERSION,
  DISCLAIMER,
  MOUTH_REGIONS,
  analyzeMetadataSchema,
  analysisResultSchema,
  candidateMaskSchema,
  compareMetadataSchema,
  comparisonResultSchema,
  isCompleteRegionSet,
  modelCardSchema,
  modelOutputSchema,
} from "../src/testing";
import bundledDemo from "../fixtures/bundled-demo.json";

describe("OralSight contracts", () => {
  it("requires every canonical region for completion", () => {
    expect(isCompleteRegionSet(MOUTH_REGIONS)).toBe(true);
    expect(isCompleteRegionSet(MOUTH_REGIONS.slice(0, 7))).toBe(false);
  });

  it("accepts a provenance-labelled abstention with unavailable uncertainty factors", () => {
    const result = analysisResultSchema.parse({
      contractVersion: CONTRACT_VERSION,
      captureId: "capture-1",
      region: "dorsal_tongue",
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
        region: "dorsal_tongue",
        confidence: 0.8,
        supported: true,
        selectedRegionMatches: true,
      },
      candidateMask: null,
      descriptors: null,
      appearanceOutput: null,
      diseaseResearchOutput: null,
      uncertainty: {
        overallConfidence: 0.2,
        imageQualityConfidence: 0.9,
        datasetSimilarity: null,
        modelAgreement: null,
        limitations: ["No release-gated segmentation model is deployed."],
      },
      abstentionReasons: ["Segmentation release gate has not passed."],
      modelVersions: { service: "test" },
      inputOrigin: "bundled_demo",
      analysisOrigin: ANALYSIS_ORIGIN_FIXTURE,
      status: "abstained",
      disclaimer: DISCLAIMER,
    });

    expect(result.status).toBe("abstained");
    expect(result.uncertainty.datasetSimilarity).toBeNull();
    expect(result.uncertainty.modelAgreement).toBeNull();
  });

  it("keeps the bundled fixture bound to its declared SHA-256", async () => {
    const bytes = Uint8Array.from(atob(bundledDemo.base64), (character) =>
      character.charCodeAt(0),
    );
    const digest = await crypto.subtle.digest("SHA-256", bytes);
    const actual = [...new Uint8Array(digest)]
      .map((byte) => byte.toString(16).padStart(2, "0"))
      .join("");

    expect(actual).toBe(bundledDemo.sha256);
    expect(actual).toBe(
      "61b49da924681f2a8dc6aab6380d7f197483925677af3a4c0a9db63c55a10338",
    );
  });

  it("binds comparison metadata to both prior analyses", () => {
    const prior = {
      region: "left_buccal_mucosa" as const,
      status: "complete" as const,
      analysisOrigin: "manual_fixture" as const,
      qualityAccepted: true,
      candidateNormalizedArea: 0.031,
      modelVersions: { fixture: "bundled-demo-left-cheek-v1" },
    };
    const valid = {
      contractVersion: CONTRACT_VERSION,
      baselineCaptureId: "baseline-1",
      currentCaptureId: "current-1",
      region: "left_buccal_mucosa" as const,
      userConfirmedMatch: true,
      inputOrigin: "bundled_demo" as const,
      baselineAnalysis: { ...prior, captureId: "baseline-1" },
      currentAnalysis: { ...prior, captureId: "current-1" },
    };

    expect(compareMetadataSchema.parse(valid).baselineAnalysis.captureId).toBe(
      "baseline-1",
    );
    expect(() =>
      compareMetadataSchema.parse({
        ...valid,
        currentAnalysis: { ...prior, captureId: "different-capture" },
      }),
    ).toThrow();
    expect(() =>
      compareMetadataSchema.parse({ ...valid, unexpected: "not allowed" }),
    ).toThrow();
  });

  it("requires exact fixture provenance and rejects unknown request fields", () => {
    const live = {
      contractVersion: CONTRACT_VERSION,
      captureId: "capture-1",
      selectedRegion: "left_buccal_mucosa" as const,
      inputOrigin: "live_capture" as const,
      requestedHeads: ["segmentation" as const],
    };
    expect(analyzeMetadataSchema.parse(live).inputOrigin).toBe("live_capture");
    expect(() =>
      analyzeMetadataSchema.parse({ ...live, unexpected: true }),
    ).toThrow();
    expect(() =>
      analyzeMetadataSchema.parse({ ...live, inputOrigin: "bundled_demo" }),
    ).toThrow(/fixtureSha256/i);
    expect(() =>
      analyzeMetadataSchema.parse({
        ...live,
        fixtureSha256: "0".repeat(64),
      }),
    ).toThrow(/fixtureSha256/i);
  });

  it("rejects predictions from a disabled model head", () => {
    expect(() =>
      modelOutputSchema.parse({
        enabled: false,
        gatePassed: false,
        topLabel: "red-patch",
        confidence: 0.8,
        scores: [{ label: "red-patch", probability: 0.8 }],
        limitation: "Test fixture",
      }),
    ).toThrow();
  });

  it("rejects malformed normalized candidate geometry", () => {
    expect(() =>
      candidateMaskSchema.parse({
        polygon: [
          [0.8, 0.8],
          [0.9, 0.8],
          [0.9, 0.9],
        ],
        boundingBox: [0.8, 0.8, 0.3, 0.3],
        normalizedArea: 0.01,
      }),
    ).toThrow(/bounding box/i);
  });

  it("rejects normalized change when comparison is suppressed", () => {
    expect(() =>
      comparisonResultSchema.parse({
        contractVersion: CONTRACT_VERSION,
        baselineCaptureId: "baseline-1",
        currentCaptureId: "current-1",
        region: "left_buccal_mucosa",
        candidateMatchScore: null,
        userConfirmedMatch: true,
        registrationConfidence: 0,
        inlierRatio: 0,
        reprojectionErrorRatio: 1,
        normalizedChange: 0.2,
        comparable: false,
        suppressionReasons: ["insufficient comparable data"],
        modelVersions: {},
        inputOrigin: "live_capture",
        analysisOrigin: "unavailable",
        disclaimer: DISCLAIMER,
      }),
    ).toThrow();
  });

  it("accepts gated descriptor and calibrated changes for a comparable pair", () => {
    const result = comparisonResultSchema.parse({
      contractVersion: CONTRACT_VERSION,
      baselineCaptureId: "baseline-1",
      currentCaptureId: "current-1",
      region: "left_buccal_mucosa",
      candidateMatchScore: 0.97,
      userConfirmedMatch: true,
      registrationConfidence: 0.92,
      inlierRatio: 0.81,
      reprojectionErrorRatio: 0.01,
      normalizedChange: 0.2,
      descriptorChanges: {
        normalizedWidthChange: 0.1,
        normalizedHeightChange: 0.05,
        normalizedPerimeterChange: 0.08,
        borderIrregularityChange: 0.02,
        meanRednessChange: 0.03,
        meanBrightnessChange: -0.01,
        textureContrastChange: 0.04,
        ulcerationLikeContrastChange: null,
        measurementLabel: "approximate image-normalized change",
      },
      calibratedMeasurementChanges: {
        cardVersion: "oralsight-calibration-v1",
        markerId: 17,
        markerSideMm: 20,
        baselineWidthMm: 4,
        currentWidthMm: 4.5,
        widthChangeMm: 0.5,
        baselineHeightMm: 3,
        currentHeightMm: 3.25,
        heightChangeMm: 0.25,
        baselineAreaMm2: 12,
        currentAreaMm2: 14.625,
        areaChangeMm2: 2.625,
        baselineConfidence: 0.9,
        currentConfidence: 0.88,
        measurementLabel: "calibrated estimate",
      },
      calibrationSuppressionReasons: [],
      comparable: true,
      suppressionReasons: [],
      modelVersions: { registration: "test" },
      inputOrigin: "live_capture",
      analysisOrigin: "live_model",
      disclaimer: DISCLAIMER,
    });

    expect(result.descriptorChanges?.normalizedWidthChange).toBe(0.1);
    expect(result.calibratedMeasurementChanges?.widthChangeMm).toBe(0.5);
  });

  it("rejects descriptor or calibrated changes when comparison is suppressed", () => {
    expect(() =>
      comparisonResultSchema.parse({
        contractVersion: CONTRACT_VERSION,
        baselineCaptureId: "baseline-1",
        currentCaptureId: "current-1",
        region: "left_buccal_mucosa",
        candidateMatchScore: null,
        userConfirmedMatch: true,
        registrationConfidence: 0,
        inlierRatio: 0,
        reprojectionErrorRatio: 1,
        normalizedChange: null,
        descriptorChanges: {
          normalizedWidthChange: 0,
          normalizedHeightChange: 0,
          normalizedPerimeterChange: 0,
          borderIrregularityChange: 0,
          meanRednessChange: 0,
          meanBrightnessChange: 0,
          textureContrastChange: 0,
          ulcerationLikeContrastChange: null,
          measurementLabel: "approximate image-normalized change",
        },
        calibratedMeasurementChanges: null,
        calibrationSuppressionReasons: [],
        comparable: false,
        suppressionReasons: ["insufficient comparable data"],
        modelVersions: {},
        inputOrigin: "live_capture",
        analysisOrigin: "unavailable",
        disclaimer: DISCLAIMER,
      }),
    ).toThrow(/descriptor or calibrated change/i);
  });

  it("rejects enabled model heads without complete release evidence", () => {
    expect(() =>
      modelCardSchema.parse({
        contractVersion: CONTRACT_VERSION,
        serviceVersion: "test",
        intendedUse: "Research prototype",
        forbiddenClaims: [],
        modelVersions: { segmentation: "test" },
        artifactHashes: { segmentation_weights: null },
        enabledHeads: ["segmentation"],
        releaseGates: [
          {
            head: "segmentation",
            passed: true,
            evaluatedAt: null,
            metrics: {},
            unmetRequirements: ["Evidence missing"],
            reviewerApproved: false,
          },
        ],
        limitations: [],
        disclaimer: DISCLAIMER,
      }),
    ).toThrow(/enabled heads/i);
  });
});
