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
  const comparisonStatus = observationComparisonStatus(comparison);
  const status: ObservationPin["status"] =
    comparisonStatus === "stable"
      ? "stable"
      : comparisonStatus === "insufficient_comparable_data"
        ? "review_unavailable"
        : "visually_changed";
  const relatedPinIds = new Set(relatedPins.map((pin) => pin.id));

  return [
    ...pins.filter((pin) => !relatedPinIds.has(pin.id)),
    {
      ...seedPin,
      userConfirmed: true,
      firstObservedAt,
      status,
      comparisonStatus,
      captureIds,
    },
  ];
}

function observationComparisonStatus(
  comparison: ComparisonResult,
): NonNullable<ObservationPin["comparisonStatus"]> {
  if (
    !comparison.comparable ||
    comparison.normalizedChange === null ||
    comparison.descriptorChanges == null
  ) {
    return "insufficient_comparable_data";
  }
  if (comparison.normalizedChange > 0.1) {
    return "increased_estimated_size";
  }
  if (comparison.normalizedChange < -0.1) {
    return "decreased_estimated_size";
  }

  const changes = comparison.descriptorChanges;
  const surfaceChanged = [
    changes.meanRednessChange,
    changes.meanBrightnessChange,
    changes.textureContrastChange,
    changes.ulcerationLikeContrastChange,
  ].some((value) => value !== null && Math.abs(value) >= 0.08);
  if (surfaceChanged) return "color_or_texture_changed";

  const shapeChanged =
    Math.abs(changes.normalizedWidthChange) > 0.1 ||
    Math.abs(changes.normalizedHeightChange) > 0.1 ||
    Math.abs(changes.normalizedPerimeterChange) > 0.1 ||
    Math.abs(changes.borderIrregularityChange) > 0.1;
  return shapeChanged ? "shape_changed" : "stable";
}
