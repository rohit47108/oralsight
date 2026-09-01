import { describe, expect, it } from "vitest";
import { MOUTH_REGIONS } from "@stoma3d/contracts";

import { captureGuideSpec } from "../src/lib/captureGuide";

describe("captureGuideSpec", () => {
  it("provides a distinct visible guide for every canonical region", () => {
    const guides = MOUTH_REGIONS.map((region) => captureGuideSpec(region));

    expect(guides).toHaveLength(8);
    expect(new Set(guides.map((guide) => guide.outlinePath)).size).toBe(8);
    expect(new Set(guides.map((guide) => guide.cue)).size).toBe(8);
    expect(
      guides.every(
        (guide) =>
          guide.outlinePath.startsWith("M") &&
          guide.cue.trim().length > 0 &&
          guide.targetWidthPercent >= 1 &&
          guide.targetWidthPercent <= 100,
      ),
    ).toBe(true);
  });
});
