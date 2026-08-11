import { describe, expect, it } from "vitest";

import {
  nextIntroRegion,
  nextIntroRotation,
} from "../src/components/oralObservationIntro";

describe("oral observation map introduction controls", () => {
  it("cycles through all eight named regions in either direction", () => {
    expect(nextIntroRegion("dorsal_tongue")).toBe("ventral_tongue");
    expect(nextIntroRegion("lower_dental_arch")).toBe("dorsal_tongue");
    expect(nextIntroRegion("dorsal_tongue", -1)).toBe("lower_dental_arch");
  });

  it("keeps manual rotation inside one full turn", () => {
    expect(nextIntroRotation(0, 1)).toBeCloseTo(0.4);
    expect(nextIntroRotation(0, -1)).toBeGreaterThan(5.8);
    expect(nextIntroRotation(Math.PI * 2 - 0.1, 1)).toBeCloseTo(0.3);
  });
});
