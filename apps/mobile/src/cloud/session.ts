import { sha256 } from "@noble/hashes/sha2.js";
import * as Crypto from "expo-crypto";
import * as SecureStore from "expo-secure-store";
import * as WebBrowser from "expo-web-browser";

import {
  TokenVault,
  createAuthorizationRequest,
  discoverOidc,
  exchangeAuthorizationCode,
  refreshTokenSet,
  validateAuthorizationCallback,
  verifyPlatformAccessToken,
  withOidcDiscovery,
  type SecureKeyValueAdapter,
  type TokenSet,
} from "./auth";
import { readCloudConfig } from "./config";
import { CloudError } from "./errors";

WebBrowser.maybeCompleteAuthSession();

const secureStorage: SecureKeyValueAdapter = {
  getItem: (key) => SecureStore.getItemAsync(key),
  setItem: (key, value) =>
    SecureStore.setItemAsync(key, value, {
      keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
    }),
  deleteItem: (key) => SecureStore.deleteItemAsync(key),
};

const tokenVault = new TokenVault(secureStorage);

let refreshPromise: Promise<TokenSet> | null = null;

async function configuredOidc() {
  const config = readCloudConfig();
  if (!config) {
    throw new CloudError({
      code: "upload_unavailable",
      message: "Account services are not configured in this build.",
    });
  }
  const discovery = await discoverOidc(config.oidc);
  return { cloud: config, oidc: withOidcDiscovery(config.oidc, discovery) };
}

export async function restoreCloudSession(): Promise<boolean> {
  return (await tokenVault.load()) !== null;
}

export async function signInToCloud(): Promise<TokenSet> {
  const { cloud, oidc } = await configuredOidc();
  const request = await createAuthorizationRequest(oidc, {
    randomBytes: (length) => Crypto.getRandomBytesAsync(length),
    sha256: async (value) => sha256(value),
  });
  const result = await WebBrowser.openAuthSessionAsync(
    request.authorizationUrl,
    oidc.redirectUri,
    { showInRecents: false },
  );
  if (result.type === "cancel" || result.type === "dismiss") {
    throw new CloudError({
      code: "cancelled",
      message: "Sign-in was cancelled.",
    });
  }
  if (result.type !== "success") {
    throw new CloudError({
      code: "unauthenticated",
      message: "Sign-in could not be completed.",
    });
  }
  const callback = validateAuthorizationCallback(
    result.url,
    request.state,
    oidc.redirectUri,
  );
  const tokens = await exchangeAuthorizationCode({
    config: oidc,
    code: callback.code,
    codeVerifier: request.codeVerifier,
    fetchImpl: fetch,
  });
  // The app treats OAuth tokens as opaque. It never parses or stores id_token
  // claims; the resource server verifies the access-token signature, issuer,
  // audience, and expiry before any credential is persisted on this device.
  await verifyPlatformAccessToken({
    platformBaseUrl: cloud.platformBaseUrl,
    accessToken: tokens.accessToken,
  });
  await tokenVault.save(tokens);
  return tokens;
}

export async function cloudAccessToken(
  minimumValidityMs = 60_000,
): Promise<string> {
  const tokens = await tokenVault.load();
  if (!tokens) {
    throw new CloudError({
      code: "unauthenticated",
      message: "Sign in to use account services.",
    });
  }
  if (tokens.expiresAt - Date.now() > minimumValidityMs) {
    return tokens.accessToken;
  }
  if (!tokens.refreshToken) {
    await tokenVault.clear();
    throw new CloudError({
      code: "unauthenticated",
      message: "Your session ended. Please sign in again.",
    });
  }
  refreshPromise ??= configuredOidc()
    .then(async ({ cloud, oidc }) => {
      const refreshed = await refreshTokenSet({
        config: oidc,
        refreshToken: tokens.refreshToken!,
        fetchImpl: fetch,
      });
      await verifyPlatformAccessToken({
        platformBaseUrl: cloud.platformBaseUrl,
        accessToken: refreshed.accessToken,
      });
      return refreshed;
    })
    .then(async (refreshed) => {
      await tokenVault.save(refreshed);
      return refreshed;
    })
    .catch(async (error: unknown) => {
      if (error instanceof CloudError && !error.retryable) {
        await tokenVault.clear();
      }
      throw error;
    })
    .finally(() => {
      refreshPromise = null;
    });
  return (await refreshPromise).accessToken;
}

export async function signOutOfCloud(): Promise<void> {
  await tokenVault.clear();
}

export async function clearCloudCredentials(): Promise<void> {
  await tokenVault.clear();
}
