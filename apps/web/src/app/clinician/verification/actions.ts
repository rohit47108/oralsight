"use server";

import { revalidatePath } from "next/cache";

import {
  PlatformApiError,
  submitClinicianVerification,
} from "@/lib/platform-api";
import { operationKeyFromForm } from "@/lib/operation-key";

export type VerificationActionState =
  | { status: "idle" }
  | { status: "error"; message: string }
  | { status: "submitted" };

function text(formData: FormData, name: string, maxLength: number): string {
  return String(formData.get(name) ?? "")
    .trim()
    .slice(0, maxLength);
}

export async function submitVerificationAction(
  _previous: VerificationActionState,
  formData: FormData,
): Promise<VerificationActionState> {
  const operationKey = operationKeyFromForm(formData);
  const profession = text(formData, "profession", 80);
  const licenseJurisdiction = text(formData, "licenseJurisdiction", 80);
  const licenseNumber = text(formData, "licenseNumber", 80);
  const organization = text(formData, "organization", 160);
  const applicantEvidenceRef = text(formData, "applicantEvidenceRef", 160);
  if (
    profession.length < 2 ||
    licenseJurisdiction.length < 2 ||
    licenseNumber.length < 4 ||
    applicantEvidenceRef.length < 4
  ) {
    return {
      status: "error",
      message: "Complete every required credential field.",
    };
  }
  if (!operationKey) {
    return {
      status: "error",
      message: "Reload this page before trying again.",
    };
  }
  try {
    await submitClinicianVerification(
      {
        profession,
        licenseJurisdiction,
        licenseNumber,
        organization: organization || null,
        applicantEvidenceRef,
      },
      operationKey,
    );
    revalidatePath("/clinician/verification");
    revalidatePath("/clinician/pending");
    return { status: "submitted" };
  } catch (error) {
    return {
      status: "error",
      message:
        error instanceof PlatformApiError
          ? error.message
          : "The verification request could not be submitted.",
    };
  }
}
