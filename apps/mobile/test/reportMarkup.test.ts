import { describe, expect, it } from "vitest";

import {
  observationImageMarkup,
  oralObservationMapMarkup,
} from "../src/lib/reportMarkup";

describe("report observation image markup", () => {
  it("draws the validated candidate polygon over the exact embedded image", () => {
    const markup = observationImageMarkup({
      base64: "AQID",
      mimeType: "image/jpeg",
      label: 'Left cheek "inside"',
      candidateMask: {
        polygon: [
          [0.1, 0.2],
          [0.4, 0.2],
          [0.3, 0.5],
        ],
        boundingBox: [0.1, 0.2, 0.3, 0.3],
        normalizedArea: 0.09,
      },
    });

    expect(markup).toContain("data:image/jpeg;base64,AQID");
    expect(markup).toContain(
      'points="0.100000,0.200000 0.400000,0.200000 0.300000,0.500000"',
    );
    expect(markup).toContain("Approximate candidate outline");
    expect(markup).toContain("&quot;inside&quot;");
    expect(markup).not.toContain('Left cheek "inside"');
  });

  it("labels an image honestly when no candidate outline was returned", () => {
    const markup = observationImageMarkup({
      base64: "AQID",
      mimeType: "image/png",
      label: "Lower lip",
      candidateMask: null,
    });

    expect(markup).toContain("no candidate outline returned");
    expect(markup).not.toContain("<polygon");
  });
});

describe("report oral observation map markup", () => {
  it("shows accepted state and confirmed pins without inventing a personalized map", () => {
    const markup = oralObservationMapMarkup({
      acceptedRegions: ["upper_lip", "right_buccal_mucosa"],
      pins: [
        {
          region: "right_buccal_mucosa",
          uvX: 0.7,
          uvY: 0.4,
          userConfirmed: true,
        },
        {
          region: "upper_lip",
          uvX: 0.5,
          uvY: 0.5,
          userConfirmed: false,
        },
      ],
      assetVersion: 'oral-map-v2 "reviewed"',
    });

    expect(markup).toContain('data-region="upper_lip" data-state="accepted"');
    expect(markup).toContain(
      'data-region="lower_lip" data-state="not-captured"',
    );
    expect(markup.match(/class="map-pin"/g)).toHaveLength(1);
    expect(markup).toContain("not a personalized anatomical model");
    expect(markup).toContain("oral-map-v2 &quot;reviewed&quot;");
    expect(markup).not.toContain('oral-map-v2 "reviewed"');
  });
});
