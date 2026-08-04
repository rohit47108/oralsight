import type { MouthRegion } from "@oralsight/contracts";

export interface CaptureGuideSpec {
  outlinePath: string;
  cue: string;
}

const CAPTURE_GUIDES: Readonly<Record<MouthRegion, CaptureGuideSpec>> = {
  dorsal_tongue: {
    outlinePath:
      "M70 151 C64 111 70 62 104 43 C123 32 157 32 176 43 C210 62 216 111 210 151 C177 168 103 168 70 151 Z",
    cue: "Center the upper tongue surface",
  },
  ventral_tongue: {
    outlinePath:
      "M82 66 C103 42 177 42 198 66 C192 111 172 145 140 158 C108 145 88 111 82 66 Z",
    cue: "Lift the tongue and center underneath",
  },
  left_buccal_mucosa: {
    outlinePath:
      "M42 39 C88 24 132 39 157 73 C176 98 173 135 148 155 C111 172 69 158 48 128 C32 105 29 65 42 39 Z",
    cue: "Center the left inner cheek",
  },
  right_buccal_mucosa: {
    outlinePath:
      "M238 39 C192 24 148 39 123 73 C104 98 107 135 132 155 C169 172 211 158 232 128 C248 105 251 65 238 39 Z",
    cue: "Center the right inner cheek",
  },
  upper_lip: {
    outlinePath:
      "M43 108 C68 65 104 61 140 82 C176 61 212 65 237 108 C208 132 72 132 43 108 Z",
    cue: "Lift and center the inside upper lip",
  },
  lower_lip: {
    outlinePath:
      "M43 81 C72 57 208 57 237 81 C212 124 176 128 140 107 C104 128 68 124 43 81 Z",
    cue: "Pull down and center the inside lower lip",
  },
  upper_dental_arch: {
    outlinePath:
      "M49 142 C55 71 101 44 140 44 C179 44 225 71 231 142 L202 142 C196 98 169 77 140 77 C111 77 84 98 78 142 Z",
    cue: "Tilt upward and center the upper arch",
  },
  lower_dental_arch: {
    outlinePath:
      "M49 48 C55 119 101 146 140 146 C179 146 225 119 231 48 L202 48 C196 92 169 113 140 113 C111 113 84 92 78 48 Z",
    cue: "Tilt downward and center the lower arch",
  },
};

export function captureGuideSpec(region: MouthRegion): CaptureGuideSpec {
  return CAPTURE_GUIDES[region];
}
