import {
  getAccountDeletionRequest,
  PlatformApiError,
} from "@/lib/platform-api";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  try {
    const deletion = await getAccountDeletionRequest(id);
    return Response.json(deletion, {
      headers: { "Cache-Control": "private, no-store, max-age=0" },
    });
  } catch (error) {
    const status = error instanceof PlatformApiError ? error.status : 503;
    return Response.json(
      { message: "Deletion status could not be checked." },
      {
        status,
        headers: { "Cache-Control": "private, no-store, max-age=0" },
      },
    );
  }
}
