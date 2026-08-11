"use server";

import { revalidatePath } from "next/cache";

import {
  PlatformApiError,
  createReviewAnnotation,
  shareResourceTypeSchema,
  updateClinicianReviewStatus,
} from "@/lib/platform-api";
import { operationKeyFromForm } from "@/lib/operation-key";

export type ReviewActionState =
  | { status: "idle" }
  | { status: "saved"; message: string }
  | { status: "error"; message: string };

export async function updateReviewStatusAction(
  _previous: ReviewActionState,
  formData: FormData,
): Promise<ReviewActionState> {
  const operationKey = operationKeyFromForm(formData);
  const reviewId = String(formData.get("reviewId") ?? "");
  const status = String(formData.get("status") ?? "");
  const summary = String(formData.get("summary") ?? "").trim();
  if (!["in_review", "completed", "declined"].includes(status)) {
    return { status: "error", message: "Choose a valid review status." };
  }
  if (!operationKey) {
    return {
      status: "error",
      message: "Reload this page before trying again.",
    };
  }
  if (summary.length > 4000) {
    return {
      status: "error",
      message: "Keep the review summary under 4,000 characters.",
    };
  }
  try {
    await updateClinicianReviewStatus(
      reviewId,
      {
        status: status as "in_review" | "completed" | "declined",
        summary: summary || null,
      },
      operationKey,
    );
    revalidatePath("/clinician/reviews");
    return { status: "saved", message: "Review status updated." };
  } catch (error) {
    return {
      status: "error",
      message:
        error instanceof PlatformApiError
          ? error.message
          : "The review status could not be updated.",
    };
  }
}

export async function createAnnotationAction(
  _previous: ReviewActionState,
  formData: FormData,
): Promise<ReviewActionState> {
  const operationKey = operationKeyFromForm(formData);
  const reviewId = String(formData.get("reviewId") ?? "");
  const resourceType = shareResourceTypeSchema.safeParse(
    formData.get("resourceType"),
  );
  const resourceId = String(formData.get("resourceId") ?? "");
  const kind = String(formData.get("kind") ?? "");
  const body = String(formData.get("body") ?? "").trim();
  const annotationKinds = [
    "note",
    "question",
    "follow_up",
    "measurement_context",
    "outline_adjustment",
    "location_correction",
    "insufficient_scan",
    "date_comparison",
  ] as const;
  type AnnotationKind = (typeof annotationKinds)[number];
  if (
    !resourceType.success ||
    !annotationKinds.includes(kind as AnnotationKind) ||
    body.length < 1 ||
    body.length > 4000
  ) {
    return {
      status: "error",
      message: "Complete the annotation before saving.",
    };
  }
  if (!operationKey) {
    return {
      status: "error",
      message: "Reload this page before trying again.",
    };
  }
  try {
    await createReviewAnnotation(
      reviewId,
      {
        resource: { resourceType: resourceType.data, resourceId },
        kind: kind as AnnotationKind,
        body,
      },
      operationKey,
    );
    revalidatePath("/clinician/reviews");
    return { status: "saved", message: "Annotation added to this review." };
  } catch (error) {
    return {
      status: "error",
      message:
        error instanceof PlatformApiError
          ? error.message
          : "The annotation could not be saved.",
    };
  }
}
