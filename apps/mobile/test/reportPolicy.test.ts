import { describe, expect, it } from "vitest";
import type { QualityResult } from "@oralsight/contracts";

import { reportContainsSyntheticData } from "../src/lib/reportPolicy";
import type { CaptureRecord, ScanSession } from "../src/types";

const ACCEPTED_TEST_QUALITY: QualityResult = {
  accepted: true,
  blurScore: 0.91,
  exposureScore: 0.86,
  glareScore: 0.01,
  obstructionScore: 0.02,
  faceDetected: false,
  reasons: [],
};

const session = (demo: boolean): ScanSession => ({
  id: demo ? "demo" : "live",
  createdAt: "2026-07-22T00:00:00.000Z",
  demo,
  label: demo ? "Demo" : "Live",
});

const capture = (inputOrigin: CaptureRecord["inputOrigin"]): CaptureRecord => ({
  id: "capture",
  sessionId: "live",
  region: "left_buccal_mucosa",
  capturedAt: "2026-07-22T00:00:00.000Z",
  encryptedUri: null,
  mimeType: "image/png",
  inputOrigin,
  quality: ACCEPTED_TEST_QUALITY,
});

describe("report synthetic-data policy", () => {
  it("watermarks demo sessions and any report containing bundled input", () => {
    expect(reportContainsSyntheticData(session(true), [])).toBe(true);
    expect(
      reportContainsSyntheticData(session(false), [capture("bundled_demo")]),
    ).toBe(true);
    expect(
      reportContainsSyntheticData(session(false), [capture("live_capture")]),
    ).toBe(false);
  });
});
