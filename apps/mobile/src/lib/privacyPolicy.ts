import type { SanitizedCapture } from "@/lib/imagePipeline";

export function withFaceDetectionResult(
  capture: SanitizedCapture,
  faceDetected: boolean,
): SanitizedCapture {
  return {
    ...capture,
    telemetry: {
      ...capture.telemetry,
      faceDetected,
    },
  };
}
