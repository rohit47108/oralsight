import { describe, expect, it } from "vitest";

import { compactHash, readableLabel } from "@/lib/presentation";

describe("workspace presentation", () => {
  it("uses product language for scan states", () => {
    expect(readableLabel("processing")).toBe("Analysis in progress");
    expect(readableLabel("standard_eight_region")).toBe(
      "Standard eight-region scan",
    );
  });

  it("shortens long hashes without hiding both ends", () => {
    expect(compactHash("1234567890abcdefghijklmnop")).toBe("12345678…ijklmnop");
  });
});
