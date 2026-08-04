import {
  MOUTH_REGIONS,
  type ComparisonResult,
  type MouthRegion,
} from "@oralsight/contracts";

import type { CaptureRecord } from "@/types";

export function acceptedRegions(
  captures: CaptureRecord[],
  sessionId: string,
): MouthRegion[] {
  const accepted = captures
    .filter(
      (capture) => capture.sessionId === sessionId && capture.quality.accepted,
    )
    .map((capture) => capture.region);
  return [...new Set(accepted)];
}

export function scanProgress(
  captures: CaptureRecord[],
  sessionId: string,
): {
  completed: number;
  total: number;
  percent: number;
  missing: MouthRegion[];
} {
  const completed = acceptedRegions(captures, sessionId);
  const missing = MOUTH_REGIONS.filter((region) => !completed.includes(region));
  return {
    completed: completed.length,
    total: MOUTH_REGIONS.length,
    percent: completed.length / MOUTH_REGIONS.length,
    missing,
  };
}

export function comparisonsWithoutCaptureIds(
  comparisons: readonly ComparisonResult[],
  removedCaptureIds: Iterable<string>,
): ComparisonResult[] {
  const removed = new Set(removedCaptureIds);
  return comparisons.filter(
    (comparison) =>
      !removed.has(comparison.baselineCaptureId) &&
      !removed.has(comparison.currentCaptureId),
  );
}
