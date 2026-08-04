import type { AnalysisStatus } from "@oralsight/contracts";

const RESULT_REASON_COPY: Readonly<Record<string, string>> = {
  image_too_small: "The image is too small to evaluate reliably.",
  image_too_blurry:
    "The image is too blurry. Hold the phone steady and try again.",
  exposure_out_of_range:
    "The image is too dark or too bright. Use even lighting and try again.",
  excessive_glare:
    "Reflections cover too much of the image. Change the angle or lighting.",
  image_obstructed:
    "The selected mouth region is partly blocked. Reframe and try again.",
  face_detected:
    "A face or identifying facial area was detected. Reframe to show mouth tissue only.",
  face_check_unavailable:
    "The privacy face check could not run, so the image was not accepted.",
  anatomy_release_gate_unmet:
    "The automatic mouth-region check is currently unavailable.",
  anatomy_model_abstained:
    "The automatic mouth-region check was not confident enough.",
  selected_region_anatomy_mismatch:
    "The image did not appear to match the selected mouth region.",
  anatomy_inference_failed:
    "The automatic mouth-region check could not finish.",
  segmentation_release_gate_unmet:
    "The abnormal-area model has not passed its required accuracy checks, so no candidate outline was shown.",
  segmentation_inference_failed: "The abnormal-area analysis could not finish.",
  appearance_inference_failed:
    "The appearance-description analysis could not finish.",
  disease_research_inference_failed:
    "The experimental disease-category analysis could not finish.",
  baseline_image_quality_rejected:
    "The earlier image did not pass the image-quality checks.",
  current_image_quality_rejected:
    "The newer image did not pass the image-quality checks.",
  user_confirmation_required:
    "Confirm that both images show the same observation before comparing them.",
  lesion_reidentification_release_gate_unmet:
    "Automatic observation matching has not passed its required accuracy checks.",
  lesion_reidentification_inference_failed:
    "Automatic observation matching could not finish.",
  candidate_match_score_unavailable: "No automatic match score is available.",
  baseline_candidate_region_unavailable:
    "The earlier image has no validated candidate outline.",
  current_candidate_region_unavailable:
    "The newer image has no validated candidate outline.",
  repeated_capture_area_error_gate_unmet:
    "Change estimates are disabled until repeated-photo testing meets the required error limit.",
  registration_inlier_ratio_below_gate:
    "The two images do not contain enough matching visual landmarks.",
  registration_reprojection_error_above_gate:
    "The two images could not be aligned closely enough.",
  baseline_candidate_area_unavailable:
    "The earlier image has no validated approximate candidate area.",
  registered_baseline_candidate_area_unavailable:
    "The earlier candidate area could not be aligned to the newer image.",
  current_candidate_area_unavailable:
    "The newer image has no validated approximate candidate area.",
  baseline_candidate_area_zero:
    "The earlier image has no measurable candidate area.",
  fixture_region_mismatch:
    "The bundled demonstration case does not match the selected region.",
  fixture_comparison_not_eligible:
    "This bundled demonstration case is not eligible for comparison.",
};

function sentenceCase(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) return "The service did not provide a reason.";
  const readable = trimmed.replaceAll("_", " ");
  const sentence = `${readable.charAt(0).toUpperCase()}${readable.slice(1)}`;
  return /[.!?]$/.test(sentence) ? sentence : `${sentence}.`;
}

export function humanizeResultReason(reason: string): string {
  const trimmed = reason.trim();
  if (!trimmed) return "The service did not provide a reason.";
  const fixedCopy = RESULT_REASON_COPY[trimmed];
  if (fixedCopy) return fixedCopy;
  if (trimmed.includes(" ") || !trimmed.includes("_")) {
    return sentenceCase(trimmed);
  }
  return sentenceCase(trimmed);
}

export function analysisStatusTitle(
  status: AnalysisStatus | undefined,
  hasCandidateMask: boolean,
): string {
  if (status === "complete") {
    return hasCandidateMask
      ? "Candidate area described"
      : "No candidate area outlined";
  }
  if (status === "abstained") return "No abnormal-area result shown";
  if (status === "unsupported") return "Image unsupported";
  return "Analysis unavailable";
}
