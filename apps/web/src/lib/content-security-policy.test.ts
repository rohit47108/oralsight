import { describe, expect, it } from "vitest";

import { buildContentSecurityPolicy } from "./content-security-policy";

describe("content security policy", () => {
  it("uses a per-request nonce without unsafe inline scripts", () => {
    const policy = buildContentSecurityPolicy("bm9uY2UtZm9yLXRlc3Rz", {
      NODE_ENV: "production",
      AUTH0_DOMAIN: "identity.example.org",
      STOMA3D_PLATFORM_API_URL: "https://api.example.org/v2",
    });

    expect(policy).toContain(
      "script-src 'self' 'nonce-bm9uY2UtZm9yLXRlc3Rz' 'strict-dynamic'",
    );
    expect(policy).not.toMatch(/script-src[^;]*'unsafe-inline'/);
    expect(policy).toContain("https://identity.example.org");
    expect(policy).toContain("https://api.example.org");
    expect(policy).toContain("upgrade-insecure-requests");
  });

  it("allows eval only for the local development runtime", () => {
    const policy = buildContentSecurityPolicy("bm9uY2UtZm9yLWRldg==", {
      NODE_ENV: "development",
    });

    expect(policy).toContain("'unsafe-eval'");
    expect(policy).not.toContain("upgrade-insecure-requests");
  });

  it("rejects malformed nonces", () => {
    expect(() => buildContentSecurityPolicy("short", {})).toThrow(
      /valid request nonce/i,
    );
  });
});
