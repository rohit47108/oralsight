const labels: Record<string, string> = {
  standard_eight_region: "Standard eight-region scan",
  detailed_multi_angle: "Detailed multi-angle scan",
  guided_video_sweep: "Guided video sweep",
  draft: "Draft",
  capturing: "Capture in progress",
  complete: "Capture complete",
  processing: "Analysis in progress",
  ready: "Ready to review",
  failed: "Analysis unavailable",
  deleted: "Deleted",
  live_capture: "Live capture",
  bundled_demo: "Bundled demonstration",
  live_model: "Live model",
  cached_model_result: "Cached model result",
  manual_fixture: "Manual fixture",
  unavailable: "Unavailable",
  pdf: "PDF report",
  html: "Web report",
  fhir_r4_bundle: "FHIR R4 bundle",
  summary_video: "Summary video",
  transcript: "Transcript",
};

export function readableLabel(value: string): string {
  return (
    labels[value] ??
    value
      .split("_")
      .filter(Boolean)
      .map((part) => part[0]?.toUpperCase() + part.slice(1))
      .join(" ")
  );
}

export function readableDate(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  }).format(new Date(value));
}

export function compactHash(value: string): string {
  return value.length <= 16 ? value : `${value.slice(0, 8)}…${value.slice(-8)}`;
}
