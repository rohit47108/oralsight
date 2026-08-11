import { PlatformApiError } from "@/lib/platform-api";

const SAFE_RESPONSE_HEADERS = [
  "content-type",
  "content-length",
  "content-disposition",
  "accept-ranges",
  "content-range",
] as const;

export function protectedContentResponse(upstream: Response): Response {
  const headers = new Headers();
  for (const name of SAFE_RESPONSE_HEADERS) {
    const value = upstream.headers.get(name);
    if (value) headers.set(name, value);
  }
  headers.set("Cache-Control", "private, no-store, max-age=0");
  headers.set("Pragma", "no-cache");
  headers.set("X-Content-Type-Options", "nosniff");
  return new Response(upstream.body, {
    status: upstream.status,
    headers,
  });
}

export function protectedContentError(error: unknown): Response {
  const status =
    error instanceof PlatformApiError &&
    [400, 401, 403, 404, 410].includes(error.status)
      ? error.status
      : 503;
  return Response.json(
    {
      error:
        status === 404 || status === 410
          ? "file_unavailable"
          : "file_request_failed",
      message:
        status === 404 || status === 410
          ? "This file is no longer available."
          : "This protected file could not be opened.",
    },
    {
      status,
      headers: {
        "Cache-Control": "private, no-store, max-age=0",
        "X-Content-Type-Options": "nosniff",
      },
    },
  );
}
