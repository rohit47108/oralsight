import { describe, expect, it } from "vitest";

import {
  clinicianApplicationMode,
  clinicianPendingMode,
} from "@/lib/clinician-application";

describe("clinician application routing", () => {
  it("never offers a second form while credential review is pending", () => {
    expect(
      clinicianApplicationMode({ state: "loaded", status: "pending" }, true),
    ).toBe("awaiting_review");
  });

  it("allows an invited applicant to resubmit after rejection", () => {
    expect(
      clinicianApplicationMode({ state: "loaded", status: "rejected" }, true),
    ).toBe("reapply");
  });

  it("does not open a form until the current token carries an invitation", () => {
    expect(clinicianApplicationMode({ state: "none" }, false)).toBe(
      "invitation_required",
    );
    expect(
      clinicianApplicationMode({ state: "loaded", status: "rejected" }, false),
    ).toBe("invitation_required");
  });

  it("fails closed when verification history cannot be checked", () => {
    expect(clinicianApplicationMode({ state: "unavailable" }, true)).toBe(
      "unavailable",
    );
  });
});

describe("clinician pending workspace state", () => {
  it("keeps a missing record distinct from a service failure", () => {
    expect(clinicianPendingMode({ state: "none" })).toBe("missing");
    expect(clinicianPendingMode({ state: "unavailable" })).toBe("unavailable");
  });

  it("only enables the activation step for an approved record", () => {
    expect(clinicianPendingMode({ state: "loaded", status: "pending" })).toBe(
      "awaiting_review",
    );
    expect(clinicianPendingMode({ state: "loaded", status: "verified" })).toBe(
      "ready_to_activate",
    );
    expect(clinicianPendingMode({ state: "loaded", status: "rejected" })).toBe(
      "rejected",
    );
  });
});
