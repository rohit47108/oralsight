import type { AnalysisResult, MouthRegion } from "@stoma3d/contracts";

export function captureStorageRejectionReasons(
  analysis: AnalysisResult,
  selectedRegion: MouthRegion,
): string[] {
  const reasons = [...analysis.quality.reasons];
  if (!analysis.quality.accepted && reasons.length === 0) {
    reasons.push("Server quality validation rejected this image.");
  }
  if (
    analysis.anatomyPrediction.supported &&
    (!analysis.anatomyPrediction.selectedRegionMatches ||
      analysis.anatomyPrediction.region !== selectedRegion)
  ) {
    reasons.push(
      "The automatic anatomy check did not match the selected region. The image was not added.",
    );
  }
  return reasons;
}
