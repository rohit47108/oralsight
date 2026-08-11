import type { ShareCreateResponse } from "./contracts";

export function buildShareUrl(
  viewerBaseUrl: string,
  response: ShareCreateResponse,
): string {
  const url = new URL(viewerBaseUrl);
  url.searchParams.set("id", response.share.shareId);
  const fragment = new URLSearchParams({
    [response.fragmentParameter]: response.fragmentSecret,
  });
  url.hash = fragment.toString();
  return url.toString();
}

export function shareSecretStaysInFragment(url: string): boolean {
  const parsed = new URL(url);
  return (
    parsed.searchParams.has("id") &&
    !parsed.searchParams.has("secret") &&
    new URLSearchParams(parsed.hash.replace(/^#/, "")).has("secret")
  );
}
