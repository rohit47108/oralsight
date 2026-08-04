import { describe, expect, it } from "vitest";

import { TRANSPORT_IMAGE_BYTE_LIMIT } from "../src/constants";
import { evaluateImageTelemetry } from "../src/lib/quality";

describe("capture quality gate", () => {
  it("accepts a stable, visible, evenly lit frame", () => {
    const result = evaluateImageTelemetry({
      edgeStrength: 0.2,
      focusVariance: 0.02,
      meanLuminance: 0.55,
      highlightFraction: 0.01,
      obstructionEstimate: 0.02,
      faceDetected: false,
      stable: true,
    });
    expect(result.accepted).toBe(true);
    expect(result.reasons).toEqual([]);
    expect(result.glareScore).toBeCloseTo(0.05);
    expect(result.obstructionScore).toBeCloseTo(0.02);
  });

  it("rejects before persistence when motion, blur, glare, or a face is present", () => {
    const result = evaluateImageTelemetry({
      edgeStrength: 0.2,
      focusVariance: 0.001,
      meanLuminance: 0.95,
      highlightFraction: 0.4,
      obstructionEstimate: 0.8,
      faceDetected: true,
      stable: false,
    });
    expect(result.accepted).toBe(false);
    expect(result.reasons.length).toBeGreaterThanOrEqual(5);
    expect(result.glareScore).toBe(1);
    expect(result.obstructionScore).toBeCloseTo(0.8);
    expect(result.blurScore).toBeLessThan(0.42);
  });

  it("rejects low-resolution, extreme-aspect, or oversized sanitized images", () => {
    const base = {
      edgeStrength: 0.2,
      focusVariance: 0.02,
      meanLuminance: 0.55,
      highlightFraction: 0.01,
      obstructionEstimate: 0.02,
      faceDetected: false,
      stable: true,
    };
    expect(
      evaluateImageTelemetry({ ...base, width: 320, height: 240 }),
    ).toMatchObject({ accepted: false });
    expect(
      evaluateImageTelemetry({ ...base, width: 3000, height: 500 }),
    ).toMatchObject({ accepted: false });
    expect(
      evaluateImageTelemetry({
        ...base,
        width: 1200,
        height: 1200,
        byteSize: TRANSPORT_IMAGE_BYTE_LIMIT + 1,
      }),
    ).toMatchObject({ accepted: false });
  });

  it("leaves room for two images inside the Vercel request-body ceiling", () => {
    const reservedMultipartBytes = 500_000;
    expect(
      2 * TRANSPORT_IMAGE_BYTE_LIMIT + reservedMultipartBytes,
    ).toBeLessThan(4_500_000);
  });
});
