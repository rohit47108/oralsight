"use server";

import { getProductContext } from "@/lib/product-auth";
import {
  PlatformApiError,
  requestAccountDeletion,
  updateAnalyticsConsent,
} from "@/lib/platform-api";
import { operationKeyFromForm } from "@/lib/operation-key";

export type DeleteAccountState = {
  status: "idle" | "error" | "accepted";
  message: string;
  requestId?: string;
};

export type AnalyticsConsentState = {
  status: "idle" | "error" | "saved";
  message: string;
  enabled?: boolean;
  updatedAt?: string;
};

export async function saveAnalyticsConsent(
  _previous: AnalyticsConsentState,
  formData: FormData,
): Promise<AnalyticsConsentState> {
  const context = await getProductContext();
  if (context.state !== "ready") {
    return {
      status: "error",
      message: "Your account could not be verified. Sign in again and retry.",
    };
  }
  const enabled = formData.get("analyticsEnabled") === "on";
  try {
    const consent = await updateAnalyticsConsent(enabled);
    return {
      status: "saved",
      message: enabled
        ? "Private product analytics are on."
        : "Private product analytics are off.",
      enabled: consent.enabled,
      updatedAt: consent.updatedAt ?? undefined,
    };
  } catch (error) {
    return {
      status: "error",
      message:
        error instanceof PlatformApiError
          ? error.message
          : "This privacy setting could not be saved.",
    };
  }
}

export async function requestDeleteAll(
  _previous: DeleteAccountState,
  formData: FormData,
): Promise<DeleteAccountState> {
  const operationKey = operationKeyFromForm(formData);
  if (formData.get("confirmation") !== "DELETE") {
    return {
      status: "error",
      message: "Type DELETE exactly to confirm this request.",
    };
  }
  if (!operationKey) {
    return {
      status: "error",
      message: "Reload this page before trying again.",
    };
  }
  const context = await getProductContext();
  if (context.state !== "ready") {
    return {
      status: "error",
      message: "Your account could not be verified. Sign in again and retry.",
    };
  }
  try {
    const request = await requestAccountDeletion(operationKey);
    return {
      status: "accepted",
      message:
        "Deletion was requested. OralSight will remove account records and stored blobs through the deletion job.",
      requestId: request.requestId,
    };
  } catch (error) {
    return {
      status: "error",
      message:
        error instanceof PlatformApiError
          ? error.message
          : "Deletion could not be requested. No records were changed.",
    };
  }
}
