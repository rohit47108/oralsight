import { cookies } from "next/headers";

import {
  protectedContentError,
  protectedContentResponse,
} from "@/lib/content-proxy";
import {
  getShareViewerReportContent,
  PlatformApiError,
} from "@/lib/platform-api";

const SHARE_COOKIE = "oralsight_share_token";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const shareToken = (await cookies()).get(SHARE_COOKIE)?.value;
  if (!shareToken) {
    return protectedContentError(
      new PlatformApiError(
        "This shared file needs a current access link.",
        "share_session_required",
        401,
      ),
    );
  }
  try {
    return protectedContentResponse(
      await getShareViewerReportContent(shareToken, id),
    );
  } catch (error) {
    return protectedContentError(error);
  }
}
