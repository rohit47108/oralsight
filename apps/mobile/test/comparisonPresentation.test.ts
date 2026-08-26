import { describe, expect, it } from "vitest";

import {
  buildDisplayRegistrationMatrix,
  buildMaskTimelineGeometry,
  containedImageRect,
  projectRegisteredPoint,
  type ComparisonRegistrationAlignment,
} from "../src/lib/comparisonPresentation";

const identityAlignment: ComparisonRegistrationAlignment = {
  method: "orb_ransac_homography",
  coordinateSpace: "normalized_image_coordinates",
  mapsFrom: "current",
  mapsTo: "baseline",
  matrix: [1, 0, 0, 0, 1, 0, 0, 0, 1],
  sourceImageSize: { widthPx: 400, heightPx: 200 },
  targetImageSize: { widthPx: 400, heightPx: 200 },
};

describe("comparison presentation", () => {
  it("fits an image inside the comparison frame without stretching it", () => {
    expect(
      containedImageRect(
        { width: 300, height: 240 },
        { widthPx: 400, heightPx: 200 },
      ),
    ).toEqual({ left: 0, top: 45, width: 300, height: 150 });
  });

  it("builds a display homography that maps current pixels into the baseline frame", () => {
    const translated: ComparisonRegistrationAlignment = {
      ...identityAlignment,
      matrix: [1, 0, 0.1, 0, 1, 0.2, 0, 0, 1],
    };
    const result = buildDisplayRegistrationMatrix(
      { width: 300, height: 240 },
      translated,
    );

    expect(result).not.toBeNull();
    expect(result?.sourceRect).toEqual({
      left: 0,
      top: 45,
      width: 300,
      height: 150,
    });
    expect(result?.targetRect).toEqual(result?.sourceRect);
    // React Native's 9-value matrix is column-major. A normalized +0.1,
    // +0.2 translation therefore becomes +30 px, +30 px in this frame.
    expect(result?.matrix).toEqual([1, 0, 0, 0, 1, 0, 30, 75, 1]);
  });

  it("rejects a singular or directionally mismatched registration", () => {
    expect(
      buildDisplayRegistrationMatrix(
        { width: 300, height: 240 },
        { ...identityAlignment, mapsFrom: "baseline" as "current" },
      ),
    ).toBeNull();
    expect(
      buildDisplayRegistrationMatrix(
        { width: 300, height: 240 },
        { ...identityAlignment, matrix: [1, 0, 0, 0, 0, 0, 0, 0, 0] },
      ),
    ).toBeNull();
  });

  it("projects current mask points through the supplied registration", () => {
    const translated: ComparisonRegistrationAlignment = {
      ...identityAlignment,
      matrix: [1, 0, 0.1, 0, 1, -0.1, 0, 0, 1],
    };

    expect(projectRegisteredPoint([0.25, 0.5], translated)).toEqual([
      0.35, 0.4,
    ]);
  });

  it("morphs registered candidate-mask outlines at chronological progress", () => {
    const baseline = {
      polygon: [
        [0.1, 0.1],
        [0.3, 0.1],
        [0.3, 0.3],
        [0.1, 0.3],
      ] as [number, number][],
    };
    const current = {
      polygon: [
        [0.2, 0.2],
        [0.4, 0.2],
        [0.4, 0.4],
        [0.2, 0.4],
      ] as [number, number][],
    };
    const geometry = buildMaskTimelineGeometry(
      baseline,
      current,
      0.5,
      identityAlignment,
      16,
    );

    expect(geometry.kind).toBe("morph");
    expect(geometry.morphed).toHaveLength(16);
    expect(geometry.morphed?.[0]?.[0]).toBeCloseTo(0.15);
    expect(geometry.morphed?.[0]?.[1]).toBeCloseTo(0.15);
  });

  it("uses an honest mask crossfade rather than spatial morphing without registration", () => {
    const baseline = {
      polygon: [
        [0.1, 0.1],
        [0.3, 0.1],
        [0.2, 0.3],
      ] as [number, number][],
    };
    const current = {
      polygon: [
        [0.2, 0.2],
        [0.4, 0.2],
        [0.3, 0.4],
      ] as [number, number][],
    };
    const geometry = buildMaskTimelineGeometry(baseline, current, 0.25, null);

    expect(geometry).toMatchObject({
      kind: "crossfade",
      morphed: null,
      baselineOpacity: 0.75,
      currentOpacity: 0.25,
    });
  });
});
