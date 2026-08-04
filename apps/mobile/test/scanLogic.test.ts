import { describe, expect, it } from "vitest";
import {
  MOUTH_REGIONS,
  type ComparisonResult,
  type QualityResult,
} from "@oralsight/contracts";

import {
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
        capturedAt: "2026-07-21T00:00:02.000Z",
        encryptedUri: null,
        mimeType: "image/png",
        inputOrigin: "live_capture",
        quality: rejected,
      },
    ];
    expect(scanProgress(captures, "s1").completed).toBe(1);
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
