import { describe, expect, it } from "vitest";

import { type SanitizedCapture } from "../src/lib/imagePipeline";
import { withFaceDetectionResult } from "../src/lib/privacyPolicy";

const baseCapture: SanitizedCapture = {
  uri: "file:///temporary/capture.jpg",
  mimeType: "image/jpeg",
  source: "camera",
  width: 1024,
  height: 768,
  byteSize: 1024,
  telemetry: {
    edgeStrength: 0.2,
    meanLuminance: 0.5,
    highlightFraction: 0.01,
    obstructionEstimate: 0.1,
    faceDetected: false,
    stable: true,
  },
};

describe("face detection telemetry", () => {
  it("records a detected face without mutating the sanitized capture", () => {
    const updated = withFaceDetectionResult(baseCapture, true);

    expect(updated.telemetry.faceDetected).toBe(true);
    expect(baseCapture.telemetry.faceDetected).toBe(false);
  });

  it("records a successful no-face result", () => {
    expect(
      withFaceDetectionResult(baseCapture, false).telemetry.faceDetected,
    ).toBe(false);
  });
});
