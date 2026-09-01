import { describe, expect, it } from "vitest";
import type { AnalysisOrigin, InputOrigin } from "@stoma3d/contracts";

import {
  assertLiveMobileInput,
  assertLiveResultOrigin,
} from "../src/lib/liveInputPolicy";

describe("installed-app live input policy", () => {
  it("accepts only live captures", () => {
    expect(() => assertLiveMobileInput("live_capture")).not.toThrow();
    expect(() => assertLiveMobileInput("bundled_demo" as InputOrigin)).toThrow(
      /live captures only/i,
    );
  });

  it.each<AnalysisOrigin>(["live_model", "unavailable"])(
    "accepts the non-fixture result origin %s",
    (origin) => {
      expect(() => assertLiveResultOrigin(origin)).not.toThrow();
    },
  );

  it.each<AnalysisOrigin>(["cached_model_result", "manual_fixture"])(
    "rejects the fixture-derived result origin %s",
    (origin) => {
      expect(() => assertLiveResultOrigin(origin)).toThrow(/fixture-derived/i);
    },
  );
});
