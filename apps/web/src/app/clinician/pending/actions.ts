"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import {
  activateCurrentClinicianVerification,
  PlatformApiError,
} from "@/lib/platform-api";

export type ActivationState =
  { status: "idle" } | { status: "error"; message: string };

export async function activateClinicianAction(
  _previous: ActivationState,
): Promise<ActivationState> {
  void _previous;
  try {
    await activateCurrentClinicianVerification();
  } catch (error) {
    if (
      error instanceof PlatformApiError &&
      error.code === "oidc_role_required"
    ) {
      return {
        status: "error",
        message:
          "Clinician access is not in your current sign-in yet. Ask the account administrator to assign it, then sign out and back in.",
      };
    }
    return {
      status: "error",
      message:
        error instanceof PlatformApiError
          ? error.message
          : "Secure access could not be checked.",
    };
  }
  revalidatePath("/clinician");
  redirect("/clinician/reviews");
}
