import { describe, expect, it } from "vitest";
import type { QualityResult } from "@oralsight/contracts";

import {
  selectBestSweepFrames,
  sweepFrameRequests,
  sweepInstruction,
} from "../src/lib/videoSweep";

const quality = (blurScore: number, accepted = true): QualityResult => ({
  accepted,
  blurScore,
  exposureScore: 0.9,
  glareScore: 0.05,
  obstructionScore: 0.05,
  faceDetected: false,
  reasons: accepted ? [] : ["rejected"],
});

describe("guided video sweep", () => {
  it("samples three frames from each of three guided segments", () => {
    const requests = sweepFrameRequests(6_000);
    expect(requests).toHaveLength(9);
    expect(new Set(requests.map((request) => request.angle))).toEqual(
      new Set(["straight", "left_oblique", "right_oblique"]),
    );
    expect(requests.every((request) => request.timeMs < 6_000)).toBe(true);
  });

  it("selects the strongest accepted frame for every angle", () => {
    const candidates = [
      { id: "straight-low", angle: "straight" as const, quality: quality(0.6) },
      {
        id: "straight-best",
        angle: "straight" as const,
        quality: quality(0.95),
      },
      {
        id: "left-rejected",
        angle: "left_oblique" as const,
        quality: quality(1, false),
      },
      {
        id: "left-best",
        angle: "left_oblique" as const,
        quality: quality(0.8),
      },
      {
        id: "right-best",
        angle: "right_oblique" as const,
        quality: quality(0.82),
      },
    ];
    expect(
      selectBestSweepFrames(candidates).map((candidate) => candidate.id),
    ).toEqual(["straight-best", "left-best", "right-best"]);
  });

  it("gives a short direction for each third of the sweep", () => {
    expect(sweepInstruction(0.1)).toContain("straight");
    expect(sweepInstruction(0.5)).toContain("left");
    expect(sweepInstruction(0.9)).toContain("right");
  });

  it("rejects sweeps too short for three useful segments", () => {
    expect(() => sweepFrameRequests(2_000)).toThrow(/2.5/);
  });
});
