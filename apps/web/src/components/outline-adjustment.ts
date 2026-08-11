export const OUTLINE_ADJUSTMENT_SCHEMA =
  "oralsight-outline-adjustment-v1" as const;

export type NormalizedPoint = [number, number];

export interface OutlineTarget {
  observationId: string;
  captureViewId: string;
  region: string;
  modelPolygon: NormalizedPoint[];
}

export interface OutlineAdjustmentPayload {
  schema: typeof OUTLINE_ADJUSTMENT_SCHEMA;
  observationId: string;
  captureViewId: string;
  region: string;
  coordinateSpace: "image_normalized";
  polygon: NormalizedPoint[];
  source: "clinician_manual";
  note: string | null;
}

type UnknownRecord = Record<string, unknown>;

function record(value: unknown): UnknownRecord | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as UnknownRecord)
    : null;
}

function nonemptyString(value: unknown): string | null {
  return typeof value === "string" && value.trim().length ? value.trim() : null;
}

export function clampNormalized(value: number): number {
  return Math.min(1, Math.max(0, value));
}

function normalizedPoint(value: unknown): NormalizedPoint | null {
  if (
    !Array.isArray(value) ||
    value.length !== 2 ||
    typeof value[0] !== "number" ||
    typeof value[1] !== "number" ||
    !Number.isFinite(value[0]) ||
    !Number.isFinite(value[1])
  ) {
    return null;
  }
  return [clampNormalized(value[0]), clampNormalized(value[1])];
}

export function normalizePolygon(
  value: unknown,
  maximumPoints = 96,
): NormalizedPoint[] | null {
  if (!Array.isArray(value) || maximumPoints < 3) return null;
  const points = value.map(normalizedPoint);
  if (points.some((point) => point === null) || points.length < 3) return null;
  const valid = points as NormalizedPoint[];
  if (valid.length <= maximumPoints) return valid;
  return Array.from({ length: maximumPoints }, (_, index) => {
    const sourceIndex = Math.floor((index * valid.length) / maximumPoints);
    return valid[sourceIndex]!;
  });
}

export function extractOutlineTargets(data: unknown): OutlineTarget[] {
  const analysis = record(data);
  const observations = Array.isArray(analysis?.observations)
    ? analysis.observations
    : [];
  return observations.flatMap((value) => {
    const observation = record(value);
    const mask = record(observation?.candidateMask);
    const observationId = nonemptyString(observation?.observationId);
    const captureViewId = nonemptyString(observation?.captureViewId);
    const polygon = normalizePolygon(mask?.polygon);
    if (!observationId || !captureViewId || !polygon) return [];
    return [
      {
        observationId,
        captureViewId,
        region: nonemptyString(observation?.region) ?? "oral_region",
        modelPolygon: polygon,
      },
    ];
  });
}

export function serializeOutlineAdjustment(input: {
  target: OutlineTarget;
  polygon: NormalizedPoint[];
  note: string;
}): string {
  const polygon = normalizePolygon(input.polygon);
  if (!polygon)
    throw new Error("An outline needs at least three valid points.");
  const payload: OutlineAdjustmentPayload = {
    schema: OUTLINE_ADJUSTMENT_SCHEMA,
    observationId: input.target.observationId,
    captureViewId: input.target.captureViewId,
    region: input.target.region,
    coordinateSpace: "image_normalized",
    polygon: polygon.map(([x, y]) => [
      Number(x.toFixed(6)),
      Number(y.toFixed(6)),
    ]),
    source: "clinician_manual",
    note: input.note.trim().slice(0, 600) || null,
  };
  return JSON.stringify(payload);
}

export function parseOutlineAdjustment(
  value: unknown,
): OutlineAdjustmentPayload | null {
  let parsed: unknown = value;
  if (typeof value === "string") {
    try {
      parsed = JSON.parse(value) as unknown;
    } catch {
      return null;
    }
  }
  const payload = record(parsed);
  const polygon = normalizePolygon(payload?.polygon);
  const observationId = nonemptyString(payload?.observationId);
  const captureViewId = nonemptyString(payload?.captureViewId);
  const region = nonemptyString(payload?.region);
  if (
    payload?.schema !== OUTLINE_ADJUSTMENT_SCHEMA ||
    payload.coordinateSpace !== "image_normalized" ||
    payload.source !== "clinician_manual" ||
    !observationId ||
    !captureViewId ||
    !region ||
    !polygon ||
    !(payload.note === null || typeof payload.note === "string")
  ) {
    return null;
  }
  return {
    schema: OUTLINE_ADJUSTMENT_SCHEMA,
    observationId,
    captureViewId,
    region,
    coordinateSpace: "image_normalized",
    polygon,
    source: "clinician_manual",
    note: typeof payload.note === "string" ? payload.note.slice(0, 600) : null,
  };
}

export function movePolygonPoint(
  polygon: NormalizedPoint[],
  index: number,
  next: NormalizedPoint,
): NormalizedPoint[] {
  if (!polygon[index]) return polygon;
  return polygon.map((point, pointIndex) =>
    pointIndex === index
      ? [clampNormalized(next[0]), clampNormalized(next[1])]
      : point,
  );
}

export function nudgePolygonPoint(
  polygon: NormalizedPoint[],
  index: number,
  deltaX: number,
  deltaY: number,
): NormalizedPoint[] {
  const current = polygon[index];
  return current
    ? movePolygonPoint(polygon, index, [
        current[0] + deltaX,
        current[1] + deltaY,
      ])
    : polygon;
}

export function insertPolygonPoint(
  polygon: NormalizedPoint[],
  afterIndex: number,
): NormalizedPoint[] {
  const current = polygon[afterIndex];
  const next = polygon[(afterIndex + 1) % polygon.length];
  if (!current || !next || polygon.length >= 96) return polygon;
  const inserted: NormalizedPoint = [
    (current[0] + next[0]) / 2,
    (current[1] + next[1]) / 2,
  ];
  return [
    ...polygon.slice(0, afterIndex + 1),
    inserted,
    ...polygon.slice(afterIndex + 1),
  ];
}

export function removePolygonPoint(
  polygon: NormalizedPoint[],
  index: number,
): NormalizedPoint[] {
  return polygon.length <= 3
    ? polygon
    : polygon.filter((_, pointIndex) => pointIndex !== index);
}

export function clientPointToNormalized(
  bounds: { left: number; top: number; width: number; height: number },
  clientX: number,
  clientY: number,
): NormalizedPoint {
  if (bounds.width <= 0 || bounds.height <= 0) return [0, 0];
  return [
    clampNormalized((clientX - bounds.left) / bounds.width),
    clampNormalized((clientY - bounds.top) / bounds.height),
  ];
}
