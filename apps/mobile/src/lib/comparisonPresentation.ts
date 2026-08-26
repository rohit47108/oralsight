import { clampComparisonBlend } from "./comparisonSlider";
import type { RegistrationAlignment } from "@oralsight/contracts";

export type NormalizedPoint = readonly [number, number];

export type ComparisonRegistrationAlignment = RegistrationAlignment;

export interface PresentationFrame {
  width: number;
  height: number;
}

export interface ImageSize {
  widthPx: number;
  heightPx: number;
}

export interface ContainedImageRect {
  left: number;
  top: number;
  width: number;
  height: number;
}

export interface DisplayRegistration {
  /** React Native's 9-value, column-major projective transform matrix. */
  matrix: readonly [
    number,
    number,
    number,
    number,
    number,
    number,
    number,
    number,
    number,
  ];
  sourceRect: ContainedImageRect;
  targetRect: ContainedImageRect;
}

interface CandidateMaskLike {
  polygon: readonly NormalizedPoint[];
}

export interface MaskTimelineGeometry {
  kind: "unavailable" | "crossfade" | "morph";
  baseline: readonly NormalizedPoint[];
  current: readonly NormalizedPoint[];
  morphed: readonly NormalizedPoint[] | null;
  baselineOpacity: number;
  currentOpacity: number;
}

const EPSILON = 1e-8;

export function containedImageRect(
  frame: PresentationFrame,
  image: ImageSize,
): ContainedImageRect | null {
  if (
    !Number.isFinite(frame.width) ||
    !Number.isFinite(frame.height) ||
    !Number.isFinite(image.widthPx) ||
    !Number.isFinite(image.heightPx) ||
    frame.width <= 0 ||
    frame.height <= 0 ||
    image.widthPx <= 0 ||
    image.heightPx <= 0
  ) {
    return null;
  }
  const scale = Math.min(
    frame.width / image.widthPx,
    frame.height / image.heightPx,
  );
  const width = image.widthPx * scale;
  const height = image.heightPx * scale;
  return {
    left: (frame.width - width) / 2,
    top: (frame.height - height) / 2,
    width,
    height,
  };
}

function determinant3(matrix: readonly number[]): number {
  const [a, b, c, d, e, f, g, h, i] = matrix;
  if (
    a === undefined ||
    b === undefined ||
    c === undefined ||
    d === undefined ||
    e === undefined ||
    f === undefined ||
    g === undefined ||
    h === undefined ||
    i === undefined
  ) {
    return 0;
  }
  return a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g);
}

export function isUsableRegistrationAlignment(
  value: ComparisonRegistrationAlignment | null | undefined,
): value is ComparisonRegistrationAlignment {
  if (
    !value ||
    value.method !== "orb_ransac_homography" ||
    value.coordinateSpace !== "normalized_image_coordinates" ||
    value.mapsFrom !== "current" ||
    value.mapsTo !== "baseline" ||
    value.matrix.length !== 9 ||
    !value.matrix.every(Number.isFinite) ||
    !Number.isFinite(value.sourceImageSize.widthPx) ||
    !Number.isFinite(value.sourceImageSize.heightPx) ||
    !Number.isFinite(value.targetImageSize.widthPx) ||
    !Number.isFinite(value.targetImageSize.heightPx) ||
    value.sourceImageSize.widthPx <= 0 ||
    value.sourceImageSize.heightPx <= 0 ||
    value.targetImageSize.widthPx <= 0 ||
    value.targetImageSize.heightPx <= 0 ||
    Math.abs(determinant3(value.matrix)) <= EPSILON
  ) {
    return false;
  }

  // A comparison registration should be a modest image-to-image warp. Refuse
  // matrices that send any image corner to infinity or far outside the frame.
  return (
    [
      [0, 0],
      [1, 0],
      [1, 1],
      [0, 1],
    ] as const
  ).every((point) => {
    const projected = projectPointUnchecked(point, value.matrix);
    return (
      projected !== null &&
      projected[0] >= -2 &&
      projected[0] <= 3 &&
      projected[1] >= -2 &&
      projected[1] <= 3
    );
  });
}

