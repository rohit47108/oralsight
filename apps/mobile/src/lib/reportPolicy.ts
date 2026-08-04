import type { CaptureRecord, ScanSession } from "@/types";

export function reportContainsSyntheticData(
  session: ScanSession,
  captures: readonly CaptureRecord[],
): boolean {
  return (
    session.demo ||
    captures.some(
      (capture) =>
        capture.inputOrigin === "bundled_demo" ||
        capture.samplePlaceholder === true,
    )
  );
}
