import { z } from "zod";

import { CloudError } from "./errors";
import { meResponseSchema } from "./contracts";

export interface OidcConfig {
  issuer: string;
  clientId: string;
  redirectUri: string;
  scopes: readonly string[];
  audience?: string;
  authorizationEndpoint?: string;
  tokenEndpoint?: string;
  endSessionEndpoint?: string;
  allowInsecureLoopback?: boolean;
}

export interface OidcDiscovery {
  issuer: string;
  authorizationEndpoint: string;
  tokenEndpoint: string;
  endSessionEndpoint?: string;
}

export interface PkceCryptoAdapter {
  randomBytes(length: number): Uint8Array | Promise<Uint8Array>;
  sha256(value: Uint8Array): Promise<Uint8Array>;
}

export interface AuthorizationRequest {
  authorizationUrl: string;
  state: string;
  nonce: string;
  codeVerifier: string;
  codeChallenge: string;
}

export interface AuthorizationCallback {
  code: string;
  state: string;
}

export interface TokenSet {
  accessToken: string;
  refreshToken?: string;
  tokenType: "Bearer";
  scopes: string[];
  expiresAt: number;
}

export interface SecureKeyValueAdapter {
  getItem(key: string): Promise<string | null>;
  setItem(key: string, value: string): Promise<void>;
  deleteItem(key: string): Promise<void>;
}

const tokenResponseSchema = z
  .object({
    access_token: z.string().min(1),
    refresh_token: z.string().min(1).optional(),
    token_type: z.string().transform((value) => value.toLowerCase()),
    expires_in: z.number().int().positive().max(604_800),
    scope: z.string().optional(),
  })
  .passthrough();

const storedTokenSchema = z
  .object({
    accessToken: z.string().min(1),
    refreshToken: z.string().min(1).optional(),
    tokenType: z.literal("Bearer"),
    scopes: z.array(z.string().min(1)),
    expiresAt: z.number().int().positive(),
  })
  .strict();

const discoverySchema = z
  .object({
    issuer: z.string().url(),
    authorization_endpoint: z.string().url(),
    token_endpoint: z.string().url(),
    end_session_endpoint: z.string().url().optional(),
  })
  .passthrough();

