import { describe, expect, it } from "vitest";

import {
  productAreaForRole,
  productHomeForAccount,
  productHomeForRole,
} from "@/lib/product-auth";

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

  it("keeps a privileged account locked until its token role is ready", () => {
    expect(
      productHomeForAccount({
        role: "admin",
        requiredOidcRole: "admin",
        privilegedAccessReady: false,
      }),
    ).toBe("/clinician/access-setup");
    expect(
      productHomeForAccount({
        role: "clinician",
        requiredOidcRole: "clinician",
        privilegedAccessReady: true,
      }),
    ).toBe("/clinician/reviews");
  });
});