function projectPointUnchecked(
  point: NormalizedPoint,
  matrix: readonly number[],
): NormalizedPoint | null {
  const [x, y] = point;
  const [h00, h01, h02, h10, h11, h12, h20, h21, h22] = matrix;
  if (
    h00 === undefined ||
    h01 === undefined ||
    h02 === undefined ||
    h10 === undefined ||
    h11 === undefined ||
    h12 === undefined ||
    h20 === undefined ||
    h21 === undefined ||
    h22 === undefined
  ) {
    return null;
  }
  const denominator = h20 * x + h21 * y + h22;
  if (!Number.isFinite(denominator) || Math.abs(denominator) <= EPSILON) {
    return null;
  }
  const projectedX = (h00 * x + h01 * y + h02) / denominator;
  const projectedY = (h10 * x + h11 * y + h12) / denominator;
  return Number.isFinite(projectedX) && Number.isFinite(projectedY)
    ? [projectedX, projectedY]
    : null;
}

export function projectRegisteredPoint(
  point: NormalizedPoint,
  alignment: ComparisonRegistrationAlignment | null | undefined,
): NormalizedPoint | null {
  return isUsableRegistrationAlignment(alignment)
    ? projectPointUnchecked(point, alignment.matrix)
    : null;
}

export function buildDisplayRegistrationMatrix(
  frame: PresentationFrame,
  alignment: ComparisonRegistrationAlignment | null | undefined,
): DisplayRegistration | null {
  if (!isUsableRegistrationAlignment(alignment)) return null;
  const sourceRect = containedImageRect(frame, alignment.sourceImageSize);
  const targetRect = containedImageRect(frame, alignment.targetImageSize);
  if (!sourceRect || !targetRect) return null;

  const [h00, h01, h02, h10, h11, h12, h20, h21, h22] = alignment.matrix;
  // Convert the normalized image-space homography to a frame-space
  // homography. The source image is laid out at (0, 0); target letterboxing
  // is included in the output translation.
  const a00 =
    (targetRect.width * h00 + targetRect.left * h20) / sourceRect.width;
  const a01 =
    (targetRect.width * h01 + targetRect.left * h21) / sourceRect.height;
  const a02 = targetRect.width * h02 + targetRect.left * h22;
  const a10 =
    (targetRect.height * h10 + targetRect.top * h20) / sourceRect.width;
  const a11 =
    (targetRect.height * h11 + targetRect.top * h21) / sourceRect.height;
  const a12 = targetRect.height * h12 + targetRect.top * h22;
  const a20 = h20 / sourceRect.width;
  const a21 = h21 / sourceRect.height;

  // React Native expands a 9-value matrix in column-major order.
  const matrix = [a00, a10, a20, a01, a11, a21, a02, a12, h22] as const;
  return matrix.every(Number.isFinite)
    ? { matrix, sourceRect, targetRect }
    : null;
}

function resampleClosedPolygon(
  input: readonly NormalizedPoint[],
  sampleCount: number,
): NormalizedPoint[] | null {
  if (input.length < 3 || sampleCount < 3) return null;
  const points = input.every(
    ([x, y]) => Number.isFinite(x) && Number.isFinite(y),
  )
    ? [...input]
    : [];
  if (points.length < 3) return null;

  const segmentLengths: number[] = [];
  let perimeter = 0;
  for (let index = 0; index < points.length; index += 1) {
    const current = points[index]!;
    const next = points[(index + 1) % points.length]!;
    const length = Math.hypot(next[0] - current[0], next[1] - current[1]);
    segmentLengths.push(length);
    perimeter += length;
  }
  if (perimeter <= EPSILON) return null;

  const result: NormalizedPoint[] = [];
  let segmentIndex = 0;
  let segmentStartDistance = 0;
  for (let sample = 0; sample < sampleCount; sample += 1) {
    const distance = (sample / sampleCount) * perimeter;
    while (
      segmentIndex < segmentLengths.length - 1 &&
      distance > segmentStartDistance + segmentLengths[segmentIndex]!
    ) {
      segmentStartDistance += segmentLengths[segmentIndex]!;
      segmentIndex += 1;
    }
    const start = points[segmentIndex]!;
    const end = points[(segmentIndex + 1) % points.length]!;
    const segmentLength = segmentLengths[segmentIndex]!;
    const fraction =
      segmentLength <= EPSILON
        ? 0
        : (distance - segmentStartDistance) / segmentLength;
    result.push([
      start[0] + (end[0] - start[0]) * fraction,
      start[1] + (end[1] - start[1]) * fraction,
    ]);
  }
  return result;
}

