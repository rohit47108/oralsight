const REQUIRED_WEB_ENVIRONMENT = [
  "AUTH0_DOMAIN",
  "AUTH0_CLIENT_ID",
  "AUTH0_CLIENT_SECRET",
  "AUTH0_SECRET",
  "AUTH0_AUDIENCE",
  "APP_BASE_URL",
  "NEXT_PUBLIC_SITE_URL",
  "STOMA3D_PLATFORM_API_URL",
] as const;

type RequiredVariable = (typeof REQUIRED_WEB_ENVIRONMENT)[number];
type Environment = Record<string, string | undefined>;

const PLACEHOLDER_PATTERN =
  /(?:^ci-|replace|change[-_ ]?me|your[-_ ]?tenant|dummy|\.invalid(?:$|[/:])|example\.(?:com|net|org)(?:$|[/:]))/i;

function requireValue(
  environment: Environment,
  name: RequiredVariable,
): string {
  const value = environment[name]?.trim();
  if (!value) {
    throw new Error(
      `[Stoma3D web] Missing required production environment variable: ${name}`,
    );
  }
  return value;
}

function requireOrigin(
  name: "APP_BASE_URL" | "NEXT_PUBLIC_SITE_URL" | "STOMA3D_PLATFORM_API_URL",
  value: string,
  requireHttps: boolean,
): void {
  let parsed: URL;
  try {
    parsed = new URL(value);
  } catch {
    throw new Error(`[Stoma3D web] ${name} must be an absolute URL.`);
  }
  if (parsed.username || parsed.password) {
    throw new Error(`[Stoma3D web] ${name} must not contain credentials.`);
  }
  if (requireHttps && parsed.protocol !== "https:") {
    throw new Error(`[Stoma3D web] ${name} must use HTTPS on Vercel.`);
  }
  if (!requireHttps && !["http:", "https:"].includes(parsed.protocol)) {
    throw new Error(`[Stoma3D web] ${name} must use HTTP or HTTPS.`);
  }
}

export function hostedWorkspaceEnabled(
  environment: Environment = process.env,
): boolean {
  const mode = environment.STOMA3D_WEB_MODE?.trim().toLowerCase();
  if (mode === "public") return false;
  if (mode === "hosted") return true;
  return REQUIRED_WEB_ENVIRONMENT.every((name) =>
    Boolean(environment[name]?.trim()),
  );
}

export function validateProductionWebEnvironment(
  environment: Environment = process.env,
): void {
  const isVercelBuild = environment.VERCEL === "1";
  const isProductionBuild =
    environment.NODE_ENV === "production" || isVercelBuild;
  if (!isProductionBuild) return;

  if (environment.STOMA3D_WEB_MODE?.trim().toLowerCase() === "public") {
    const siteUrl = requireValue(environment, "NEXT_PUBLIC_SITE_URL");
    if (PLACEHOLDER_PATTERN.test(siteUrl)) {
      throw new Error(
        "[Stoma3D web] NEXT_PUBLIC_SITE_URL still contains a placeholder value.",
      );
    }
    requireOrigin("NEXT_PUBLIC_SITE_URL", siteUrl, isVercelBuild);
    return;
  }

  const allowCiDummyValues =
    environment.STOMA3D_ALLOW_CI_DUMMY_WEB_ENV === "true" &&
    environment.CI === "true" &&
    !isVercelBuild;

  const values = Object.fromEntries(
    REQUIRED_WEB_ENVIRONMENT.map((name) => [
      name,
      requireValue(environment, name),
    ]),
  ) as Record<RequiredVariable, string>;

  if (!allowCiDummyValues) {
    for (const name of REQUIRED_WEB_ENVIRONMENT) {
      if (PLACEHOLDER_PATTERN.test(values[name])) {
        throw new Error(
          `[Stoma3D web] ${name} still contains a placeholder value.`,
        );
      }
    }
    if (!/^[a-f0-9]{64,}$/i.test(values.AUTH0_SECRET)) {
      throw new Error(
        "[Stoma3D web] AUTH0_SECRET must be at least 32 random bytes encoded as hexadecimal.",
      );
    }
  }

  if (
    values.AUTH0_DOMAIN.includes("://") ||
    !/^[a-z0-9.-]+$/i.test(values.AUTH0_DOMAIN)
  ) {
    throw new Error(
      "[Stoma3D web] AUTH0_DOMAIN must be a hostname without a protocol or path.",
    );
  }

  requireOrigin("APP_BASE_URL", values.APP_BASE_URL, isVercelBuild);
  requireOrigin(
    "NEXT_PUBLIC_SITE_URL",
    values.NEXT_PUBLIC_SITE_URL,
    isVercelBuild,
  );
  requireOrigin(
    "STOMA3D_PLATFORM_API_URL",
    values.STOMA3D_PLATFORM_API_URL,
    isVercelBuild,
  );

  if (allowCiDummyValues) {
    console.warn(
      "[Stoma3D web] Explicit CI-only dummy environment enabled. Vercel deployments cannot use this bypass.",
    );
  }
}

export const productionEnvironmentForTesting = {
  requiredNames: REQUIRED_WEB_ENVIRONMENT,
};
