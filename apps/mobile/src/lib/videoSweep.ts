import type { CaptureAngle, QualityResult } from "@stoma3d/contracts";

export const SWEEP_ANGLES = [
  "straight",
  "left_oblique",
  "right_oblique",
] as const satisfies readonly CaptureAngle[];
export type SweepAngle = (typeof SWEEP_ANGLES)[number];

const SAMPLE_POSITIONS: Record<SweepAngle, readonly number[]> = {
  straight: [0.12, 0.2, 0.29],
  left_oblique: [0.38, 0.48, 0.58],
  right_oblique: [0.7, 0.8, 0.9],
};

export interface SweepFrameRequest {
  angle: SweepAngle;
  timeMs: number;
}

export function sweepFrameRequests(durationMs: number): SweepFrameRequest[] {
  if (
    !Number.isFinite(durationMs) ||
    durationMs < 2_500 ||
    durationMs > 60_000
  ) {
    throw new Error("A guided sweep must last between 2.5 and 60 seconds.");
  }
  return SWEEP_ANGLES.flatMap((angle) =>
    SAMPLE_POSITIONS[angle].map((position) => ({
      angle,
      timeMs: Math.min(
        durationMs - 100,
        Math.max(100, Math.round(durationMs * position)),
      ),
    })),
  );
}

export function sweepQualityScore(quality: QualityResult): number {
  if (!quality.accepted) return Number.NEGATIVE_INFINITY;
  return (
    quality.blurScore * 0.4 +
    quality.exposureScore * 0.25 +
    (1 - quality.glareScore) * 0.2 +
    (1 - quality.obstructionScore) * 0.15
  );
}

export function selectBestSweepFrames<
  T extends { angle: SweepAngle; quality: QualityResult },
>(candidates: readonly T[]): T[] {
  return SWEEP_ANGLES.flatMap((angle) => {
    const best = candidates
      .filter(
        (candidate) => candidate.angle === angle && candidate.quality.accepted,
      )
      .sort(
        (left, right) =>
          sweepQualityScore(right.quality) - sweepQualityScore(left.quality),
      )[0];
    return best ? [best] : [];
  });
}

export function sweepInstruction(elapsedRatio: number): string {
  if (elapsedRatio < 0.34) return "Hold the target straight and centered";
  if (elapsedRatio < 0.67) return "Move slowly toward the left view";
  return "Move slowly toward the right view";
}
