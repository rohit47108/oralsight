import { NextRequest } from "next/server";

import { auth0 } from "./lib/auth0";
import { buildContentSecurityPolicy } from "./lib/content-security-policy";

export async function proxy(request: Request) {
  const nonce = Buffer.from(crypto.randomUUID()).toString("base64");
  const contentSecurityPolicy = buildContentSecurityPolicy(nonce);
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("Content-Security-Policy", contentSecurityPolicy);
  requestHeaders.set("x-nonce", nonce);
  const response = await auth0.middleware(
    new NextRequest(request, { headers: requestHeaders }),
  );
  response.headers.set("Content-Security-Policy", contentSecurityPolicy);
  return response;
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|sitemap.xml|robots.txt).*)",
  ],
};
