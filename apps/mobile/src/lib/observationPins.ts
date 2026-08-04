import type { ComparisonResult } from "@oralsight/contracts";

import type { CaptureRecord, ObservationPin } from "@/types";

export function pinsAfterConfirmedComparison(
  pins: readonly ObservationPin[],
  captures: readonly CaptureRecord[],
  comparison: ComparisonResult,
): ObservationPin[] {
  if (!comparison.userConfirmedMatch) return [...pins];

  const linkedIds = new Set([
    comparison.baselineCaptureId,
    comparison.currentCaptureId,
  ]);
  const linkedCaptures = captures.filter((capture) =>
    linkedIds.has(capture.id),
  );
  if (
    linkedCaptures.length !== 2 ||
    linkedCaptures.some((capture) => capture.region !== comparison.region)
  ) {
    return [...pins];
  }

  const relatedPins = pins.filter(
    (pin) =>
      pin.userConfirmed &&
      pin.region === comparison.region &&
      pin.captureIds.some((captureId) => linkedIds.has(captureId)),
  );
  const seedPin = relatedPins
    .slice()
    .sort((left, right) =>
      left.firstObservedAt.localeCompare(right.firstObservedAt),
    )[0];
  if (!seedPin) return [...pins];

  const captureIds = [
    ...new Set([
      ...relatedPins.flatMap((pin) => pin.captureIds),
      comparison.baselineCaptureId,
      comparison.currentCaptureId,
    ]),
  ];
  const firstObservedAt =
    [
      ...relatedPins.map((pin) => pin.firstObservedAt),
      ...linkedCaptures.map((capture) => capture.capturedAt),
    ].sort()[0] ?? seedPin.firstObservedAt;
  const status: ObservationPin["status"] =
    comparison.comparable && comparison.normalizedChange !== null
      ? Math.abs(comparison.normalizedChange) <= 0.1
        ? "stable"
        : "visually_changed"
      : "review_unavailable";
  const relatedPinIds = new Set(relatedPins.map((pin) => pin.id));

  return [
    ...pins.filter((pin) => !relatedPinIds.has(pin.id)),
    {
      ...seedPin,
      userConfirmed: true,
      firstObservedAt,
      status,
      captureIds,
    },
  ];
}