function base64Url(value: Uint8Array): string {
  const alphabet =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
  let output = "";
  for (let index = 0; index < value.length; index += 3) {
    const a = value[index] ?? 0;
    const b = value[index + 1] ?? 0;
    const c = value[index + 2] ?? 0;
    const packed = (a << 16) | (b << 8) | c;
    output += alphabet[(packed >> 18) & 63];
    output += alphabet[(packed >> 12) & 63];
    output += index + 1 < value.length ? alphabet[(packed >> 6) & 63] : "=";
    output += index + 2 < value.length ? alphabet[packed & 63] : "=";
  }
  return output.replace(/=/g, "").replace(/\+/g, "-").replace(/\//g, "_");
}

function isLoopback(url: URL): boolean {
  return ["127.0.0.1", "localhost", "[::1]"].includes(url.hostname);
}

function requireSecureEndpoint(
  raw: string,
  allowInsecureLoopback: boolean | undefined,
): URL {
  const url = new URL(raw);
  if (
    url.protocol !== "https:" &&
    !(allowInsecureLoopback && url.protocol === "http:" && isLoopback(url))
  ) {
    throw new Error("OIDC endpoints must use HTTPS.");
  }
  return url;
}

export function validateOidcConfig(config: OidcConfig): URL {
  if (!config.clientId.trim() || config.clientId.length > 256) {
    throw new Error("OIDC clientId is required.");
  }
  if (!config.scopes.includes("openid")) {
    throw new Error("OIDC scopes must include openid.");
  }
  const issuer = requireSecureEndpoint(
    config.issuer,
    config.allowInsecureLoopback,
  );
  if (issuer.search || issuer.hash) {
    throw new Error("OIDC issuer cannot contain a query or fragment.");
  }
  const redirect = new URL(config.redirectUri);
  if (
    redirect.protocol === "http:" &&
    !(config.allowInsecureLoopback && isLoopback(redirect))
  ) {
    throw new Error("OIDC redirect must use an app scheme or HTTPS.");
  }
  if (!redirect.protocol) throw new Error("OIDC redirect is invalid.");
  for (const endpoint of [
    config.authorizationEndpoint,
    config.tokenEndpoint,
    config.endSessionEndpoint,
  ]) {
    if (endpoint) requireSecureEndpoint(endpoint, config.allowInsecureLoopback);
  }
  return issuer;
}

export async function discoverOidc(
  config: OidcConfig,
  fetchImpl: typeof fetch = fetch,
): Promise<OidcDiscovery> {
  const issuer = validateOidcConfig(config);
  if (config.authorizationEndpoint && config.tokenEndpoint) {
    return {
      issuer: issuer.toString().replace(/\/$/, ""),
      authorizationEndpoint: config.authorizationEndpoint,
      tokenEndpoint: config.tokenEndpoint,
      ...(config.endSessionEndpoint
        ? { endSessionEndpoint: config.endSessionEndpoint }
        : {}),
    };
  }
  let response: Response;
  try {
    response = await fetchImpl(
      `${issuer.toString().replace(/\/$/, "")}/.well-known/openid-configuration`,
      {
        headers: { Accept: "application/json", "Cache-Control": "no-store" },
        redirect: "error",
      },
    );
  } catch (cause) {
    throw new CloudError({
      code: "offline",
      message: "The identity service could not be reached.",
      retryable: true,
      cause,
    });
  }
  if (!response.ok) {
    throw new CloudError({
      code: "unauthenticated",
      message: "The identity service is not available.",
      status: response.status,
      retryable: response.status >= 500,
    });
  }
  const parsed = discoverySchema.safeParse(await response.json());
  if (!parsed.success) {
    throw new CloudError({
      code: "invalid_response",
      message: "The identity service configuration is invalid.",
    });
  }
  const expectedIssuer = issuer.toString().replace(/\/$/, "");
  if (parsed.data.issuer.replace(/\/$/, "") !== expectedIssuer) {
    throw new CloudError({
      code: "invalid_response",
      message: "The identity service issuer did not match.",
    });
  }
  requireSecureEndpoint(
    parsed.data.authorization_endpoint,
    config.allowInsecureLoopback,
  );
  requireSecureEndpoint(
    parsed.data.token_endpoint,
    config.allowInsecureLoopback,
  );
  return {
    issuer: expectedIssuer,
    authorizationEndpoint: parsed.data.authorization_endpoint,
    tokenEndpoint: parsed.data.token_endpoint,
    ...(parsed.data.end_session_endpoint
      ? { endSessionEndpoint: parsed.data.end_session_endpoint }
      : {}),
  };
}

function endpointConfig(
  config: OidcConfig,
  discovery: OidcDiscovery,
): OidcConfig {
  return {
    ...config,
    authorizationEndpoint: discovery.authorizationEndpoint,
    tokenEndpoint: discovery.tokenEndpoint,
    endSessionEndpoint: discovery.endSessionEndpoint,
  };
}

export async function createAuthorizationRequest(
  config: OidcConfig,
  crypto: PkceCryptoAdapter,
): Promise<AuthorizationRequest> {
  const issuer = validateOidcConfig(config);
  const state = base64Url(await crypto.randomBytes(24));
  const nonce = base64Url(await crypto.randomBytes(24));
  const codeVerifier = base64Url(await crypto.randomBytes(48));
  if (codeVerifier.length < 43 || codeVerifier.length > 128) {
    throw new Error("Invalid PKCE verifier length.");
  }
  const codeChallenge = base64Url(
    await crypto.sha256(new TextEncoder().encode(codeVerifier)),
  );
  const authorizationEndpoint =
    config.authorizationEndpoint ??
    `${issuer.toString().replace(/\/$/, "")}/authorize`;
  const url = new URL(authorizationEndpoint);
  url.searchParams.set("response_type", "code");
  url.searchParams.set("client_id", config.clientId);
  url.searchParams.set("redirect_uri", config.redirectUri);
  url.searchParams.set("scope", [...new Set(config.scopes)].join(" "));
  url.searchParams.set("state", state);
  url.searchParams.set("nonce", nonce);
  url.searchParams.set("code_challenge", codeChallenge);
  url.searchParams.set("code_challenge_method", "S256");
  if (config.audience) url.searchParams.set("audience", config.audience);
  return {
    authorizationUrl: url.toString(),
    state,
    nonce,
    codeVerifier,
    codeChallenge,
  };
}

export function validateAuthorizationCallback(
  callbackUrl: string,
  expectedState: string,
  expectedRedirectUri?: string,
): AuthorizationCallback {
  const url = new URL(callbackUrl);
  if (expectedRedirectUri) {
    const expected = new URL(expectedRedirectUri);
    if (
      url.protocol !== expected.protocol ||
      url.host !== expected.host ||
      url.pathname !== expected.pathname
    ) {
      throw new CloudError({
        code: "unauthenticated",
        message: "The sign-in response used an unexpected redirect.",
      });
    }
  }
  const state = url.searchParams.get("state") ?? "";
  if (!state || state !== expectedState) {
    throw new CloudError({
      code: "unauthenticated",
      message: "The sign-in response could not be verified.",
    });
  }
  if (url.searchParams.has("error")) {
    throw new CloudError({
      code: "unauthenticated",
      message: "Sign-in was not completed.",
    });
  }
  const code = url.searchParams.get("code") ?? "";
  if (!code) {
    throw new CloudError({
      code: "unauthenticated",
      message: "The sign-in response is missing a code.",
    });
  }
  return { code, state };
}

async function parseTokenResponse(
  response: Response,
  scopes: readonly string[],
  now: () => number,
  previousRefreshToken?: string,
): Promise<TokenSet> {
  if (!response.ok) {
    throw new CloudError({
      code: "unauthenticated",
      message: "Sign-in could not be completed.",
      status: response.status,
      retryable: response.status >= 500,
    });
  }
  const parsed = tokenResponseSchema.safeParse(await response.json());
  if (!parsed.success || parsed.data.token_type !== "bearer") {
    throw new CloudError({
      code: "invalid_response",
      message: "The identity service returned an invalid response.",
    });
  }
  return {
    accessToken: parsed.data.access_token,
    refreshToken: parsed.data.refresh_token ?? previousRefreshToken,
    tokenType: "Bearer",
    scopes: parsed.data.scope?.split(/\s+/).filter(Boolean) ?? [...scopes],
    expiresAt: now() + parsed.data.expires_in * 1000,
  };
}

export async function exchangeAuthorizationCode(options: {
  config: OidcConfig;
  code: string;
  codeVerifier: string;
  fetchImpl: typeof fetch;
  now?: () => number;
}): Promise<TokenSet> {
  const issuer = validateOidcConfig(options.config);
  const body = new URLSearchParams({
    grant_type: "authorization_code",
    client_id: options.config.clientId,
    code: options.code,
    code_verifier: options.codeVerifier,
    redirect_uri: options.config.redirectUri,
  });
  const endpoint =
    options.config.tokenEndpoint ??
    `${issuer.toString().replace(/\/$/, "")}/oauth/token`;
  const response = await options.fetchImpl(endpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      Accept: "application/json",
      "Cache-Control": "no-store",
    },
    body: body.toString(),
    redirect: "error",
  });
  return parseTokenResponse(
    response,
    options.config.scopes,
    options.now ?? Date.now,
  );
}

