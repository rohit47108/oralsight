export type ClinicianApplicationHistory =
  | { state: "unavailable" }
  | { state: "none" }
  | {
      state: "loaded";
      status: "pending" | "verified" | "rejected";
    };

export type ClinicianApplicationMode =
  | "unavailable"
  | "awaiting_review"
  | "approved"
  | "invitation_required"
  | "apply"
  | "reapply";

export type ClinicianPendingMode =
  | "unavailable"
  | "missing"
  | "awaiting_review"
  | "ready_to_activate"
  | "rejected";

export function clinicianApplicationMode(
  history: ClinicianApplicationHistory,
  invitationReady: boolean,
): ClinicianApplicationMode {
  if (history.state === "unavailable") return "unavailable";
  if (history.state === "loaded" && history.status === "pending") {
    return "awaiting_review";
  }
  if (history.state === "loaded" && history.status === "verified") {
    return "approved";
  }
  if (!invitationReady) return "invitation_required";
  if (history.state === "loaded" && history.status === "rejected") {
    return "reapply";
  }
  return "apply";
}

export function clinicianPendingMode(
  history: ClinicianApplicationHistory,
): ClinicianPendingMode {
  if (history.state === "unavailable") return "unavailable";
  if (history.state === "none") return "missing";
  if (history.status === "verified") return "ready_to_activate";
  if (history.status === "rejected") return "rejected";
  return "awaiting_review";
}
