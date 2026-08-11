"use server";

import { revalidatePath } from "next/cache";

import {
  PlatformApiError,
  createAccessGrant,
  createShare,
  revokeAccessGrant,
  revokeShare,
  shareResourceTypeSchema,
} from "@/lib/platform-api";
import { operationKeyFromForm } from "@/lib/operation-key";

export type ShareActionState =
  | { status: "idle" }
  | { status: "error"; message: string }
  | {
      status: "created";
      shareId: string;
      fragmentSecret: string;
      expiresAt: string;
      maxExchanges: number;
    };

export type GrantActionState =
  | { status: "idle" }
  | { status: "error"; message: string }
  | { status: "created"; message: string };

export type RevokeActionState =
  | { status: "idle" }
  | { status: "revoked"; message: string }
  | { status: "error"; message: string };

function selectedResource(formData: FormData) {
  const manualResourceId = String(
    formData.get("manualResourceId") ?? "",
  ).trim();
  if (manualResourceId) {
    const manualResourceType = shareResourceTypeSchema.safeParse(
      formData.get("manualResourceType"),
    );
    return manualResourceType.success &&
      /^[A-Za-z0-9._:-]{1,64}$/.test(manualResourceId)
      ? { resourceType: manualResourceType.data, resourceId: manualResourceId }
      : null;
  }
  try {
    const choice: unknown = JSON.parse(
      String(formData.get("resourceChoice") ?? ""),
    );
    if (
      choice === null ||
      typeof choice !== "object" ||
      Array.isArray(choice)
    ) {
      return null;
    }
    const resourceType = shareResourceTypeSchema.safeParse(
      (choice as Record<string, unknown>).resourceType,
    );
    const resourceId = String(
      (choice as Record<string, unknown>).resourceId ?? "",
    );
    return resourceType.success && /^[A-Za-z0-9._:-]{1,64}$/.test(resourceId)
      ? { resourceType: resourceType.data, resourceId }
      : null;
  } catch {
    return null;
  }
}

export async function createShareAction(
  _previous: ShareActionState,
  formData: FormData,
): Promise<ShareActionState> {
  const operationKey = operationKeyFromForm(formData);
  const resource = selectedResource(formData);
  const expiresInSeconds = Number(formData.get("expiresInSeconds"));
  const maxExchanges = Number(formData.get("maxExchanges"));
  if (!resource) {
    return {
      status: "error",
      message: "Choose a record or enter a valid record ID.",
    };
  }
  if (!operationKey) {
    return {
      status: "error",
      message: "Reload this page before trying again.",
    };
  }
  if (![86_400, 259_200, 604_800].includes(expiresInSeconds)) {
    return { status: "error", message: "Choose a valid share expiry." };
  }
  if (
    !Number.isInteger(maxExchanges) ||
    maxExchanges < 1 ||
    maxExchanges > 10
  ) {
    return { status: "error", message: "Choose between 1 and 10 openings." };
  }
  try {
    const result = await createShare(
      {
        resources: [resource],
        expiresInSeconds,
        maxExchanges,
      },
      operationKey,
    );
    revalidatePath("/app/share");
    return {
      status: "created",
      shareId: result.share.shareId,
      fragmentSecret: result.fragmentSecret,
      expiresAt: result.share.expiresAt,
      maxExchanges: result.share.maxExchanges,
    };
  } catch (error) {
    return {
      status: "error",
      message:
        error instanceof PlatformApiError
          ? error.message
          : "The share could not be created. Try again.",
    };
  }
}

export async function revokeShareAction(
  _previous: RevokeActionState,
  formData: FormData,
): Promise<RevokeActionState> {
  const operationKey = operationKeyFromForm(formData);
  const shareId = String(formData.get("shareId") ?? "");
  if (!/^[A-Za-z0-9._:-]{1,64}$/.test(shareId)) {
    return { status: "error", message: "This share record is invalid." };
  }
  if (!operationKey) {
    return {
      status: "error",
      message: "Reload this page before trying again.",
    };
  }
  try {
    await revokeShare(shareId, operationKey);
    revalidatePath("/app/share");
    return { status: "revoked", message: "Link access ended." };
  } catch (error) {
    return {
      status: "error",
      message:
        error instanceof PlatformApiError
          ? error.message
          : "Link access could not be ended. Try again.",
    };
  }
}

export async function createGrantAction(
  _previous: GrantActionState,
  formData: FormData,
): Promise<GrantActionState> {
  const operationKey = operationKeyFromForm(formData);
  const clinicianUserId = String(formData.get("clinicianUserId") ?? "").trim();
  const resource = selectedResource(formData);
  const label = String(formData.get("label") ?? "")
    .trim()
    .slice(0, 120);
  if (!/^[A-Za-z0-9._:-]{1,64}$/.test(clinicianUserId) || !resource) {
    return {
      status: "error",
      message: "Enter valid clinician and record IDs.",
    };
  }
  if (!operationKey) {
    return {
      status: "error",
      message: "Reload this page before trying again.",
    };
  }
  try {
    const grant = await createAccessGrant(
      {
        clinicianUserId,
        resources: [resource],
        label: label || null,
        expiresAt: null,
      },
      operationKey,
    );
    revalidatePath("/app/share");
    return {
      status: "created",
      message: `Review access granted until ${new Date(grant.expiresAt).toLocaleDateString("en-US", { timeZone: "UTC" })}.`,
    };
  } catch (error) {
    return {
      status: "error",
      message:
        error instanceof PlatformApiError
          ? error.message
          : "Professional review access could not be granted.",
    };
  }
}

export async function revokeGrantAction(
  _previous: RevokeActionState,
  formData: FormData,
): Promise<RevokeActionState> {
  const operationKey = operationKeyFromForm(formData);
  const grantId = String(formData.get("grantId") ?? "");
  if (!/^[A-Za-z0-9._:-]{1,64}$/.test(grantId)) {
    return { status: "error", message: "This access record is invalid." };
  }
  if (!operationKey) {
    return {
      status: "error",
      message: "Reload this page before trying again.",
    };
  }
  try {
    await revokeAccessGrant(grantId, operationKey);
    revalidatePath("/app/share");
    return { status: "revoked", message: "Professional access ended." };
  } catch (error) {
    return {
      status: "error",
      message:
        error instanceof PlatformApiError
          ? error.message
          : "Professional access could not be ended. Try again.",
    };
  }
}
