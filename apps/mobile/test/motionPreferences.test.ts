import { describe, expect, it } from "vitest";

import { animationDurationMs } from "../src/lib/motionPreferences";

describe("animation speed preference", () => {
  it("keeps standard playback timing", () => {
    expect(animationDurationMs(1_250, "standard")).toBe(1_250);
  });

  it("uses twice the duration for 0.5x playback", () => {
    expect(animationDurationMs(1_250, "slow")).toBe(2_500);
  });
});
