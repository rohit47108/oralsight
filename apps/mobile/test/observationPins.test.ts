import { describe, expect, it } from "vitest";
import type { ComparisonResult } from "@stoma3d/contracts";

import { pinsAfterConfirmedComparison } from "../src/lib/observationPins";
import type { CaptureRecord, ObservationPin } from "../src/types";

const capture = (id: string, capturedAt: string): CaptureRecord => ({
  id,
  sessionId: id,
  region: "dorsal_tongue",
  angle: "primary",
  mediaKind: "image",
  capturedAt,
  encryptedUri: `${id}.osv`,
  mimeType: "image/jpeg",
  inputOrigin: "live_capture",
  captureSource: "camera",
  privacyConfirmedByUser: true,
  regionConfirmedByUser: true,
  quality: {
    accepted: true,
    blurScore: 1,
    exposureScore: 1,
    glareScore: 0,
    obstructionScore: 0,
    faceDetected: false,
    reasons: [],
  },
});

const comparison = (
  normalizedChange: number | null,
  comparable = normalizedChange !== null,
  descriptorChanges: ComparisonResult["descriptorChanges"] = comparable
    ? {
        normalizedWidthChange: normalizedChange ?? 0,
        normalizedHeightChange: 0,
        normalizedPerimeterChange: normalizedChange ?? 0,
        borderIrregularityChange: 0,
        meanRednessChange: 0,
        meanBrightnessChange: 0,
        textureContrastChange: 0,
        ulcerationLikeContrastChange: null,
        measurementLabel: "approximate image-normalized change",
      }
    : null,
): ComparisonResult => ({
  contractVersion: "1.1.0",
  baselineCaptureId: "earlier",
  currentCaptureId: "later",
  region: "dorsal_tongue",
  candidateMatchScore: null,
  userConfirmedMatch: true,
  registrationConfidence: comparable ? 0.9 : 0.2,
  inlierRatio: comparable ? 0.8 : 0.2,
  reprojectionErrorRatio: comparable ? 0.01 : 0.2,
  normalizedChange,
  descriptorChanges,
  calibratedMeasurementChanges: null,
  calibrationSuppressionReasons: [],
  comparable,
  suppressionReasons: comparable ? [] : ["insufficient_registration_features"],
  modelVersions: {},
  inputOrigin: "live_capture",
  analysisOrigin: comparable ? "live_model" : "unavailable",
  disclaimer: "This result is not a diagnosis.",
});

const confirmedPin: ObservationPin = {
  id: "pin",
  region: "dorsal_tongue",
  meshId: "tongue_dorsal",
  uvX: 0.4,
  uvY: 0.5,
  assetVersion: "procedural-v1",
  userConfirmed: true,
  firstObservedAt: "2026-07-01T00:00:00.000Z",
  status: "review_unavailable",
  captureIds: ["earlier"],
};

const captures = [
  capture("earlier", "2026-07-01T00:00:00.000Z"),
  capture("later", "2026-07-08T00:00:00.000Z"),
];

describe("pinsAfterConfirmedComparison", () => {
  it("does not invent a user-confirmed map pin", () => {
    expect(
      pinsAfterConfirmedComparison([], captures, comparison(null, false)),
    ).toEqual([]);
  });

  it("links an explicitly confirmed pin to both observations", () => {
    const [pin] = pinsAfterConfirmedComparison(
      [confirmedPin],
      captures,
      comparison(0.08),
    );

    expect(pin?.captureIds).toEqual(["earlier", "later"]);
    expect(pin?.status).toBe("stable");
    expect(pin?.comparisonStatus).toBe("stable");
    expect(pin?.uvX).toBe(0.4);
  });

  it("marks a material comparable change without implying a diagnosis", () => {
    const [pin] = pinsAfterConfirmedComparison(
      [confirmedPin],
      captures,
      comparison(0.22),
    );

    expect(pin?.status).toBe("visually_changed");
    expect(pin?.comparisonStatus).toBe("increased_estimated_size");
  });

  it("distinguishes decreased estimated size", () => {
    const [pin] = pinsAfterConfirmedComparison(
      [confirmedPin],
      captures,
      comparison(-0.22),
    );

    expect(pin?.status).toBe("visually_changed");
    expect(pin?.comparisonStatus).toBe("decreased_estimated_size");
  });

  it("distinguishes color or texture change when size is stable", () => {
    const [pin] = pinsAfterConfirmedComparison(
      [confirmedPin],
      captures,
      comparison(0.02, true, {
        normalizedWidthChange: 0.01,
        normalizedHeightChange: 0.01,
        normalizedPerimeterChange: 0.01,
        borderIrregularityChange: 0.01,
        meanRednessChange: 0.11,
        meanBrightnessChange: 0,
        textureContrastChange: 0,
        ulcerationLikeContrastChange: null,
        measurementLabel: "approximate image-normalized change",
      }),
    );

    expect(pin?.comparisonStatus).toBe("color_or_texture_changed");
  });

  it("records insufficient comparison evidence explicitly", () => {
    const [pin] = pinsAfterConfirmedComparison(
      [confirmedPin],
      captures,
      comparison(null, false),
    );

    expect(pin?.status).toBe("review_unavailable");
    expect(pin?.comparisonStatus).toBe("insufficient_comparable_data");
  });
});
