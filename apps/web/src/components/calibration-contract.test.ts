import { describe, expect, it } from "vitest";

import { ARUCO_4X4_50_MARKER_17 } from "@/components/aruco-marker";
import { CALIBRATION_QR_PAYLOAD } from "@/components/calibration-qr";

describe("print calibration contract", () => {
  it("uses the tested ArUco marker 17 module pattern", () => {
    expect(ARUCO_4X4_50_MARKER_17).toEqual([
      "111111",
      "110011",
      "110011",
      "111111",
      "111111",
      "111111",
    ]);
  });

  it("uses the same metadata payload as the generated PDF cards", () => {
    expect(JSON.parse(CALIBRATION_QR_PAYLOAD)).toEqual({
      marker_dictionary: "DICT_4X4_50",
      marker_id: 17,
      marker_side_mm: 20,
      reference_bar_mm: 50,
      schema: "oralsight_calibration_card",
      version: "oralsight-calibration-v1",
    });
  });
});