function alignPolygonSamples(
  baseline: readonly NormalizedPoint[],
  current: readonly NormalizedPoint[],
): NormalizedPoint[] {
  let best = [...current];
  let bestError = Number.POSITIVE_INFINITY;
  const orientations = [[...current], [...current].reverse()];
  for (const orientation of orientations) {
    for (let offset = 0; offset < orientation.length; offset += 1) {
      let error = 0;
      for (let index = 0; index < baseline.length; index += 1) {
        const baselinePoint = baseline[index]!;
        const currentPoint =
          orientation[(index + offset) % orientation.length]!;
        error +=
          (baselinePoint[0] - currentPoint[0]) ** 2 +
          (baselinePoint[1] - currentPoint[1]) ** 2;
      }
      if (error < bestError) {
        bestError = error;
        best = baseline.map(
          (_point, index) =>
            orientation[(index + offset) % orientation.length]!,
        );
      }
    }
  }
  return best;
}

export function buildMaskTimelineGeometry(
  baselineMask: CandidateMaskLike | null | undefined,
  currentMask: CandidateMaskLike | null | undefined,
  progress: number,
  alignment: ComparisonRegistrationAlignment | null | undefined,
  sampleCount = 48,
): MaskTimelineGeometry {
  const boundedProgress = clampComparisonBlend(progress);
  if (!baselineMask || !currentMask) {
    return {
      kind: "unavailable",
      baseline: [],
      current: [],
      morphed: null,
      baselineOpacity: 1 - boundedProgress,
      currentOpacity: boundedProgress,
    };
  }

  const baseline = resampleClosedPolygon(baselineMask.polygon, sampleCount);
  const current = resampleClosedPolygon(currentMask.polygon, sampleCount);
  if (!baseline || !current) {
    return {
      kind: "unavailable",
      baseline: [],
      current: [],
      morphed: null,
      baselineOpacity: 1 - boundedProgress,
      currentOpacity: boundedProgress,
    };
  }

  if (!isUsableRegistrationAlignment(alignment)) {
    return {
      kind: "crossfade",
      baseline,
      current,
      morphed: null,
      baselineOpacity: 1 - boundedProgress,
      currentOpacity: boundedProgress,
    };
  }

  const projectedCurrent = current.map((point) =>
    projectPointUnchecked(point, alignment.matrix),
  );
  if (projectedCurrent.some((point) => point === null)) {
    return {
      kind: "crossfade",
      baseline,
      current,
      morphed: null,
      baselineOpacity: 1 - boundedProgress,
      currentOpacity: boundedProgress,
    };
  }
  const alignedCurrent = alignPolygonSamples(
    baseline,
    projectedCurrent as NormalizedPoint[],
  );
  return {
    kind: "morph",
    baseline,
    current: alignedCurrent,
    morphed: baseline.map((point, index) => {
      const currentPoint = alignedCurrent[index]!;
      return [
        point[0] + (currentPoint[0] - point[0]) * boundedProgress,
        point[1] + (currentPoint[1] - point[1]) * boundedProgress,
      ];
    }),
    baselineOpacity: 0,
    currentOpacity: 0,
  };
}
