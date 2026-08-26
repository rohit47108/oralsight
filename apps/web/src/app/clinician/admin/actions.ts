"use server";

import { revalidatePath } from "next/cache";

import {
  PlatformApiError,
  decideClinicianVerification,
} from "@/lib/platform-api";
import { operationKeyFromForm } from "@/lib/operation-key";

export type DecisionState =
  | { status: "idle" }
  | { status: "saved"; message: string }
  | { status: "error"; message: string };

export async function decideVerificationAction(
  _previous: DecisionState,
  formData: FormData,
): Promise<DecisionState> {
  const operationKey = operationKeyFromForm(formData);
  const verificationId = String(formData.get("verificationId") ?? "");
  const status = String(formData.get("status") ?? "");
  const source = String(formData.get("source") ?? "").trim();
  const referenceId = String(formData.get("referenceId") ?? "").trim();
  const reviewerNotes = String(formData.get("reviewerNotes") ?? "").trim();
  const decisionReason = String(formData.get("decisionReason") ?? "").trim();
  if (
    !["verified", "rejected"].includes(status) ||
    source.length < 1 ||
    referenceId.length < 4 ||
    (status === "rejected" && decisionReason.length < 2)
  ) {
    return {
      status: "error",
      message: "Complete the review evidence and decision.",
    };
  }
  if (!operationKey) {
    return {
      status: "error",
      message: "Reload this page before trying again.",
    };
  }
  try {
    await decideClinicianVerification(
      verificationId,
      {
        status: status as "verified" | "rejected",
        decisionReason: decisionReason || null,
        evidence: {
          source,
          referenceId,
          checkedAt: new Date().toISOString(),
          reviewerNotes: reviewerNotes || null,
        },
      },
      operationKey,
    );
    revalidatePath("/clinician/admin");
    return {
      status: "saved",
      message:
        status === "verified"
          ? "Credentials approved. Assign the clinician role in the sign-in provider; access opens only after a fresh signed role is observed."
          : "Verification decision recorded.",
    };
  } catch (error) {
    return {
      status: "error",
      message:
        error instanceof PlatformApiError
          ? error.message
          : "The verification decision could not be recorded.",
    };
  }
}
