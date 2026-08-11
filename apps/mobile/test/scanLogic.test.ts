import { describe, expect, it } from "vitest";
import {
  MOUTH_REGIONS,
  type ComparisonResult,
  type QualityResult,
} from "@oralsight/contracts";

import {
  detailedScanProgress,
  comparisonsWithoutCaptureIds,
  scanProgress,
} from "../src/lib/scanLogic";
import type { CaptureRecord } from "../src/types";

const ACCEPTED_TEST_QUALITY: QualityResult = {
  accepted: true,
  blurScore: 0.91,
  exposureScore: 0.86,
  glareScore: 0.01,
  obstructionScore: 0.02,
  faceDetected: false,
  reasons: [],
};

describe("eight-region completeness", () => {
  it("requires one accepted capture for every canonical region", () => {
    const captures: CaptureRecord[] = MOUTH_REGIONS.map((region) => ({
      id: region,
      sessionId: "s1",
      region,
      angle: "primary",
      mediaKind: "image",
      capturedAt: "2026-07-21T00:00:00.000Z",
      encryptedUri: null,
      mimeType: "image/png",
      inputOrigin: "live_capture",
      quality: ACCEPTED_TEST_QUALITY,
    }));
    expect(scanProgress(captures, "s1")).toMatchObject({
      completed: 8,
      total: 8,
      percent: 1,
      missing: [],
    });
  });

  it("does not count rejected or duplicate captures", () => {
    const rejected = {
      ...ACCEPTED_TEST_QUALITY,
      accepted: false,
      reasons: ["blur"],
    };
    const captures: CaptureRecord[] = [
      {
        id: "a",
        sessionId: "s1",
        region: "dorsal_tongue",
        angle: "primary",
        mediaKind: "image",
        capturedAt: "2026-07-21T00:00:00.000Z",
        encryptedUri: null,
        mimeType: "image/png",
        inputOrigin: "live_capture",
        quality: ACCEPTED_TEST_QUALITY,
      },
      {
        id: "b",
        sessionId: "s1",
        region: "dorsal_tongue",
        angle: "primary",
        mediaKind: "image",
        capturedAt: "2026-07-21T00:00:01.000Z",
        encryptedUri: null,
        mimeType: "image/png",
        inputOrigin: "live_capture",
        quality: ACCEPTED_TEST_QUALITY,
      },
      {
        id: "c",
        sessionId: "s1",
        region: "ventral_tongue",
        angle: "primary",
        mediaKind: "image",
        capturedAt: "2026-07-21T00:00:02.000Z",
        encryptedUri: null,
        mimeType: "image/png",
        inputOrigin: "live_capture",
        quality: rejected,
      },
    ];
    expect(scanProgress(captures, "s1").completed).toBe(1);
  });

  it("does not let an oblique-only view complete a canonical region", () => {
    const captures: CaptureRecord[] = [
      {
        id: "oblique-only",
        sessionId: "s1",
        region: "dorsal_tongue",
        angle: "left_oblique",
        mediaKind: "image",
        capturedAt: "2026-07-21T00:00:00.000Z",
        encryptedUri: null,
        mimeType: "image/png",
        inputOrigin: "live_capture",
        quality: ACCEPTED_TEST_QUALITY,
      },
    ];

    expect(scanProgress(captures, "s1")).toMatchObject({
      completed: 0,
      missing: expect.arrayContaining(["dorsal_tongue"]),
    });
  });

  it("tracks all 24 required views in a detailed multi-angle scan", () => {
    const angles = ["straight", "left_oblique", "right_oblique"] as const;
    const captures: CaptureRecord[] = MOUTH_REGIONS.flatMap((region) =>
      angles.map((angle) => ({
        id: `${region}-${angle}`,
        sessionId: "s1",
        region,
        angle,
        mediaKind: "image" as const,
        capturedAt: "2026-07-21T00:00:00.000Z",
        encryptedUri: null,
        mimeType: "image/png" as const,
        inputOrigin: "live_capture" as const,
        quality: ACCEPTED_TEST_QUALITY,
      })),
    );

    expect(
      detailedScanProgress(captures, "s1", "detailed_multi_angle"),
    ).toMatchObject({
      completedViews: 24,
      totalViews: 24,
      completeRegions: 8,
    });
  });

  it("requires the same three traceable angles for a guided sweep", () => {
    const captures: CaptureRecord[] = [
      {
        id: "straight",
        sessionId: "s1",
        region: "lower_lip",
        angle: "straight",
        mediaKind: "video_frame",
        capturedAt: "2026-07-21T00:00:00.000Z",
        encryptedUri: null,
        mimeType: "image/jpeg",
        inputOrigin: "live_capture",
        captureSource: "video_sweep",
        sourceVideoDurationMs: 6_000,
        frameTimeMs: 1_000,
        quality: ACCEPTED_TEST_QUALITY,
      },
      {
        id: "left",
        sessionId: "s1",
        region: "lower_lip",
        angle: "left_oblique",
        mediaKind: "video_frame",
        capturedAt: "2026-07-21T00:00:01.000Z",
        encryptedUri: null,
        mimeType: "image/jpeg",
        inputOrigin: "live_capture",
        captureSource: "video_sweep",
        sourceVideoDurationMs: 6_000,
        frameTimeMs: 3_000,
        quality: ACCEPTED_TEST_QUALITY,
      },
    ];

    const progress = detailedScanProgress(captures, "s1", "guided_video_sweep");
    expect(progress.completedViews).toBe(2);
    expect(progress.missingByRegion.lower_lip).toEqual(["right_oblique"]);
  });
});

describe("capture replacement cleanup", () => {
  it("purges comparisons that reference a superseded capture", () => {
    const comparison = (baselineCaptureId: string, currentCaptureId: string) =>
      ({ baselineCaptureId, currentCaptureId }) as ComparisonResult;
    const comparisons = [
      comparison("old", "current"),
      comparison("baseline", "old"),
      comparison("baseline", "current"),
    ];

    expect(
      comparisonsWithoutCaptureIds(comparisons, ["old"]).map((item) => [
        item.baselineCaptureId,
        item.currentCaptureId,
      ]),
    ).toEqual([["baseline", "current"]]);
  });
});
