import { cache } from "react";

import { auth0 } from "@/lib/auth0";
import {
  PlatformApiError,
  getMe,
  type PlatformMe,
  type UserRole,
} from "@/lib/platform-api";
import { hostedWorkspaceEnabled } from "@/lib/production-env";

export type ViewerIdentity = {
  displayName: string;
  email: string | null;
};

export type ProductContext =
  | { state: "signed_out" }
  | {
      state: "service_unavailable";
      identity: ViewerIdentity;
      error: PlatformApiError;
    }
  | {
      state: "ready";
      identity: ViewerIdentity;
      account: PlatformMe;
    };

export type ProductArea = "patient" | "shared" | "clinician";

export function productAreaForRole(role: UserRole): ProductArea {
  if (role === "patient") return "patient";
  if (role === "share_viewer") return "shared";
  return "clinician";
}

export function productHomeForRole(role: UserRole): string {
  if (role === "patient") return "/app/overview";
  if (role === "share_viewer") return "/shared";
  if (role === "clinician_pending") return "/clinician/pending";
  if (role === "admin") return "/clinician/admin";
  return "/clinician/reviews";
}

export function productHomeForAccount(
  account: Pick<
    PlatformMe,
    "role" | "requiredOidcRole" | "privilegedAccessReady"
  >,
): string {
  if (account.requiredOidcRole && !account.privilegedAccessReady) {
    return "/clinician/access-setup";
  }
  return productHomeForRole(account.role);
}

function identityFromUser(user: Record<string, unknown>): ViewerIdentity {
  const name = typeof user.name === "string" ? user.name.trim() : "";
  const email = typeof user.email === "string" ? user.email.trim() : "";
  return {
    displayName: name || email || "OralSight user",
    email: email || null,
  };
}

export const getProductContext = cache(async (): Promise<ProductContext> => {
  if (!hostedWorkspaceEnabled()) return { state: "signed_out" };
  const session = await auth0.getSession();
  if (!session) return { state: "signed_out" };
  const identity = identityFromUser(session.user);
  try {
    const account = await getMe();
    return { state: "ready", identity, account };
  } catch (error) {
    const apiError =
      error instanceof PlatformApiError
        ? error
        : new PlatformApiError(
            "Your OralSight account could not be checked. Try again.",
            "account_check_failed",
            503,
          );
    return { state: "service_unavailable", identity, error: apiError };
  }
});
