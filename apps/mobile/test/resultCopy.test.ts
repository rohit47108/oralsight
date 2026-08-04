import { describe, expect, it } from "vitest";

import {
  analysisStatusTitle,
  humanizeResultReason,
} from "../src/lib/resultCopy";

describe("humanizeResultReason", () => {
  it("explains release-gated analysis in plain language", () => {
    expect(humanizeResultReason("segmentation_release_gate_unmet")).toBe(
      "The abnormal-area model has not passed its required accuracy checks, so no candidate outline was shown.",
    );
  });

  it("turns unknown machine codes into readable sentences", () => {
    expect(humanizeResultReason("future_reason_code")).toBe(
      "Future reason code.",
    );
  });

  it("preserves a plain service explanation and adds punctuation", () => {
    expect(humanizeResultReason("The service could not be reached")).toBe(
      "The service could not be reached.",
    );
  });

  it("handles a blank reason without exposing an empty bullet", () => {
    expect(humanizeResultReason("   ")).toBe(
      "The service did not provide a reason.",
    );
  });
});

describe("analysisStatusTitle", () => {
  it("does not present a completed empty mask as an all-clear result", () => {
    expect(analysisStatusTitle("complete", false)).toBe(
      "No candidate area outlined",
    );
  });

  it("labels a completed candidate result as a visual description", () => {
    expect(analysisStatusTitle("complete", true)).toBe(
      "Candidate area described",
    );
  });
});
