import {
  protectedContentError,
  protectedContentResponse,
} from "@/lib/content-proxy";
import { getReportContent } from "@/lib/platform-api";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  try {
    return protectedContentResponse(await getReportContent(id));
  } catch (error) {
    return protectedContentError(error);
  }
}
