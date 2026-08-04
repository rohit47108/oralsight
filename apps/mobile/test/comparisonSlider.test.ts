import { describe, expect, it } from "vitest";

import {
  clampComparisonBlend,
  comparisonBlendAfterDrag,
  comparisonBlendFromTrackPosition,
} from "../src/lib/comparisonSlider";

describe("comparison slider", () => {
  it("converts a track position to a bounded blend", () => {
    expect(comparisonBlendFromTrackPosition(50, 200)).toBe(0.25);
    expect(comparisonBlendFromTrackPosition(-10, 200)).toBe(0);
    expect(comparisonBlendFromTrackPosition(240, 200)).toBe(1);
  });

  it("updates continuously from the blend where a drag began", () => {
    expect(comparisonBlendAfterDrag(0.4, 40, 200)).toBeCloseTo(0.6);
    expect(comparisonBlendAfterDrag(0.1, -80, 200)).toBe(0);
    expect(comparisonBlendAfterDrag(0.9, 80, 200)).toBe(1);
  });

  it("fails safely for invalid measurements", () => {
    expect(comparisonBlendFromTrackPosition(20, 0)).toBe(0.5);
    expect(comparisonBlendAfterDrag(0.3, 20, Number.NaN)).toBe(0.3);
    expect(clampComparisonBlend(Number.NaN)).toBe(0.5);
  });
});
