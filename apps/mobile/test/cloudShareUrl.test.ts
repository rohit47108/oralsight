import { describe, expect, it } from "vitest";

import {
  buildShareUrl,
  shareSecretStaysInFragment,
} from "../src/cloud/shareUrl";

describe("fragment-secret share URLs", () => {
  it("keeps the secret out of the path and query", () => {
    const url = buildShareUrl("https://app.example.test/shared", {
      share: {
        shareId: "share-123",
        patientUserId: "patient-1",
        status: "active",
        resources: [{ resourceType: "scan_session", resourceId: "scan-1" }],
        expiresAt: "2026-08-07T12:00:00.000Z",
        maxExchanges: 1,
        exchangeCount: 0,
        revokedAt: null,
        createdAt: "2026-08-06T12:00:00.000Z",
        retentionExpiresAt: "2026-09-06T12:00:00.000Z",
        active: true,
      },
      fragmentSecret: "s".repeat(48),
      fragmentParameter: "secret",
    });
    expect(shareSecretStaysInFragment(url)).toBe(true);
    expect(new URL(url).pathname).not.toContain("s".repeat(48));
    expect(new URL(url).searchParams.get("id")).toBe("share-123");
    expect(new URL(url).searchParams.has("secret")).toBe(false);
  });
});
