import { describe, expect, it } from "vitest";
import type { AnalysisResult, ComparisonResult } from "@oralsight/contracts";

import {
  comparisonsEndingInSession,
  isCrossSessionChronologicalComparison,
  isChronologicalComparison,
  isEligibleLongitudinalCapture,
  latestPriorAcceptedCapture,
} from "../src/lib/longitudinalPolicy";

const comparison = (
  baselineCaptureId: string,
  currentCaptureId: string,
): ComparisonResult =>
  ({
    baselineCaptureId,
    currentCaptureId,
  }) as ComparisonResult;

describe("longitudinal comparison policy", () => {
  it("accepts only a strictly earlier baseline", () => {
    expect(
      isChronologicalComparison(
        { capturedAt: "2026-07-20T12:00:00.000Z" },
        { capturedAt: "2026-07-21T12:00:00.000Z" },
      ),
    ).toBe(true);
    expect(
      isChronologicalComparison(
        { capturedAt: "2026-07-21T12:00:00.000Z" },
        { capturedAt: "2026-07-20T12:00:00.000Z" },
      ),
    ).toBe(false);
    expect(
      isChronologicalComparison(
        { capturedAt: "not-a-date" },
        { capturedAt: "2026-07-21T12:00:00.000Z" },
      ),
    ).toBe(false);
  });

  it("includes cross-session comparisons that end in the report session", () => {
    const results = comparisonsEndingInSession(
      [
        comparison("older-session-capture", "current-session-capture"),
        comparison("current-session-capture", "future-session-capture"),
      ],
      new Set(["current-session-capture"]),
    );
    expect(results).toHaveLength(1);
    expect(results[0]?.baselineCaptureId).toBe("older-session-capture");
    expect(results[0]?.currentCaptureId).toBe("current-session-capture");
  });

  it("requires a strictly later capture from a different scan session", () => {
    expect(
      isCrossSessionChronologicalComparison(
        {
          sessionId: "session-one",
          capturedAt: "2026-07-20T12:00:00.000Z",
        },
        {
          sessionId: "session-two",
          capturedAt: "2026-07-21T12:00:00.000Z",
        },
      ),
    ).toBe(true);
    expect(
      isCrossSessionChronologicalComparison(
        {
          sessionId: "same-session",
          capturedAt: "2026-07-20T12:00:00.000Z",
        },
        {
          sessionId: "same-session",
          capturedAt: "2026-07-21T12:00:00.000Z",
        },
      ),
    ).toBe(false);
  });

  it("keeps an accepted live capture eligible when released analysis abstains", () => {
    const quality = {
      accepted: true,
      blurScore: 0.9,
      exposureScore: 0.9,
      glareScore: 0,
      obstructionScore: 0,
      faceDetected: false,
      reasons: [],
    };
    const capture = {
      id: "accepted-abstention",
      sessionId: "session-one",
      region: "dorsal_tongue" as const,
      capturedAt: "2026-07-21T12:00:00.000Z",
      encryptedUri: "file:///vault/capture.osv",
      inputOrigin: "live_capture" as const,
      quality,
    };
    const analysis = {
      captureId: capture.id,
      region: capture.region,
      inputOrigin: "live_capture",
      analysisOrigin: "live_model",
      status: "abstained",
      quality,
      anatomyPrediction: {
        region: capture.region,
        confidence: 0.98,
        supported: true,
        selectedRegionMatches: true,
      },
    } as AnalysisResult;

    expect(isEligibleLongitudinalCapture(capture, analysis)).toBe(true);
    expect(
      isEligibleLongitudinalCapture(capture, {
        ...analysis,
        status: "unsupported",
      }),
    ).toBe(false);
    expect(
      isEligibleLongitudinalCapture(capture, {
        ...analysis,
        analysisOrigin: "manual_fixture",
      }),
    ).toBe(false);
  });

  it("selects the latest protected accepted live capture from an earlier session", () => {
    const quality = {
      accepted: true,
      blurScore: 0.9,
      exposureScore: 0.9,
      glareScore: 0,
      obstructionScore: 0,
      faceDetected: false,
      reasons: [],
    };
    const base = {
      region: "lower_lip" as const,
      encryptedUri: "file:///vault/capture.osv",
      inputOrigin: "live_capture" as const,
      quality,
    };
    const result = latestPriorAcceptedCapture(
      [
        {
          ...base,
          id: "old",
          sessionId: "older-session",
          capturedAt: "2026-07-01T00:00:00.000Z",
        },
        {
          ...base,
          id: "latest",
          sessionId: "recent-session",
          capturedAt: "2026-07-20T00:00:00.000Z",
        },
        {
          ...base,
          id: "current",
          sessionId: "current-session",
          capturedAt: "2026-07-21T00:00:00.000Z",
        },
      ],
      "current-session",
      "lower_lip",
    );

    expect(result?.id).toBe("latest");
  });
});
