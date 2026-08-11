import { describe, expect, it } from "vitest";
import type { AnalysisResult } from "@oralsight/contracts";

import {
  buildObservationReplayFrames,
  buildRegionObservationSummaries,
  derivePinWorldPosition,
  deriveRegionWorldPosition,
  deriveScanPhonePose,
  nextScanPathRegion,
  scanPathCue,
} from "../src/lib/observationMap";
import type { CaptureRecord, ObservationPin } from "../src/types";

const quality = (accepted = true) => ({
  accepted,
  blurScore: accepted ? 0.9 : 0.1,
  exposureScore: 0.9,
  glareScore: 0.05,
  obstructionScore: 0.05,
  faceDetected: false,
  reasons: accepted ? [] : ["blur"],
});

const capture = (
  id: string,
  sessionId: string,
  capturedAt: string,
  region: CaptureRecord["region"] = "dorsal_tongue",
  inputOrigin: CaptureRecord["inputOrigin"] = "live_capture",
  accepted = true,
): CaptureRecord => ({
  id,
  sessionId,
  region,
  angle: "primary",
  mediaKind: "image",
  capturedAt,
  encryptedUri: `${id}.osv`,
  mimeType: "image/jpeg",
  inputOrigin,
  quality: quality(accepted),
});

const analysis = (
  captureId: string,
  region: AnalysisResult["region"],
  confidence: number,
): AnalysisResult => ({
  contractVersion: "1.1.0",
  captureId,
  region,
  quality: quality(),
  anatomyPrediction: {
    region,
    confidence: 0.92,
    supported: true,
    selectedRegionMatches: true,
  },
  candidateMask: null,
  descriptors: null,
  appearanceOutput: null,
  diseaseResearchOutput: null,
  uncertainty: {
    overallConfidence: confidence,
    imageQualityConfidence: 0.9,
    datasetSimilarity: null,
    modelAgreement: null,
    limitations: [],
  },
  abstentionReasons: [],
  modelVersions: { segmentation: "test" },
  inputOrigin: "live_capture",
  analysisOrigin: "live_model",
  status: "complete",
  disclaimer: "This result is not a diagnosis.",
});

const pin = (
  id: string,
  firstObservedAt: string,
  captureIds: string[],
  status: ObservationPin["status"] = "monitoring",
): ObservationPin => ({
  id,
  region: "dorsal_tongue",
  meshId: "tongue_dorsal",
  uvX: 0.75,
  uvY: 0.25,
  assetVersion: "procedural-v1",
  userConfirmed: true,
  firstObservedAt,
  status,
  captureIds,
});

describe("oral observation map model", () => {
  it("personalizes coverage only from accepted live captures", () => {
    const captures = [
      capture("live-1", "session-1", "2026-07-01T10:00:00.000Z"),
      capture("live-2", "session-2", "2026-07-08T10:00:00.000Z"),
      capture(
        "demo",
        "session-demo",
        "2026-07-09T10:00:00.000Z",
        "upper_lip",
        "bundled_demo",
      ),
      capture(
        "rejected",
        "session-3",
        "2026-07-10T10:00:00.000Z",
        "lower_lip",
        "live_capture",
        false,
      ),
    ];
    const summaries = buildRegionObservationSummaries(
      captures,
      {
        "live-1": analysis("live-1", "dorsal_tongue", 0.7),
        "live-2": analysis("live-2", "dorsal_tongue", 0.9),
      },
      [
        pin("pin-live", "2026-07-01T10:00:00.000Z", ["live-1"]),
        pin("pin-demo", "2026-07-09T10:00:00.000Z", ["demo"]),
      ],
    );

    expect(summaries.dorsal_tongue.acceptedCaptureCount).toBe(2);
    expect(summaries.dorsal_tongue.averageAnalysisConfidence).toBeCloseTo(0.8);
    expect(summaries.dorsal_tongue.confirmedPinCount).toBe(1);
    expect(summaries.upper_lip.acceptedCaptureCount).toBe(0);
    expect(summaries.lower_lip.acceptedCaptureCount).toBe(0);
    expect(summaries.lower_lip.rejectedCaptureCount).toBe(1);
    expect(summaries.lower_lip.retakeRequiredCount).toBe(1);
  });

  it("derives the personal scan-status layer only from live confirmed history", () => {
    const live = capture(
      "live",
      "session",
      "2026-07-01T10:00:00.000Z",
      "dorsal_tongue",
    );
    const summaries = buildRegionObservationSummaries([live], {}, [
      pin("changed", "2026-07-01T10:00:00.000Z", ["live"], "visually_changed"),
    ]);

    expect(summaries.dorsal_tongue.confirmedPinCount).toBe(1);
    expect(summaries.dorsal_tongue.visuallyChangedPinCount).toBe(1);
    expect(summaries.dorsal_tongue.retakeRequiredCount).toBe(0);
  });

  it("builds chronological cumulative replay frames and date-gates pins", () => {
    const captures = [
      capture("later", "session-2", "2026-07-08T10:00:00.000Z"),
      capture("earlier", "session-1", "2026-07-01T10:00:00.000Z", "upper_lip"),
    ];
    const frames = buildObservationReplayFrames(captures, {}, [
      pin("later-pin", "2026-07-08T10:00:00.000Z", ["later"]),
    ]);

    expect(frames).toHaveLength(2);
    expect(frames[0]?.sessionId).toBe("session-1");
    expect(frames[0]?.completedRegions).toEqual(["upper_lip"]);
    expect(frames[0]?.visiblePinIds).toEqual([]);
    expect(frames[1]?.completedRegions).toEqual(["dorsal_tongue", "upper_lip"]);
    expect(frames[1]?.visiblePinIds).toEqual(["later-pin"]);
  });

  it("derives render coordinates from region and UV data without persisting them", () => {
    expect(deriveRegionWorldPosition("left_buccal_mucosa", false)).toEqual([
      -1.02, 0, 0,
    ]);
    expect(deriveRegionWorldPosition("left_buccal_mucosa", true)).toEqual([
      -1.4, 0, 0,
    ]);
    const pinPosition = derivePinWorldPosition(
      { region: "dorsal_tongue", uvX: 0.75, uvY: 0.25 },
      false,
    );
    expect(pinPosition[0]).toBeCloseTo(0.186875);
    expect(pinPosition[1]).toBeCloseTo(-0.243);
    expect(pinPosition[2]).toBeCloseTo(0.735);
  });

  it("starts the scan path at the first missing region and wraps", () => {
    expect(nextScanPathRegion(["dorsal_tongue"], null, 1)).toBe(
      "ventral_tongue",
    );
    expect(nextScanPathRegion([], "lower_dental_arch", 1)).toBe(
      "dorsal_tongue",
    );
  });

  it("provides deterministic phone poses and plain scan-path instructions", () => {
    expect(deriveScanPhonePose("right_buccal_mucosa")).toEqual({
      position: [1.72, 0.02, 1.18],
      rotation: [0, -0.52, -0.12],
    });
    expect(scanPathCue("ventral_tongue")).toMatchObject({
      camera: "Rear camera recommended",
      helperRecommended: true,
    });
  });
});
