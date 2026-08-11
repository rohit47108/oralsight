import {
  protectedContentError,
  protectedContentResponse,
} from "@/lib/content-proxy";
import { getClinicianReviewReportContent } from "@/lib/platform-api";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ reviewId: string; reportId: string }> },
) {
  const { reviewId, reportId } = await params;
  try {
    return protectedContentResponse(
      await getClinicianReviewReportContent(reviewId, reportId),
    );
  } catch (error) {
    return protectedContentError(error);
  }
}
