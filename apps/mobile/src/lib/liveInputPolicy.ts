import type { AnalysisOrigin, InputOrigin } from "@stoma3d/contracts";

export function assertLiveMobileInput(
  origin: InputOrigin,
): asserts origin is "live_capture" {
  if (origin !== "live_capture") {
    throw new Error("Installed Stoma3D builds accept live captures only.");
  }
}

export function assertLiveResultOrigin(origin: AnalysisOrigin): void {
  if (origin === "cached_model_result" || origin === "manual_fixture") {
    throw new Error(
      "Installed Stoma3D builds reject fixture-derived analysis results.",
    );
  }
}
