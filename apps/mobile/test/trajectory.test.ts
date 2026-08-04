import { describe, expect, it } from "vitest";
import type {
  AnalysisResult,
  ComparisonResult,
  MouthRegion,
  QualityResult,
} from "@oralsight/contracts";

import {
  buildTrajectorySeries,
  captureQualityScore,
} from "../src/lib/trajectory";

const region: MouthRegion = "dorsal_tongue";
const quality: QualityResult = {
  accepted: true,
  blurScore: 0.9,
  exposureScore: 0.8,
  glareScore: 0.1,
  obstructionScore: 0.05,
  faceDetected: false,
  reasons: [],
};

function analysis(captureId: string, area: number): AnalysisResult {
  return {
    captureId,
    region,
    quality,
    anatomyPrediction: {
      region,
      confidence: 0.93,
      supported: true,
      selectedRegionMatches: true,
    },
    candidateMask: {
      polygon: [
        [0.1, 0.1],
        [0.2, 0.1],
        [0.2, 0.2],
      ],
      boundingBox: [0.1, 0.1, 0.1, 0.1],
      normalizedArea: area,
    },
    descriptors: {
      normalizedArea: area,
      perimeter: 0.4,
      borderIrregularity: 0.1,
      meanRedness: 0.5,
      meanBrightness: 0.5,
      textureContrast: 0.3,
      measurementLabel: "approximate",
    },
    uncertainty: {
      overallConfidence: 0.81,
      imageQualityConfidence: 0.8,
      datasetSimilarity: null,
      modelAgreement: null,
      limitations: ["Approximate."],
    },
    abstentionReasons: [],
    modelVersions: { segmentation: "seg-v1", anatomy: "anatomy-v1" },
    inputOrigin: "live_capture",
    analysisOrigin: "live_model",
    status: "complete",
  };
}

describe("visual trajectory policy", () => {
  it("uses the weakest image-quality factor", () => {
    expect(captureQualityScore(quality)).toBe(0.8);
  });

  it("orders real observations and connects only a passed exact comparison", () => {
    const captures = [
      {
        id: "current",
        region,
        capturedAt: "2026-07-02T00:00:00.000Z",
        inputOrigin: "live_capture" as const,
        quality,
      },
      {
        id: "baseline",
        region,
        capturedAt: "2026-07-01T00:00:00.000Z",
        inputOrigin: "live_capture" as const,
        quality,
      },
    ];
    const comparison = {
      baselineCaptureId: "baseline",
      currentCaptureId: "current",
      region,
      candidateMatchScore: null,
      userConfirmedMatch: true,
      registrationConfidence: 0.9,
      normalizedChange: 0.1,
      comparable: true,
      suppressionReasons: [],
      modelVersions: { registration: "orb-v1" },
      inputOrigin: "live_capture",
      analysisOrigin: "live_model",
    } satisfies ComparisonResult;

    const series = buildTrajectorySeries(
      captures,
      {
        baseline: analysis("baseline", 0.1),
        current: analysis("current", 0.11),
      },
      [comparison],
    );

    expect(series).toHaveLength(1);
    expect(series[0].points.map((point) => point.captureId)).toEqual([
      "baseline",
      "current",
    ]);
    expect(series[0].points[1].comparableFromPrevious).toBe(true);
    expect(
      buildTrajectorySeries(
        captures,
        {
          baseline: analysis("baseline", 0.1),
          current: analysis("current", 0.11),
        },
        [],
      )[0].points[1].comparableFromPrevious,
    ).toBe(false);
  });

  it("excludes sample, failed, and non-live observations", () => {
    const series = buildTrajectorySeries(
      [
        {
          id: "sample",
          region,
          capturedAt: "2026-07-01T00:00:00.000Z",
          inputOrigin: "bundled_demo",
          samplePlaceholder: true,
          quality,
        },
      ],
      { sample: analysis("sample", 0.1) },
      [],
    );
    expect(series).toEqual([]);
  });
});
