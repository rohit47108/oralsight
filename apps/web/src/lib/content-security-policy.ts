function origin(value: string | undefined): string | null {
  if (!value) return null;
  try {
    return new URL(value).origin;
  } catch {
    return null;
  }
}

function auth0Origin(domain: string | undefined): string | null {
  if (!domain || !/^[a-z0-9.-]+$/i.test(domain)) return null;
  return `https://${domain}`;
}

export function buildContentSecurityPolicy(
  nonce: string,
  values: Readonly<Record<string, string | undefined>> = process.env,
): string {
  if (!/^[A-Za-z0-9+/=_-]{16,256}$/.test(nonce)) {
    throw new Error("A valid request nonce is required.");
  }
  const connectOrigins = [
    origin(values.ORALSIGHT_PLATFORM_API_URL),
    auth0Origin(values.AUTH0_DOMAIN),
  ].filter((value): value is string => Boolean(value));
  const isDevelopment = values.NODE_ENV === "development";

  return [
    "default-src 'self'",
    "base-uri 'self'",
    "object-src 'none'",
    "frame-ancestors 'none'",
    "form-action 'self'",
    "img-src 'self' blob: data:",
    "media-src 'self' blob:",
    "font-src 'self' data:",
    "style-src 'self' 'unsafe-inline'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${isDevelopment ? " 'unsafe-eval'" : ""}`,
    `connect-src 'self' ${connectOrigins.join(" ")}`.trim(),
    "worker-src 'self' blob:",
    ...(isDevelopment ? [] : ["upgrade-insecure-requests"]),
  ].join("; ");
}
