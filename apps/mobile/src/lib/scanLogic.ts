import {
  MOUTH_REGIONS,
  type CaptureAngle,
  type CaptureProtocol,
  type ComparisonResult,
  type MouthRegion,
} from "@oralsight/contracts";

import type { CaptureRecord } from "@/types";

export function acceptedRegions(
  captures: readonly CaptureRecord[],
  sessionId: string,
): MouthRegion[] {
  const accepted = captures
    .filter(
      (capture) =>
        capture.sessionId === sessionId &&
        capture.quality.accepted &&
        (capture.angle === "primary" || capture.angle === "straight"),
    )
    .map((capture) => capture.region);
  return [...new Set(accepted)];
}

export function scanProgress(
  captures: readonly CaptureRecord[],
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

export const REQUIRED_DETAILED_ANGLES = [
  "straight",
  "left_oblique",
  "right_oblique",
] as const satisfies readonly CaptureAngle[];

export function requiredAnglesForProtocol(
  protocol: CaptureProtocol,
): readonly CaptureAngle[] {
  return protocol === "standard_eight_region"
    ? (["primary"] as const)
    : REQUIRED_DETAILED_ANGLES;
}

export function acceptedAngles(
  captures: readonly CaptureRecord[],
  sessionId: string,
  region: MouthRegion,
): CaptureAngle[] {
  return [
    ...new Set(
      captures
        .filter(
          (capture) =>
            capture.sessionId === sessionId &&
            capture.region === region &&
            capture.quality.accepted,
        )
        .map((capture) => capture.angle),
    ),
  ];
}

export function detailedScanProgress(
  captures: readonly CaptureRecord[],
  sessionId: string,
  protocol: CaptureProtocol,
): {
  completedViews: number;
  totalViews: number;
  completeRegions: number;
  missingByRegion: Record<MouthRegion, CaptureAngle[]>;
} {
  const required = requiredAnglesForProtocol(protocol);
  const missingByRegion = Object.fromEntries(
    MOUTH_REGIONS.map((region) => {
      const accepted = acceptedAngles(captures, sessionId, region);
      return [region, required.filter((angle) => !accepted.includes(angle))];
    }),
  ) as Record<MouthRegion, CaptureAngle[]>;
  const totalViews = required.length * MOUTH_REGIONS.length;
  const missingViews = Object.values(missingByRegion).reduce(
    (total, angles) => total + angles.length,
    0,
  );
  return {
    completedViews: totalViews - missingViews,
    totalViews,
    completeRegions: MOUTH_REGIONS.filter(
      (region) => missingByRegion[region].length === 0,
    ).length,
    missingByRegion,
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
