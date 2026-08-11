import * as Linking from "expo-linking";

import type { OidcConfig } from "./auth";

export interface CloudConfig {
  platformBaseUrl: string;
  shareViewerBaseUrl: string;
  oidc: OidcConfig;
  requestTimeoutMs: number;
}

function isLoopback(url: URL): boolean {
  return ["127.0.0.1", "localhost", "[::1]"].includes(url.hostname);
}

function safeBaseUrl(raw: string, label: string): string {
  const url = new URL(raw);
  const loopback = url.protocol === "http:" && isLoopback(url);
  if (url.protocol !== "https:" && !loopback) {
    throw new Error(`${label} must use HTTPS outside local development.`);
  }
  if (url.username || url.password || url.search || url.hash) {
    throw new Error(
      `${label} cannot contain credentials, a query, or a fragment.`,
    );
  }
  return url.toString().replace(/\/$/, "");
}

export function readCloudConfig(): CloudConfig | null {
  const platformBaseUrl = process.env.EXPO_PUBLIC_PLATFORM_URL?.trim();
  const issuer = process.env.EXPO_PUBLIC_OIDC_ISSUER?.trim();
  const clientId = process.env.EXPO_PUBLIC_OIDC_CLIENT_ID?.trim();
  if (!platformBaseUrl || !issuer || !clientId) return null;

  const platform = safeBaseUrl(platformBaseUrl, "Platform URL");
  const issuerUrl = safeBaseUrl(issuer, "OIDC issuer");
  const allowInsecureLoopback =
    isLoopback(new URL(platform)) && isLoopback(new URL(issuerUrl));
  const shareViewer = safeBaseUrl(
    process.env.EXPO_PUBLIC_SHARE_VIEWER_URL?.trim() ?? platform,
    "Share viewer URL",
  );
  const audience = process.env.EXPO_PUBLIC_OIDC_AUDIENCE?.trim();
  return {
    platformBaseUrl: platform,
    shareViewerBaseUrl: shareViewer,
    requestTimeoutMs: 20_000,
    oidc: {
      issuer: issuerUrl,
      clientId,
      redirectUri: Linking.createURL("auth/callback"),
      scopes: ["openid", "profile", "email", "offline_access"],
      ...(audience ? { audience } : {}),
      allowInsecureLoopback,
    },
  };
}

export function cloudConfigurationStatus(): {
  configured: boolean;
  message: string;
} {
  try {
    return readCloudConfig()
      ? { configured: true, message: "Account services are configured." }
      : {
          configured: false,
          message:
            "Account services are not configured in this build. Local scans still work.",
        };
  } catch (error) {
    return {
      configured: false,
      message:
        error instanceof Error
          ? error.message
          : "Account services are not configured correctly.",
    };
  }
}
