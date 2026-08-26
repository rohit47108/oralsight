import { afterEach, describe, expect, it, vi } from "vitest";

import { getAuth0Client } from "@/lib/auth0";

describe("getAuth0Client", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("fails clearly when hosted accounts are disabled", () => {
    vi.stubEnv("ORALSIGHT_WEB_MODE", "public");

    expect(() => getAuth0Client()).toThrow(/hosted accounts are disabled/i);
  });
});
