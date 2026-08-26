import { describe, expect, it, vi } from "vitest";

import {
  createAuthorizationRequest,
  discoverOidc,
  exchangeAuthorizationCode,
  refreshTokenSet,
  validateAuthorizationCallback,
  verifyPlatformAccessToken,
  type OidcConfig,
} from "../src/cloud/auth";

const config: OidcConfig = {
  issuer: "https://identity.example.test",
  clientId: "oralsight-mobile",
  redirectUri: "oralsight://auth/callback",
  scopes: ["openid", "profile", "offline_access"],
};

describe("OIDC authorization-code PKCE", () => {
  it("creates a state-bound S256 authorization request without a client secret", async () => {
    let seed = 0;
    const request = await createAuthorizationRequest(config, {
      randomBytes: (length) =>
        Uint8Array.from({ length }, () => (seed++ * 17) % 256),
      sha256: async () => Uint8Array.from({ length: 32 }, (_, index) => index),
    });
    const url = new URL(request.authorizationUrl);
    expect(url.pathname).toBe("/authorize");
    expect(url.searchParams.get("response_type")).toBe("code");
    expect(url.searchParams.get("code_challenge_method")).toBe("S256");
    expect(url.searchParams.get("state")).toBe(request.state);
    expect(url.searchParams.has("client_secret")).toBe(false);
    expect(request.codeVerifier.length).toBeGreaterThanOrEqual(43);
  });

  it("discovers exact endpoints and rejects an issuer substitution", async () => {
    const goodFetch = vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            issuer: config.issuer,
            authorization_endpoint: `${config.issuer}/authorize`,
            token_endpoint: `${config.issuer}/oauth/token`,
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        ),
    );
    await expect(
      discoverOidc(config, goodFetch as typeof fetch),
    ).resolves.toMatchObject({
      issuer: config.issuer,
      tokenEndpoint: `${config.issuer}/oauth/token`,
    });
    const badFetch = vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            issuer: "https://attacker.example.test",
            authorization_endpoint: `${config.issuer}/authorize`,
            token_endpoint: `${config.issuer}/oauth/token`,
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        ),
    );
    await expect(
      discoverOidc(config, badFetch as typeof fetch),
    ).rejects.toThrow(/issuer/i);
  });

  it("rejects a callback with the wrong state", () => {
    expect(() =>
      validateAuthorizationCallback(
        "oralsight://auth/callback?code=abc&state=wrong",
        "expected",
      ),
    ).toThrow(/verified/i);
  });

  it("rejects a state-matched callback sent to another redirect", () => {
    expect(() =>
      validateAuthorizationCallback(
        "otherapp://auth/callback?code=abc&state=expected",
        "expected",
        config.redirectUri,
      ),
    ).toThrow(/redirect/i);
  });

  it("exchanges and refreshes tokens without sending a client secret", async () => {
    const fetchImpl = vi.fn(
      async (_input: RequestInfo | URL, init?: RequestInit) => {
        expect(String(init?.body)).not.toContain("client_secret");
        return new Response(
          JSON.stringify({
            access_token: "access-token",
            refresh_token: "refresh-token",
            id_token: "header.payload.signature",
            token_type: "Bearer",
            expires_in: 3600,
            scope: "openid profile offline_access",
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        );
      },
    );
    const configured = {
      ...config,
      tokenEndpoint: `${config.issuer}/oauth/token`,
    };
    const exchanged = await exchangeAuthorizationCode({
      config: configured,
      code: "code",
      codeVerifier: "v".repeat(64),
      fetchImpl: fetchImpl as typeof fetch,
      now: () => 1_000,
    });
    expect(exchanged.expiresAt).toBe(3_601_000);
    expect(exchanged).not.toHaveProperty("idToken");
    const refreshed = await refreshTokenSet({
      config: configured,
      refreshToken: "refresh-token",
      fetchImpl: fetchImpl as typeof fetch,
      now: () => 2_000,
    });
    expect(refreshed.refreshToken).toBe("refresh-token");
  });

  it("requires the platform to validate the opaque access token", async () => {
    const acceptedFetch = vi.fn(
      async (_input: RequestInfo | URL, init?: RequestInit) => {
        expect(init?.redirect).toBe("error");
        expect((init?.headers as Record<string, string>).Authorization).toBe(
          "Bearer access-token",
        );
        return new Response(
          JSON.stringify({
            id: "account-1",
            role: "patient",
            status: "active",
            createdAt: "2026-08-08T12:00:00.000Z",
            deletionPending: false,
            requiredOidcRole: null,
            privilegedAccessReady: true,
            clinicianApplicationEligible: false,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      },
    );
    await expect(
      verifyPlatformAccessToken({
        platformBaseUrl: "https://platform.example.test",
        accessToken: "access-token",
        fetchImpl: acceptedFetch as typeof fetch,
      }),
    ).resolves.toBeUndefined();

    const rejectedFetch = vi.fn(
      async () => new Response("{}", { status: 401 }),
    );
    await expect(
      verifyPlatformAccessToken({
        platformBaseUrl: "https://platform.example.test",
        accessToken: "forged-token",
        fetchImpl: rejectedFetch as typeof fetch,
      }),
    ).rejects.toThrow(/verify this sign-in/i);
  });
});
