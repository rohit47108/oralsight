import {
  protectedContentError,
  protectedContentResponse,
} from "@/lib/content-proxy";
import { getClinicianCaptureViewContent } from "@/lib/platform-api";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ reviewId: string; captureViewId: string }> },
) {
  const { reviewId, captureViewId } = await params;
  try {
    return protectedContentResponse(
      await getClinicianCaptureViewContent(reviewId, captureViewId),
    );
  } catch (error) {
    return protectedContentError(error);
  }
}
