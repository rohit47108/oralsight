import { describe, expect, it } from "vitest";

import { productAreaForRole, productHomeForRole } from "@/lib/product-auth";

describe("role routing", () => {
  it.each([
    ["patient", "patient", "/app/overview"],
    ["share_viewer", "shared", "/shared"],
    ["clinician_pending", "clinician", "/clinician/pending"],
    ["clinician", "clinician", "/clinician/reviews"],
    ["admin", "clinician", "/clinician/admin"],
  ] as const)("routes %s to its permitted area", (role, area, home) => {
    expect(productAreaForRole(role)).toBe(area);
    expect(productHomeForRole(role)).toBe(home);
  });
});
