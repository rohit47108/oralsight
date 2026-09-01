import { describe, expect, it } from "vitest";
import type { CaptureRecord } from "../src/types";

import { calibrationForReport } from "../src/lib/reportCalibration";

const baseCapture: CaptureRecord = {
  id: "11111111-1111-4111-8111-111111111111",
  sessionId: "22222222-2222-4222-8222-222222222222",
  region: "dorsal_tongue",
  angle: "primary",
  mediaKind: "image",
  capturedAt: "2026-08-06T20:00:00.000Z",
  encryptedUri: null,
  mimeType: "image/jpeg",
  inputOrigin: "live_capture",
  quality: {
    accepted: true,
    blurScore: 0.9,
    exposureScore: 0.9,
    glareScore: 0.1,
    obstructionScore: 0.1,
    faceDetected: false,
    reasons: [],
  },
};

describe("report physical calibration gate", () => {
  it("keeps millimeter values unavailable when calibration was not attempted", () => {
    expect(calibrationForReport(baseCapture)).toEqual({
      status: "not_attempted",
      gateReasons: [],
    });
  });

  it("suppresses invalid calibration and retains its gate reasons", () => {
    const result = calibrationForReport({
      ...baseCapture,
      calibrationRequested: true,
      calibration: {
        calibrationId: "33333333-3333-4333-8333-333333333333",
        captureViewId: baseCapture.id,
        status: "invalid",
        method: "versioned_reference_card",
        cardVersion: "stoma3d-calibration-v1",
        markerId: null,
        referenceWidthMm: null,
        millimetersPerPixel: null,
        estimatedWidthMm: null,
        estimatedHeightMm: null,
        estimatedAreaMm2: null,
        confidence: null,
        gateReasons: ["marker_not_found"],
        calibratedAt: null,
        modelVersions: { calibration: "aruco-v1" },
        measurementLabel: "calibrated estimate",
      },
    });
    expect(result).toEqual({
      status: "invalid",
      gateReasons: ["marker_not_found"],
    });
    expect(result).not.toHaveProperty("estimatedAreaMm2");
  });

  it("exposes estimates only with complete passing evidence", () => {
    const result = calibrationForReport({
      ...baseCapture,
      calibrationRequested: true,
      calibration: {
        calibrationId: "33333333-3333-4333-8333-333333333333",
        captureViewId: baseCapture.id,
        status: "valid",
        method: "versioned_reference_card",
        cardVersion: "stoma3d-calibration-v1",
        markerId: "17",
        referenceWidthMm: 20,
        millimetersPerPixel: 0.08,
        estimatedWidthMm: 4.2,
        estimatedHeightMm: 2.8,
        estimatedAreaMm2: 9.7,
        confidence: 0.91,
        gateReasons: [],
        calibratedAt: "2026-08-06T20:00:01.000Z",
        modelVersions: { calibration: "aruco-v1" },
        measurementLabel: "calibrated estimate",
      },
    });
    expect(result.status).toBe("valid");
    if (result.status === "valid") {
      expect(result.measurementLabel).toBe("calibrated estimate");
      expect(result.estimatedWidthMm).toBe(4.2);
      expect(result.estimatedHeightMm).toBe(2.8);
      expect(result.estimatedAreaMm2).toBe(9.7);
      expect(result.confidence).toBe(0.91);
    }
  });
});
