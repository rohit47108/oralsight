import { NextResponse } from "next/server";

import { PlatformApiError, exchangeShareSecret } from "@/lib/platform-api";
import { parseOperationKey } from "@/lib/operation-key";

const SHARE_COOKIE = "stoma3d_share_token";

export async function POST(request: Request) {
  const payload: unknown = await request.json().catch(() => null);
  if (
    !payload ||
    typeof payload !== "object" ||
    !("shareId" in payload) ||
    !("secret" in payload) ||
    !("operationKey" in payload) ||
    typeof payload.shareId !== "string" ||
    typeof payload.secret !== "string" ||
    !parseOperationKey(payload.operationKey)
  ) {
    return NextResponse.json(
      { message: "This share link is incomplete." },
      { status: 400 },
    );
  }
  const operationKey = parseOperationKey(payload.operationKey)!;
  try {
    const exchange = await exchangeShareSecret(
      { shareId: payload.shareId, secret: payload.secret },
      operationKey,
    );
    const response = NextResponse.json({ opened: true });
    response.cookies.set(SHARE_COOKIE, exchange.exchangeToken, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "strict",
      // The viewer page and its same-origin /api/shared byte routes both need
      // this HttpOnly token. A /shared-only cookie is never sent to /api/shared.
      path: "/",
      expires: new Date(exchange.expiresAt),
    });
    response.headers.set("Cache-Control", "no-store");
    return response;
  } catch (error) {
    const status = error instanceof PlatformApiError ? error.status : 503;
    return NextResponse.json(
      {
        message:
          status === 404 || status === 410
            ? "This share link is invalid, expired, or has reached its opening limit."
            : "The shared record could not be opened. Try again.",
      },
      { status },
    );
  }
}
