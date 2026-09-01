import { MOUTH_REGIONS, type MouthRegion } from "@stoma3d/contracts";

export function nextIntroRegion(
  current: MouthRegion,
  direction: -1 | 1 = 1,
): MouthRegion {
  const index = MOUTH_REGIONS.indexOf(current);
  const nextIndex =
    (Math.max(0, index) + direction + MOUTH_REGIONS.length) %
    MOUTH_REGIONS.length;
  return MOUTH_REGIONS[nextIndex]!;
}

export function nextIntroRotation(current: number, direction: -1 | 1): number {
  const next = current + direction * 0.4;
  const fullTurn = Math.PI * 2;
  return ((next % fullTurn) + fullTurn) % fullTurn;
}
