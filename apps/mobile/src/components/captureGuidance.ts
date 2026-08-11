export interface MotionSample {
  x: number;
  y: number;
  z: number;
}

export type CaptureGuidanceSource =
  "live_camera" | "sweep_start" | "imported_photo";

export interface CaptureGuidanceSnapshot {
  stabilityPercent: number | null;
  tiltDegrees: number | null;
  rotationDegrees: number | null;
  targetWidthPercent: number;
  source: CaptureGuidanceSource;
}

export interface CaptureReplayComparison {
  angleSimilarity: number | null;
  rotationSimilarity: number | null;
  lightingSimilarity: number | null;
  calibratedScaleSimilarity: number | null;
  overallSimilarity: number | null;
  unavailableReasons: string[];
}

const clamp = (value: number, minimum: number, maximum: number) =>
  Math.min(maximum, Math.max(minimum, value));

const round = (value: number, decimals = 1) => {
  const factor = 10 ** decimals;
  const rounded = Math.round(value * factor) / factor;
  return Object.is(rounded, -0) ? 0 : rounded;
};

const finiteOrNull = (value: number | null | undefined): number | null =>
  typeof value === "number" && Number.isFinite(value) ? value : null;

const similarityFromDifference = (
  difference: number,
  maximumUsefulDifference: number,
): number => round(clamp(1 - difference / maximumUsefulDifference, 0, 1), 3);

const angularDifference = (left: number, right: number): number => {
  const difference = Math.abs(left - right) % 360;
  return Math.min(difference, 360 - difference);
};

export function deriveDeviceOrientation(sample: MotionSample): {
  tiltDegrees: number;
  rotationDegrees: number;
} {
  const tiltDegrees =
    (Math.atan2(-sample.x, Math.hypot(sample.y, sample.z)) * 180) / Math.PI;
  const rotationDegrees = (Math.atan2(sample.y, sample.z) * 180) / Math.PI;
  return {
    tiltDegrees: round(tiltDegrees),
    rotationDegrees: round(rotationDegrees),
  };
}

export function createCaptureGuidanceSnapshot(input: {
  motion: MotionSample | null;
  stability: number;
  sensorAvailable: boolean | null;
  targetWidthPercent: number;
  source: CaptureGuidanceSource;
}): CaptureGuidanceSnapshot {
  const orientation =
    input.sensorAvailable === true && input.motion
      ? deriveDeviceOrientation(input.motion)
      : null;
  return {
    stabilityPercent:
      input.sensorAvailable === true
        ? Math.round(clamp(input.stability, 0, 1) * 100)
        : null,
    tiltDegrees: orientation?.tiltDegrees ?? null,
    rotationDegrees: orientation?.rotationDegrees ?? null,
    targetWidthPercent: Math.round(clamp(input.targetWidthPercent, 1, 100)),
    source: input.source,
  };
}

export function signedDegrees(value: number | null): string {
  if (value === null) return "Unavailable";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(1)}°`;
}

/**
 * Compares capture conditions without claiming anatomical registration. Angle
 * and rotation come from the device IMU, lighting comes from the post-capture
 * exposure check, and scale is available only when both captures passed the
 * same physical-marker calibration path.
 */
export function compareCaptureGuidance(input: {
  baselineSnapshot: CaptureGuidanceSnapshot | null;
  currentSnapshot: CaptureGuidanceSnapshot | null;
  baselineExposureScore?: number | null;
  currentExposureScore?: number | null;
  baselineMillimetersPerPixel?: number | null;
  currentMillimetersPerPixel?: number | null;
}): CaptureReplayComparison {
  const unavailableReasons: string[] = [];
  const baselineTilt = finiteOrNull(input.baselineSnapshot?.tiltDegrees);
  const currentTilt = finiteOrNull(input.currentSnapshot?.tiltDegrees);
  const angleSimilarity =
    baselineTilt === null || currentTilt === null
      ? null
      : similarityFromDifference(
          angularDifference(baselineTilt, currentTilt),
          30,
        );
  if (angleSimilarity === null) {
    unavailableReasons.push("angle_requires_two_device_readings");
  }

  const baselineRotation = finiteOrNull(
    input.baselineSnapshot?.rotationDegrees,
  );
  const currentRotation = finiteOrNull(input.currentSnapshot?.rotationDegrees);
  const rotationSimilarity =
    baselineRotation === null || currentRotation === null
      ? null
      : similarityFromDifference(
          angularDifference(baselineRotation, currentRotation),
          30,
        );
  if (rotationSimilarity === null) {
    unavailableReasons.push("rotation_requires_two_device_readings");
  }

  const baselineExposure = finiteOrNull(input.baselineExposureScore);
  const currentExposure = finiteOrNull(input.currentExposureScore);
  const lightingSimilarity =
    baselineExposure === null || currentExposure === null
      ? null
      : similarityFromDifference(
          Math.abs(baselineExposure - currentExposure),
          0.35,
        );
  if (lightingSimilarity === null) {
    unavailableReasons.push("lighting_requires_two_exposure_checks");
  }

  const baselineScale = finiteOrNull(input.baselineMillimetersPerPixel);
  const currentScale = finiteOrNull(input.currentMillimetersPerPixel);
  const calibratedScaleSimilarity =
    baselineScale === null ||
    currentScale === null ||
    baselineScale <= 0 ||
    currentScale <= 0
      ? null
      : similarityFromDifference(
          Math.abs(currentScale - baselineScale) /
            Math.max(currentScale, baselineScale),
          0.35,
        );
  if (calibratedScaleSimilarity === null) {
    unavailableReasons.push("scale_requires_two_valid_marker_calibrations");
  }

  const available = [
    angleSimilarity,
    rotationSimilarity,
    lightingSimilarity,
    calibratedScaleSimilarity,
  ].filter((value): value is number => value !== null);

  return {
    angleSimilarity,
    rotationSimilarity,
    lightingSimilarity,
    calibratedScaleSimilarity,
    overallSimilarity:
      available.length === 0
        ? null
        : round(
            available.reduce((total, value) => total + value, 0) /
              available.length,
            3,
          ),
    unavailableReasons,
  };
}

export function captureGuidanceSummary(
  snapshot: CaptureGuidanceSnapshot,
  exposureScore: number | null,
): string {
  const stability =
    snapshot.stabilityPercent === null
      ? "stability unavailable"
      : `stability ${snapshot.stabilityPercent} percent`;
  const exposure =
    exposureScore === null
      ? "exposure measured after capture"
      : `exposure pass score ${Math.round(clamp(exposureScore, 0, 1) * 100)} percent`;
  return [
    stability,
    `device tilt ${signedDegrees(snapshot.tiltDegrees)}`,
    `device rotation ${signedDegrees(snapshot.rotationDegrees)}`,
    exposure,
    `distance proxy target ${snapshot.targetWidthPercent} percent of guide width`,
  ].join(". ");
}
