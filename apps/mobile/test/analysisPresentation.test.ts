import { describe, expect, it } from "vitest";

import {
  ADDITIONAL_ANALYSIS_TITLE,
  isReleasedModelOutput,
} from "../src/lib/analysisPresentation";

describe("analysis presentation", () => {
  it("shows a model output only after that output is enabled and released", () => {
    expect(isReleasedModelOutput(null)).toBe(false);
    expect(isReleasedModelOutput({ enabled: false, gatePassed: true })).toBe(
      false,
    );
    expect(isReleasedModelOutput({ enabled: true, gatePassed: false })).toBe(
      false,
    );
    expect(isReleasedModelOutput({ enabled: true, gatePassed: true })).toBe(
      true,
    );
  });

  it("uses a concise product-facing title", () => {
    expect(ADDITIONAL_ANALYSIS_TITLE).toBe("Additional image pattern analysis");
    expect(ADDITIONAL_ANALYSIS_TITLE).not.toMatch(/experimental|unsupported/i);
  });
});
