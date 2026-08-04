import { describe, expect, it } from "vitest";

import { routeRequiresConsent } from "../src/lib/navigationPolicy";

describe("consent route policy", () => {
  it("leaves only the entry and onboarding routes public", () => {
    expect(routeRequiresConsent([])).toBe(false);
    expect(routeRequiresConsent(["index"])).toBe(false);
    expect(routeRequiresConsent(["onboarding"])).toBe(false);
    expect(routeRequiresConsent(["(tabs)", "scan"])).toBe(true);
    expect(routeRequiresConsent(["capture", "[region]"])).toBe(true);
    expect(routeRequiresConsent(["report"])).toBe(true);
  });
});
