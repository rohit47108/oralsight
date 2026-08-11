import { describe, expect, it } from "vitest";

import {
  DISCLAIMER,
  footerNavigation,
  mouthRegions,
  primaryNavigation,
  scanSteps,
} from "./site";

describe("public site content contract", () => {
  it("uses the exact non-diagnostic statement", () => {
    expect(DISCLAIMER).toBe("This result is not a diagnosis.");
  });

  it("contains every canonical region exactly once", () => {
    expect(mouthRegions.map((region) => region.id)).toEqual([
      "dorsal_tongue",
      "ventral_tongue",
      "left_buccal_mucosa",
      "right_buccal_mucosa",
      "upper_lip",
      "lower_lip",
      "upper_dental_arch",
      "lower_dental_arch",
    ]);
    expect(new Set(mouthRegions.map((region) => region.id)).size).toBe(8);
  });

  it("keeps the four-part product story and required public navigation", () => {
    expect(scanSteps).toHaveLength(4);
    expect(primaryNavigation.map((item) => item.label)).toContain("Privacy");
    expect(primaryNavigation.map((item) => item.label)).toContain(
      "For professionals",
    );
    expect(footerNavigation.map((item) => item.label)).toContain(
      "Accessibility",
    );
    expect(footerNavigation.map((item) => item.label)).toContain(
      "Calibration card",
    );
  });
});
