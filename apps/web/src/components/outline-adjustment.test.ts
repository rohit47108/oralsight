import { describe, expect, it } from "vitest";

import {
  clientPointToNormalized,
  extractOutlineTargets,
  insertPolygonPoint,
  normalizePolygon,
  nudgePolygonPoint,
  parseOutlineAdjustment,
  removePolygonPoint,
  serializeOutlineAdjustment,
  type OutlineTarget,
} from "@/components/outline-adjustment";

const target: OutlineTarget = {
  observationId: "observation-1",
  captureViewId: "capture-view-1",
  region: "left_buccal_mucosa",
  modelPolygon: [
    [0.2, 0.2],
    [0.8, 0.2],
    [0.8, 0.8],
    [0.2, 0.8],
  ],
};

describe("outline adjustment geometry", () => {
  it("extracts only valid normalized candidate outlines", () => {
    expect(
      extractOutlineTargets({
        observations: [
          {
            observationId: "observation-1",
            captureViewId: "capture-view-1",
            region: "left_buccal_mucosa",
            candidateMask: {
              polygon: [
                [-0.1, 0.2],
                [0.8, 0.2],
                [1.2, 0.8],
              ],
            },
          },
          {
            observationId: "invalid",
            captureViewId: "capture-view-2",
            candidateMask: {
              polygon: [
                [0.1, 0.1],
                [0.2, 0.2],
              ],
            },
          },
        ],
      }),
    ).toEqual([
      {
        observationId: "observation-1",
        captureViewId: "capture-view-1",
        region: "left_buccal_mucosa",
        modelPolygon: [
          [0, 0.2],
          [0.8, 0.2],
          [1, 0.8],
        ],
      },
    ]);
  });

  it("moves, inserts, and removes handles while enforcing image bounds", () => {
    const moved = nudgePolygonPoint(target.modelPolygon, 0, -0.4, 0.9);
    expect(moved[0]).toEqual([0, 1]);
    const inserted = insertPolygonPoint(moved, 0);
    expect(inserted).toHaveLength(5);
    expect(inserted[1]).toEqual([0.4, 0.6]);
    expect(removePolygonPoint(inserted, 1)).toEqual(moved);
    expect(removePolygonPoint(moved.slice(0, 3), 0)).toHaveLength(3);
  });

  it("converts pointer positions to clamped normalized coordinates", () => {
    expect(
      clientPointToNormalized(
        { left: 100, top: 50, width: 400, height: 200 },
        300,
        100,
      ),
    ).toEqual([0.5, 0.25]);
    expect(
      clientPointToNormalized(
        { left: 100, top: 50, width: 400, height: 200 },
        900,
        -10,
      ),
    ).toEqual([1, 0]);
  });

  it("round-trips a versioned normalized annotation body", () => {
    const body = serializeOutlineAdjustment({
      target,
      polygon: target.modelPolygon,
      note: "  Boundary follows the visible edge.  ",
    });
    expect(parseOutlineAdjustment(body)).toEqual({
      schema: "stoma3d-outline-adjustment-v1",
      observationId: "observation-1",
      captureViewId: "capture-view-1",
      region: "left_buccal_mucosa",
      coordinateSpace: "image_normalized",
      polygon: target.modelPolygon,
      source: "clinician_manual",
      note: "Boundary follows the visible edge.",
    });
    expect(parseOutlineAdjustment("plain text note")).toBeNull();
    expect(
      normalizePolygon([
        [0, 0],
        [0.5, 0.5],
      ]),
    ).toBeNull();
  });

  it("bounds saved outlines so the existing annotation limit is respected", () => {
    const polygon = Array.from({ length: 500 }, (_, index) => [
      index / 499,
      (499 - index) / 499,
    ]);
    const normalized = normalizePolygon(polygon);
    expect(normalized).toHaveLength(96);
    const body = serializeOutlineAdjustment({
      target,
      polygon: normalized!,
      note: "a".repeat(1_000),
    });
    expect(body.length).toBeLessThan(4_000);
    expect(parseOutlineAdjustment(body)?.note).toHaveLength(600);
  });
});
