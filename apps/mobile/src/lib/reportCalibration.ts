import type { CaptureRecord } from "../types";

export interface ValidReportCalibration {
  status: "valid";
  measurementLabel: "calibrated estimate";
  cardVersion: string;
  markerId: string;
  referenceWidthMm: number;
  millimetersPerPixel: number;
  estimatedWidthMm: number | null;
  estimatedHeightMm: number | null;
  estimatedAreaMm2: number | null;
  confidence: number;
  calibratedAt: string;
  modelVersions: Record<string, string>;
}

export interface SuppressedReportCalibration {
  status: "not_attempted" | "invalid" | "unavailable";
  gateReasons: string[];
}

export type ReportCalibration =
  ValidReportCalibration | SuppressedReportCalibration;

/** Re-checks the evidence gate before any physical unit reaches a report. */
export function calibrationForReport(
  capture: CaptureRecord,
): ReportCalibration {
  const calibration = capture.calibration;
  if (!calibration) {
    return capture.calibrationRequested
      ? {
          status: "unavailable",
          gateReasons: ["calibration_result_unavailable"],
        }
      : { status: "not_attempted", gateReasons: [] };
  }
  if (calibration.status !== "valid") {
    return {
      status: calibration.status === "invalid" ? "invalid" : "not_attempted",
      gateReasons: [...calibration.gateReasons],
    };
  }
  const completeEvidence =
    calibration.measurementLabel === "calibrated estimate" &&
    calibration.cardVersion !== null &&
    calibration.markerId !== null &&
    calibration.referenceWidthMm !== null &&
    calibration.millimetersPerPixel !== null &&
    calibration.confidence !== null &&
    calibration.calibratedAt !== null &&
    calibration.gateReasons.length === 0 &&
    Object.keys(calibration.modelVersions).length > 0;
  if (!completeEvidence) {
    return {
      status: "unavailable",
      gateReasons: ["calibration_evidence_incomplete"],
    };
  }
  return {
    status: "valid",
    measurementLabel: "calibrated estimate",
    cardVersion: calibration.cardVersion!,
    markerId: calibration.markerId!,
    referenceWidthMm: calibration.referenceWidthMm!,
    millimetersPerPixel: calibration.millimetersPerPixel!,
    estimatedWidthMm: calibration.estimatedWidthMm,
    estimatedHeightMm: calibration.estimatedHeightMm,
    estimatedAreaMm2: calibration.estimatedAreaMm2,
    confidence: calibration.confidence!,
    calibratedAt: calibration.calibratedAt!,
    modelVersions: { ...calibration.modelVersions },
  };
}
