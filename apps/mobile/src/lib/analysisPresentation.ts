export const ADDITIONAL_ANALYSIS_TITLE =
  "Additional image pattern analysis" as const;

interface ReleasableOutput {
  enabled: boolean;
  gatePassed: boolean;
}

export function isReleasedModelOutput(
  output: ReleasableOutput | null | undefined,
): output is ReleasableOutput {
  return output?.enabled === true && output.gatePassed === true;
}
