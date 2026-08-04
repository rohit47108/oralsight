export interface ApiTransportPolicy {
  isLoopback: boolean;
  url: URL;
}

export function isLoopbackHostname(hostname: string): boolean {
  const normalized = hostname.toLowerCase().replace(/^\[|\]$/g, "");
  if (normalized === "localhost" || normalized === "::1") return true;
  const ipv4 = normalized.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/);
  if (!ipv4) return false;
  return (
    Number(ipv4[1]) === 127 &&
    ipv4.slice(1).every((part) => Number(part) <= 255)
  );
}

export function enforceApiTransport(endpoint: string): ApiTransportPolicy {
  let url: URL;
  try {
    url = new URL(endpoint);
  } catch {
    throw new Error("The inference service URL is invalid.");
  }
  if (url.username || url.password) {
    throw new Error("The inference service URL must not contain credentials.");
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    throw new Error("The inference service URL must use HTTP or HTTPS.");
  }
  const isLoopback = isLoopbackHostname(url.hostname);
  if (!isLoopback && url.protocol !== "https:") {
    throw new Error("Non-loopback inference services require HTTPS.");
  }
  return { isLoopback, url };
}
