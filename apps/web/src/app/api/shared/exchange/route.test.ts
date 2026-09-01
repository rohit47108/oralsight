import { beforeEach, describe, expect, it, vi } from "vitest";

const { exchangeShareSecret } = vi.hoisted(() => ({
  exchangeShareSecret: vi.fn(),
}));

vi.mock("@/lib/platform-api", () => ({
  PlatformApiError: class PlatformApiError extends Error {
    status = 503;
  },
  exchangeShareSecret,
}));

import { POST } from "./route";

describe("shared-record exchange cookie", () => {
  const operationKey = "019cfd1d-9fb7-7a55-b261-a7510f678c21";
  beforeEach(() => {
    exchangeShareSecret.mockReset();
  });

  it("covers both the viewer page and same-origin shared API routes", async () => {
    exchangeShareSecret.mockResolvedValue({
      exchangeToken: "opaque-exchange-token",
      expiresAt: "2026-08-08T16:00:00.000Z",
    });

    const response = await POST(
      new Request("https://app.example.test/api/shared/exchange", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          shareId: "share-1",
          secret: "fragment-secret",
          operationKey,
        }),
      }),
    );

    expect(response.status).toBe(200);
    const cookie = response.headers.get("set-cookie") ?? "";
    expect(cookie).toContain("stoma3d_share_token=opaque-exchange-token");
    expect(cookie).toContain("Path=/");
    expect(cookie).toContain("HttpOnly");
    expect(cookie).toContain("SameSite=strict");
    expect(exchangeShareSecret).toHaveBeenCalledWith(
      { shareId: "share-1", secret: "fragment-secret" },
      operationKey,
    );
  });

  it("rejects a missing retry key before contacting the platform", async () => {
    const response = await POST(
      new Request("https://app.example.test/api/shared/exchange", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ shareId: "share-1", secret: "fragment-secret" }),
      }),
    );
    expect(response.status).toBe(400);
    expect(exchangeShareSecret).not.toHaveBeenCalled();
  });
});
