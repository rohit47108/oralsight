import type { CandidateMask, MouthRegion } from "@stoma3d/contracts";

function escapeAttribute(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

export function observationImageMarkup(input: {
  base64: string;
  mimeType: "image/jpeg" | "image/png";
  label: string;
  candidateMask: CandidateMask | null | undefined;
}): string {
  const label = escapeAttribute(input.label);
  const source = `data:${input.mimeType};base64,${input.base64}`;
  if (!input.candidateMask) {
    return `<img class="capture" src="${source}" alt="Captured ${label}; no candidate outline returned" />`;
  }
  const points = input.candidateMask.polygon
    .map(([x, y]) => `${x.toFixed(6)},${y.toFixed(6)}`)
    .join(" ");
  return `<figure class="capture-figure">
    <svg class="capture" viewBox="0 0 1 1" preserveAspectRatio="none" role="img" aria-label="Captured ${label} with approximate candidate outline">
      <title>Captured ${label} with approximate candidate outline</title>
      <image href="${source}" x="0" y="0" width="1" height="1" preserveAspectRatio="none" />
      <polygon points="${points}" fill="#FF6B5E" fill-opacity="0.22" stroke="#B42318" stroke-width="0.012" vector-effect="non-scaling-stroke" />
    </svg>
    <figcaption>Approximate candidate outline</figcaption>
  </figure>`;
}

const REPORT_MAP_LAYOUT: Readonly<
  Record<
    MouthRegion,
    {
      cx: number;
      cy: number;
      rx: number;
      ry: number;
      label: string;
    }
  >
> = {
  upper_lip: { cx: 120, cy: 24, rx: 68, ry: 15, label: "Upper lip" },
  upper_dental_arch: {
    cx: 120,
    cy: 58,
    rx: 54,
    ry: 17,
    label: "Upper arch",
  },
  left_buccal_mucosa: {
    cx: 42,
    cy: 103,
    rx: 28,
    ry: 47,
    label: "Left cheek",
  },
  right_buccal_mucosa: {
    cx: 198,
    cy: 103,
    rx: 28,
    ry: 47,
    label: "Right cheek",
  },
  dorsal_tongue: {
    cx: 120,
    cy: 105,
    rx: 52,
    ry: 30,
    label: "Tongue top",
  },
  ventral_tongue: {
    cx: 120,
    cy: 145,
    rx: 39,
    ry: 18,
    label: "Tongue underside",
  },
  lower_dental_arch: {
    cx: 120,
    cy: 178,
    rx: 54,
    ry: 17,
    label: "Lower arch",
  },
  lower_lip: { cx: 120, cy: 210, rx: 68, ry: 15, label: "Lower lip" },
};

export function oralObservationMapMarkup(input: {
  acceptedRegions: readonly MouthRegion[];
  pins: ReadonlyArray<{
    region: MouthRegion;
    uvX: number;
    uvY: number;
    userConfirmed: boolean;
  }>;
  assetVersion: string;
}): string {
  const accepted = new Set(input.acceptedRegions);
  const confirmedPins = input.pins.filter((pin) => pin.userConfirmed);
  const regions = (Object.keys(REPORT_MAP_LAYOUT) as MouthRegion[])
    .map((region) => {
      const layout = REPORT_MAP_LAYOUT[region];
      const regionAccepted = accepted.has(region);
      const state = regionAccepted ? "Accepted" : "Not captured";
      const fill = regionAccepted ? "#A7E8D4" : "#EEF3F5";
      const stroke = regionAccepted ? "#0B716C" : "#7C919D";
      const dash = regionAccepted ? "" : ' stroke-dasharray="5 4"';
      const pinMarkup = confirmedPins
        .filter((pin) => pin.region === region)
        .map((pin, index) => {
          const uvX = Math.max(0, Math.min(1, pin.uvX));
          const uvY = Math.max(0, Math.min(1, pin.uvY));
          const pinX = layout.cx + (uvX - 0.5) * layout.rx * 1.35;
          const pinY = layout.cy + (uvY - 0.5) * layout.ry * 1.35;
          return `<circle class="map-pin" data-pin-index="${index + 1}" cx="${pinX.toFixed(2)}" cy="${pinY.toFixed(2)}" r="5.5"><title>Confirmed observation pin in ${escapeAttribute(layout.label)}</title></circle>`;
        })
        .join("");
      return `<g data-region="${region}" data-state="${regionAccepted ? "accepted" : "not-captured"}">
        <ellipse cx="${layout.cx}" cy="${layout.cy}" rx="${layout.rx}" ry="${layout.ry}" fill="${fill}" stroke="${stroke}" stroke-width="2"${dash} />
        <text x="${layout.cx}" y="${layout.cy - 1}" text-anchor="middle" class="map-label">${escapeAttribute(layout.label)}</text>
        <text x="${layout.cx}" y="${layout.cy + 10}" text-anchor="middle" class="map-state">${state}</text>
        ${pinMarkup}
      </g>`;
    })
    .join("");
  return `<figure class="oral-map-figure">
    <svg class="oral-map" viewBox="0 0 240 235" role="img" aria-label="Generic eight-region oral observation map showing accepted and not captured regions with confirmed observation pins">
      <title>Generic eight-region oral observation map</title>
      ${regions}
    </svg>
    <figcaption>Generic map asset ${escapeAttribute(input.assetVersion)}. Solid teal regions are accepted; dashed gray regions are not captured; yellow dots are user-confirmed observation pins. This is not a personalized anatomical model.</figcaption>
  </figure>`;
}
