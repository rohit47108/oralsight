import { describe, expect, it } from "vitest";

import {
  captureGuidanceSummary,
  compareCaptureGuidance,
  createCaptureGuidanceSnapshot,
  deriveDeviceOrientation,
  signedDegrees,
} from "../src/components/captureGuidance";

describe("capture guidance measurements", () => {
  it("derives signed device orientation from gravity without inventing distance", () => {
    expect(deriveDeviceOrientation({ x: 0, y: 0, z: 1 })).toEqual({
      tiltDegrees: 0,
      rotationDegrees: 0,
    });
    const tilted = deriveDeviceOrientation({ x: -0.5, y: 0.5, z: 0.707 });
    expect(tilted.tiltDegrees).toBeGreaterThan(20);
    expect(tilted.rotationDegrees).toBeGreaterThan(20);
  });

  it("scores matching follow-up conditions from real saved readings", () => {
    const snapshot = createCaptureGuidanceSnapshot({
      motion: { x: 0, y: 0, z: 1 },
      stability: 0.95,
      sensorAvailable: true,
      targetWidthPercent: 62,
      source: "live_camera",
    });
    expect(
      compareCaptureGuidance({
        baselineSnapshot: snapshot,
        currentSnapshot: snapshot,
        baselineExposureScore: 0.8,
        currentExposureScore: 0.8,
        baselineMillimetersPerPixel: 0.05,
        currentMillimetersPerPixel: 0.05,
      }),
    ).toEqual({
      angleSimilarity: 1,
      rotationSimilarity: 1,
      lightingSimilarity: 1,
      calibratedScaleSimilarity: 1,
      overallSimilarity: 1,
      unavailableReasons: [],
    });
  });

  it("uses bounded, understandable tolerances for follow-up matching", () => {
    const comparison = compareCaptureGuidance({
      baselineSnapshot: {
        stabilityPercent: 90,
        tiltDegrees: 0,
        rotationDegrees: 10,
        targetWidthPercent: 60,
        source: "live_camera",
      },
      currentSnapshot: {
        stabilityPercent: 92,
        tiltDegrees: 15,
        rotationDegrees: -5,
        targetWidthPercent: 60,
        source: "live_camera",
      },
      baselineExposureScore: 0.8,
      currentExposureScore: 0.625,
      baselineMillimetersPerPixel: 0.05,
      currentMillimetersPerPixel: 0.06,
    });
    expect(comparison.angleSimilarity).toBe(0.5);
    expect(comparison.rotationSimilarity).toBe(0.5);
    expect(comparison.lightingSimilarity).toBe(0.5);
    expect(comparison.calibratedScaleSimilarity).toBe(0.524);
    expect(comparison.overallSimilarity).toBe(0.506);
  });

  it("keeps unavailable factors null instead of inventing a score", () => {
    const comparison = compareCaptureGuidance({
      baselineSnapshot: null,
      currentSnapshot: null,
    });
    expect(comparison.overallSimilarity).toBeNull();
    expect(comparison.angleSimilarity).toBeNull();
    expect(comparison.rotationSimilarity).toBeNull();
    expect(comparison.lightingSimilarity).toBeNull();
    expect(comparison.calibratedScaleSimilarity).toBeNull();
    expect(comparison.unavailableReasons).toEqual([
      "angle_requires_two_device_readings",
      "rotation_requires_two_device_readings",
      "lighting_requires_two_exposure_checks",
      "scale_requires_two_valid_marker_calibrations",
    ]);
  });

  it("records numeric sensor readings and a framing-only distance proxy", () => {
    const snapshot = createCaptureGuidanceSnapshot({
      motion: { x: 0.1, y: -0.05, z: 0.99 },
      stability: 0.923,
      sensorAvailable: true,
      targetWidthPercent: 69,
      source: "live_camera",
    });
    expect(snapshot.stabilityPercent).toBe(92);
    expect(snapshot.tiltDegrees).not.toBeNull();
    expect(snapshot.rotationDegrees).not.toBeNull();
    expect(snapshot.targetWidthPercent).toBe(69);
    expect(captureGuidanceSummary(snapshot, 0.84)).toContain(
      "distance proxy target 69 percent of guide width",
    );
    expect(captureGuidanceSummary(snapshot, 0.84)).not.toContain("mm");
  });

  it("marks motion values unavailable for imported photos or missing sensors", () => {
    const snapshot = createCaptureGuidanceSnapshot({
      motion: null,
      stability: 1,
      sensorAvailable: false,
      targetWidthPercent: 54,
      source: "imported_photo",
    });
    expect(snapshot.stabilityPercent).toBeNull();
    expect(snapshot.tiltDegrees).toBeNull();
    expect(snapshot.rotationDegrees).toBeNull();
    expect(signedDegrees(null)).toBe("Unavailable");
    expect(captureGuidanceSummary(snapshot, null)).toContain(
      "exposure measured after capture",
    );
  });
});
