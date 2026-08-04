import type {
  AnalysisResult,
  ComparisonResult,
  MouthRegion,
  QualityResult,
} from "@oralsight/contracts";

interface DatedCapture {
  capturedAt: string;
}

interface PriorCaptureCandidate extends DatedCapture {
  id: string;
  sessionId: string;
  region: MouthRegion;
  encryptedUri: string | null;
  inputOrigin: "live_capture" | "bundled_demo";
  quality: QualityResult;
}

interface ComparisonCaptureCandidate extends PriorCaptureCandidate {
  samplePlaceholder?: boolean;
}

export function isEligibleLongitudinalCapture(
  capture: ComparisonCaptureCandidate,
  analysis: AnalysisResult | undefined,
): boolean {
  return Boolean(
    capture.inputOrigin === "live_capture" &&
    !capture.samplePlaceholder &&
    capture.encryptedUri &&
    capture.quality.accepted &&
    analysis &&
    analysis.captureId === capture.id &&
    analysis.region === capture.region &&
    analysis.inputOrigin === "live_capture" &&
    analysis.analysisOrigin === "live_model" &&
    (analysis.status === "complete" || analysis.status === "abstained") &&
    analysis.quality.accepted &&
    analysis.anatomyPrediction.supported &&
    analysis.anatomyPrediction.selectedRegionMatches &&
    Number.isFinite(Date.parse(capture.capturedAt)),
  );
}

export function isChronologicalComparison(
  baseline: DatedCapture,
  current: DatedCapture,
): boolean {
  const baselineTime = Date.parse(baseline.capturedAt);
  const currentTime = Date.parse(current.capturedAt);
  return (
    Number.isFinite(baselineTime) &&
    Number.isFinite(currentTime) &&
    baselineTime < currentTime
  );
}

export function isCrossSessionChronologicalComparison(
  baseline: DatedCapture & { sessionId: string },
  current: DatedCapture & { sessionId: string },
): boolean {
  return (
    baseline.sessionId !== current.sessionId &&
    isChronologicalComparison(baseline, current)
  );
}

export function comparisonsEndingInSession(
  comparisons: readonly ComparisonResult[],
  sessionCaptureIds: ReadonlySet<string>,
): ComparisonResult[] {
  return comparisons.filter((comparison) =>
    sessionCaptureIds.has(comparison.currentCaptureId),
  );
}

export function latestPriorAcceptedCapture<T extends PriorCaptureCandidate>(
  captures: readonly T[],
  currentSessionId: string | null,
  region: MouthRegion,
): T | null {
  if (!currentSessionId) return null;
  return (
    captures
      .filter(
        (capture) =>
          capture.sessionId !== currentSessionId &&
          capture.region === region &&
          capture.inputOrigin === "live_capture" &&
          capture.quality.accepted &&
          Boolean(capture.encryptedUri) &&
          Number.isFinite(Date.parse(capture.capturedAt)),
      )
      .sort(
        (left, right) =>
          Date.parse(right.capturedAt) - Date.parse(left.capturedAt),
      )[0] ?? null
  );
}
