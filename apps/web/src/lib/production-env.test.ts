import { describe, expect, it, vi } from "vitest";

import { validateProductionWebEnvironment } from "@/lib/production-env";
import { hostedWorkspaceEnabled } from "@/lib/production-env";

const realEnvironment = {
  NODE_ENV: "production",
  VERCEL: "1",
  AUTH0_DOMAIN: "identity.oralsight.test",
  AUTH0_CLIENT_ID: "public-client-id",
  AUTH0_CLIENT_SECRET: "server-client-secret-value",
  AUTH0_SECRET: "a".repeat(64),
  AUTH0_AUDIENCE: "oralsight-platform-api",
  APP_BASE_URL: "https://app.oralsight.test",
  NEXT_PUBLIC_SITE_URL: "https://app.oralsight.test",
  ORALSIGHT_PLATFORM_API_URL: "https://api.oralsight.test",
};

describe("production web environment", () => {
  it("does nothing during development", () => {
    expect(() =>
      validateProductionWebEnvironment({ NODE_ENV: "development" }),
    ).not.toThrow();
  });

  it("accepts a complete HTTPS Vercel environment", () => {
    expect(() =>
      validateProductionWebEnvironment(realEnvironment),
    ).not.toThrow();
  });

  it("accepts a public competition deployment without account credentials", () => {
    const environment = {
      NODE_ENV: "production",
      VERCEL: "1",
      ORALSIGHT_WEB_MODE: "public",
      NEXT_PUBLIC_SITE_URL: "https://oralsight.vercel.app",
    };

    expect(() => validateProductionWebEnvironment(environment)).not.toThrow();
    expect(hostedWorkspaceEnabled(environment)).toBe(false);
  });

  it("requires a real HTTPS site origin in public mode", () => {
    expect(() =>
      validateProductionWebEnvironment({
        NODE_ENV: "production",
        VERCEL: "1",
        ORALSIGHT_WEB_MODE: "public",
        NEXT_PUBLIC_SITE_URL: "http://oralsight.test",
      }),
    ).toThrow(/NEXT_PUBLIC_SITE_URL.*HTTPS/);
  });

  it("keeps hosted accounts enabled by default", () => {
    expect(hostedWorkspaceEnabled(realEnvironment)).toBe(true);
  });

  it("rejects a missing production variable", () => {
    const environment: Record<string, string | undefined> = {
      ...realEnvironment,
    };
    delete environment.AUTH0_CLIENT_SECRET;
    expect(() => validateProductionWebEnvironment(environment)).toThrow(
      /AUTH0_CLIENT_SECRET/,
    );
  });

  it("allows explicit dummy values only for non-Vercel CI builds", () => {
    const warning = vi
      .spyOn(console, "warn")
      .mockImplementation(() => undefined);
    const environment = {
      ...realEnvironment,
      VERCEL: "0",
      CI: "true",
      ORALSIGHT_ALLOW_CI_DUMMY_WEB_ENV: "true",
      AUTH0_DOMAIN: "ci-identity.invalid",
      AUTH0_CLIENT_SECRET: "ci-client-secret",
      AUTH0_SECRET: "ci-secret",
      APP_BASE_URL: "https://ci-web.invalid",
      NEXT_PUBLIC_SITE_URL: "https://ci-web.invalid",
      ORALSIGHT_PLATFORM_API_URL: "https://ci-platform.invalid",
    };

    expect(() => validateProductionWebEnvironment(environment)).not.toThrow();
    expect(warning).toHaveBeenCalledOnce();
    warning.mockRestore();
  });

  it("does not allow the CI bypass on Vercel", () => {
    expect(() =>
      validateProductionWebEnvironment({
        ...realEnvironment,
        CI: "true",
        ORALSIGHT_ALLOW_CI_DUMMY_WEB_ENV: "true",
        AUTH0_DOMAIN: "ci-identity.invalid",
      }),
    ).toThrow(/placeholder/);
  });

  it("requires HTTPS for the platform API on Vercel", () => {
    expect(() =>
      validateProductionWebEnvironment({
        ...realEnvironment,
        ORALSIGHT_PLATFORM_API_URL: "http://api.oralsight.test",
      }),
    ).toThrow(/HTTPS/);
  });
});