export async function refreshTokenSet(options: {
  config: OidcConfig;
  refreshToken: string;
  fetchImpl: typeof fetch;
  now?: () => number;
}): Promise<TokenSet> {
  const issuer = validateOidcConfig(options.config);
  const endpoint =
    options.config.tokenEndpoint ??
    `${issuer.toString().replace(/\/$/, "")}/oauth/token`;
  const response = await options.fetchImpl(endpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      Accept: "application/json",
      "Cache-Control": "no-store",
    },
    body: new URLSearchParams({
      grant_type: "refresh_token",
      client_id: options.config.clientId,
      refresh_token: options.refreshToken,
      scope: [...new Set(options.config.scopes)].join(" "),
    }).toString(),
    redirect: "error",
  });
  return parseTokenResponse(
    response,
    options.config.scopes,
    options.now ?? Date.now,
    options.refreshToken,
  );
}

export async function verifyPlatformAccessToken(options: {
  platformBaseUrl: string;
  accessToken: string;
  fetchImpl?: typeof fetch;
}): Promise<void> {
  const baseUrl = new URL(options.platformBaseUrl);
  if (baseUrl.protocol !== "https:" && !isLoopback(baseUrl)) {
    throw new Error("Platform URL must use HTTPS outside local development.");
  }
  let response: Response;
  try {
    response = await (options.fetchImpl ?? fetch)(
      `${baseUrl.toString().replace(/\/$/, "")}/v2/me`,
      {
        headers: {
          Accept: "application/json",
          Authorization: `Bearer ${options.accessToken}`,
          "Cache-Control": "no-store",
        },
        redirect: "error",
      },
    );
  } catch (cause) {
    throw new CloudError({
      code: "offline",
      message: "The account service could not verify this sign-in.",
      retryable: true,
      cause,
    });
  }
  if (!response.ok) {
    throw new CloudError({
      code:
        response.status === 401 || response.status === 403
          ? "unauthenticated"
          : "invalid_response",
      message: "The account service could not verify this sign-in.",
      status: response.status,
      retryable: response.status >= 500,
    });
  }
  const parsed = meResponseSchema.safeParse(
    await response.json().catch(() => null),
  );
  if (!parsed.success) {
    throw new CloudError({
      code: "invalid_response",
      message: "The account service returned an invalid verification response.",
    });
  }
}

export function withOidcDiscovery(
  config: OidcConfig,
  discovery: OidcDiscovery,
): OidcConfig {
  return endpointConfig(config, discovery);
}

export class TokenVault {
  constructor(
    private readonly storage: SecureKeyValueAdapter,
    private readonly key = "oralsight.cloud.oidc.tokens.v1",
    private readonly now: () => number = Date.now,
  ) {}

  async save(tokens: TokenSet): Promise<void> {
    const parsed = storedTokenSchema.parse(tokens);
    await this.storage.setItem(this.key, JSON.stringify(parsed));
  }

  async load(): Promise<TokenSet | null> {
    const raw = await this.storage.getItem(this.key);
    if (!raw) return null;
    try {
      return storedTokenSchema.parse(JSON.parse(raw));
    } catch {
      await this.storage.deleteItem(this.key);
      return null;
    }
  }

  async accessToken(minimumValidityMs = 30_000): Promise<string | null> {
    const value = await this.load();
    return value && value.expiresAt - this.now() > minimumValidityMs
      ? value.accessToken
      : null;
  }

  async clear(): Promise<void> {
    await this.storage.deleteItem(this.key);
  }
}
