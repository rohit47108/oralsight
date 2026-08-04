import { describe, expect, it } from "vitest";
import type { ComparisonResult } from "@oralsight/contracts";

import { pinsAfterConfirmedComparison } from "../src/lib/observationPins";
import type { CaptureRecord, ObservationPin } from "../src/types";

const capture = (id: string, capturedAt: string): CaptureRecord => ({
  id,
  sessionId: id,
  region: "dorsal_tongue",
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
    expect(pin?.uvX).toBe(0.4);
  });

  it("marks a material comparable change without implying a diagnosis", () => {
    const [pin] = pinsAfterConfirmedComparison(
      [confirmedPin],
      captures,
      comparison(0.22),
    );

    expect(pin?.status).toBe("visually_changed");
  });
});
