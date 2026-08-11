import type { AnimationSpeed } from "../types";

/** Slow is 0.5x playback, so each animation phase takes twice as long. */
export function animationDurationMs(
  standardDurationMs: number,
  speed: AnimationSpeed,
): number {
  return speed === "slow" ? standardDurationMs * 2 : standardDurationMs;
}
