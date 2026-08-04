export function clampComparisonBlend(value: number): number {
  if (!Number.isFinite(value)) return 0.5;
  return Math.max(0, Math.min(1, value));
}

export function comparisonBlendFromTrackPosition(
  position: number,
  trackWidth: number,
): number {
  if (!Number.isFinite(trackWidth) || trackWidth <= 0) return 0.5;
  return clampComparisonBlend(position / trackWidth);
}

export function comparisonBlendAfterDrag(
  startingBlend: number,
  horizontalDistance: number,
  trackWidth: number,
): number {
  if (!Number.isFinite(trackWidth) || trackWidth <= 0) {
    return clampComparisonBlend(startingBlend);
  }
  return clampComparisonBlend(startingBlend + horizontalDistance / trackWidth);
}
