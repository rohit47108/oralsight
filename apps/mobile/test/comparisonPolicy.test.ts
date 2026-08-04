import { describe, expect, it } from "vitest";
import type { ComparisonResult } from "@oralsight/contracts";

import {
  assertComparisonResult,
  type ExpectedComparisonIdentity,
} from "../src/lib/comparisonPolicy";

const expected: ExpectedComparisonIdentity = {
  baselineCaptureId: "baseline",
  currentCaptureId: "current",
  region: "left_buccal_mucosa",
  inputOrigin: "live_capture",
  userConfirmedMatch: true,
  baselineAnalysis: {
    captureId: "baseline",
    region: "left_buccal_mucosa",
    status: "complete",
    analysisOrigin: "live_model",
    qualityAccepted: true,
    candidateNormalizedArea: 0.05,
    modelVersions: { segmentation: "v1" },
  },
  currentAnalysis: {
    captureId: "current",
    region: "left_buccal_mucosa",
    status: "complete",
    analysisOrigin: "live_model",
    qualityAccepted: true,
    candidateNormalizedArea: 0.06,
    modelVersions: { segmentation: "v1" },
  },
};

const validResult: ComparisonResult = {
  contractVersion: "1.1.0",
  baselineCaptureId: "baseline",
  currentCaptureId: "current",
  region: "left_buccal_mucosa",
  candidateMatchScore: 0.95,
  userConfirmedMatch: true,
  registrationConfidence: 0.9,
  inlierRatio: 0.8,
  reprojectionErrorRatio: 0.02,
  normalizedChange: 0.2,
  comparable: true,
  suppressionReasons: [],
  modelVersions: { registration: "v1" },
  inputOrigin: "live_capture",
  analysisOrigin: "live_model",
  disclaimer: "This result is not a diagnosis.",
};

describe("comparison response invariants", () => {
  it("accepts a matching confidence-gated response", () => {
    expect(() => assertComparisonResult(validResult, expected)).not.toThrow();
  });

  it("accepts honest segmentation abstentions for a suppressed registration attempt", () => {
    const abstainedExpected: ExpectedComparisonIdentity = {
      ...expected,
      baselineAnalysis: {
        ...expected.baselineAnalysis,
        status: "abstained",
        candidateNormalizedArea: null,
        modelVersions: { anatomy: "v1" },
      },
      currentAnalysis: {
        ...expected.currentAnalysis,
        status: "abstained",
        candidateNormalizedArea: null,
        modelVersions: { anatomy: "v1" },
      },
    };
    expect(() =>
      assertComparisonResult(
        {
          ...validResult,
          candidateMatchScore: null,
          comparable: false,
          normalizedChange: null,
          suppressionReasons: [
            "segmentation_release_gate_unmet",
            "registered_baseline_candidate_area_unavailable",
            "current_candidate_area_unavailable",
          ],
          analysisOrigin: "unavailable",
        },
        abstainedExpected,
      ),
    ).not.toThrow();
  });

  it("rejects identity substitution", () => {
    expect(() =>
      assertComparisonResult(
        { ...validResult, currentCaptureId: "other" },
        expected,
      ),
    ).toThrow(/identity/i);
  });

  it("rejects a comparable result below registration thresholds", () => {
    expect(() =>
      assertComparisonResult({ ...validResult, inlierRatio: 0.59 }, expected),
    ).toThrow(/invariants/i);
  });

  it("accepts an unconfirmed model suggestion only when change is suppressed", () => {
    const unconfirmedExpected = {
      ...expected,
      userConfirmedMatch: false,
    };
    expect(() =>
      assertComparisonResult(
        {
          ...validResult,
          userConfirmedMatch: false,
          comparable: false,
          normalizedChange: null,
          suppressionReasons: ["user_confirmation_required"],
        },
        unconfirmedExpected,
      ),
    ).not.toThrow();
  });

  it("rejects an unconfirmed suggestion that omits the confirmation gate", () => {
    expect(() =>
      assertComparisonResult(
        {
          ...validResult,
          userConfirmedMatch: false,
          comparable: false,
          normalizedChange: null,
          suppressionReasons: ["registration_inlier_ratio_below_gate"],
        },
        { ...expected, userConfirmedMatch: false },
      ),
    ).toThrow(/confirmation-required/i);
  });
});
