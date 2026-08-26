import type {
  AnalysisResult,
  ComparisonResult,
  InputOrigin,
  MouthRegion,
} from "@oralsight/contracts";

import {
  assertLiveMobileInput,
  assertLiveResultOrigin,
} from "./liveInputPolicy";

export interface ComparisonAnalysisReference {
  captureId: string;
  region: MouthRegion;
  status: AnalysisResult["status"];
  analysisOrigin: AnalysisResult["analysisOrigin"];
  qualityAccepted: boolean;
  candidateNormalizedArea: number | null;
  modelVersions: Record<string, string>;
}

export interface ExpectedComparisonIdentity {
  baselineCaptureId: string;
  currentCaptureId: string;
  region: MouthRegion;
  inputOrigin: InputOrigin;
  userConfirmedMatch: boolean;
  baselineAnalysis: ComparisonAnalysisReference;
  currentAnalysis: ComparisonAnalysisReference;
}

export function assertComparisonRequest(
  input: ExpectedComparisonIdentity,
): void {
  assertLiveMobileInput(input.inputOrigin);
  if (input.baselineCaptureId === input.currentCaptureId) {
    throw new Error("A comparison requires two distinct capture IDs.");
  }
  for (const [label, reference, expectedId] of [
    ["Baseline", input.baselineAnalysis, input.baselineCaptureId],
    ["Current", input.currentAnalysis, input.currentCaptureId],
  ] as const) {
    if (
      reference.captureId !== expectedId ||
      reference.region !== input.region
    ) {
      throw new Error(
        `${label} analysis identity does not match the comparison request.`,
      );
    }
    if (!reference.qualityAccepted) {
      throw new Error(`${label} analysis did not accept image quality.`);
    }
    if (reference.status !== "complete" && reference.status !== "abstained") {
      throw new Error(`${label} analysis is not eligible for comparison.`);
    }
    assertLiveResultOrigin(reference.analysisOrigin);
  }
}

export function assertComparisonResult(
  result: ComparisonResult,
  expected: ExpectedComparisonIdentity,
): void {
  assertComparisonRequest(expected);
  if (
    result.baselineCaptureId !== expected.baselineCaptureId ||
    result.currentCaptureId !== expected.currentCaptureId ||
    result.region !== expected.region ||
    result.inputOrigin !== expected.inputOrigin
  ) {
    throw new Error("Comparison response identity did not match the request.");
  }
  if (result.userConfirmedMatch !== expected.userConfirmedMatch) {
    throw new Error(
      "Comparison response user-confirmation state did not match the request.",
    );
  }
  assertLiveResultOrigin(result.analysisOrigin);
  if (
    !expected.userConfirmedMatch &&
    !result.suppressionReasons.includes("user_confirmation_required")
  ) {
    throw new Error(
      "Unconfirmed comparison response omitted the confirmation-required suppression.",
    );
  }
  if (result.comparable) {
    if (
      !expected.userConfirmedMatch ||
      !result.repeatabilityGatePassed ||
      result.repeatedCaptureAreaError === null ||
      result.analysisOrigin === "unavailable" ||
      result.normalizedChange === null ||
      result.descriptorChanges == null ||
      result.registrationConfidence <= 0 ||
      result.inlierRatio < 0.6 ||
      result.reprojectionErrorRatio > 0.03 ||
      result.suppressionReasons.length > 0
    ) {
      throw new Error(
        "Comparable response did not satisfy registration invariants.",
      );
    }
  } else if (
    result.normalizedChange !== null ||
    result.descriptorChanges != null ||
    result.calibratedMeasurementChanges != null ||
    result.suppressionReasons.length === 0
  ) {
    throw new Error(
      "Suppressed comparison response did not satisfy abstention invariants.",
    );
  }
}
