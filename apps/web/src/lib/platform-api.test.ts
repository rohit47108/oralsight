import { describe, expect, it } from "vitest";

import { platformSchemasForTesting } from "@/lib/platform-api";

const CREATED_AT = "2026-08-04T12:00:00.000Z";
const SHA256 = "0".repeat(64);

describe("platform response boundaries", () => {
  it("accepts the fixed account roles", () => {
    expect(
      platformSchemasForTesting.me.parse({
        id: "person-1",
        role: "clinician_pending",
        status: "active",
        createdAt: "2026-08-04T12:00:00Z",
        deletionPending: false,
        requiredOidcRole: null,
        privilegedAccessReady: true,
        clinicianApplicationEligible: false,
      }).role,
    ).toBe("clinician_pending");
  });

  it("rejects an invented account role", () => {
    expect(() =>
      platformSchemasForTesting.me.parse({
        id: "person-1",
        role: "doctor",
        status: "active",
        createdAt: "2026-08-04T12:00:00Z",
        deletionPending: false,
        requiredOidcRole: null,
        privilegedAccessReady: true,
        clinicianApplicationEligible: false,
      }),
    ).toThrow();
  });

  it("rejects an incomplete scan payload", () => {
    expect(() =>
      platformSchemasForTesting.scanSession.parse({
        contractVersion: "2.0.0",
        scanSessionId: "scan-1",
        protocol: "standard_eight_region",
        status: "complete",
      }),
    ).toThrow();
  });

  it("accepts the consent binding returned with a real scan session", () => {
    const parsed = platformSchemasForTesting.scanSession.parse({
      contractVersion: "2.0.0",
      scanSessionId: "scan-1",
      consentRecordId: "consent-1",
      protocol: "standard_eight_region",
      status: "capturing",
      createdAt: CREATED_AT,
      updatedAt: CREATED_AT,
      completedAt: null,
    });

    expect(parsed.consentRecordId).toBe("consent-1");
  });

  it("accepts the capture transport status without weakening the stored contract", () => {
    const captureSet = {
      contractVersion: "2.0.0",
      captureSetId: "capture-set-1",
      scanSessionId: "scan-1",
      region: "dorsal_tongue",
      protocol: "standard_eight_region",
      primaryViewId: "view-1",
      views: [
        {
          captureViewId: "view-1",
          captureSetId: "capture-set-1",
          region: "dorsal_tongue",
          anatomicalSite: "dorsal_tongue",
          angle: "straight",
          asset: {
            assetId: "asset-1",
            mediaKind: "image",
            mimeType: "image/jpeg",
            byteSize: 24_000,
            sha256: SHA256,
            widthPx: 1200,
            heightPx: 900,
            durationMs: null,
            inputOrigin: "live_capture",
            encrypted: true,
            createdAt: CREATED_AT,
            retentionExpiresAt: null,
            uploadStatus: "available",
          },
          sourceVideoAssetId: null,
          qualityAccepted: true,
          qualityReasons: [],
          ordinal: 0,
          capturedAt: CREATED_AT,
        },
      ],
      complete: true,
      createdAt: CREATED_AT,
      updatedAt: CREATED_AT,
    };
    const parsed = platformSchemasForTesting.captureSet.parse(captureSet);
    expect(parsed.views[0].asset).not.toHaveProperty("uploadStatus");
    expect(() =>
      platformSchemasForTesting.captureSet.parse({
        ...captureSet,
        unexpected: true,
      }),
    ).toThrow();
    expect(() =>
      platformSchemasForTesting.captureSet.parse({
        ...captureSet,
        views: [
          {
            ...captureSet.views[0],
            asset: { ...captureSet.views[0].asset, uploadStatus: "trusted" },
          },
        ],
      }),
    ).toThrow();
  });

  it("accepts only the consent fields returned by the privacy endpoint", () => {
    expect(
      platformSchemasForTesting.analyticsConsent.parse({
        enabled: false,
        policyVersion: null,
        updatedAt: null,
      }).enabled,
    ).toBe(false);
    expect(() =>
      platformSchemasForTesting.analyticsConsent.parse({
        enabled: true,
        policyVersion: "analytics-v1",
        updatedAt: CREATED_AT,
        recordId: "must-not-be-here",
      }),
    ).toThrow();
  });

  it("accepts only privacy-thresholded analytics groups", () => {
    expect(
      platformSchemasForTesting.analyticsSummary.parse({
        days: 30,
        minimumGroupSize: 5,
        groups: [
          {
            name: "scan_completed",
            platform: "ios",
            outcome: "completed",
            count: 5,
          },
        ],
        generatedAt: CREATED_AT,
      }).groups[0].count,
    ).toBe(5);
    expect(() =>
      platformSchemasForTesting.analyticsSummary.parse({
        days: 30,
        minimumGroupSize: 5,
        groups: [
          {
            name: "scan_completed",
            platform: "ios",
            outcome: "completed",
            count: 4,
          },
        ],
        generatedAt: CREATED_AT,
      }),
    ).toThrow();
  });

  it("accepts a patient-authorized clinician review", () => {
    expect(
      platformSchemasForTesting.clinicianReview.parse({
        reviewId: "review-1",
        grantId: "grant-1",
        patientUserId: "patient-1",
        clinicianUserId: "clinician-1",
        status: "in_review",
        summary: null,
        resources: [{ resourceType: "report", resourceId: "report-1" }],
        annotations: [],
        grantExpiresAt: "2026-08-06T12:00:00Z",
        grantRevokedAt: null,
        createdAt: "2026-08-04T12:00:00Z",
        updatedAt: "2026-08-04T12:00:00Z",
        startedAt: "2026-08-04T12:00:00Z",
        completedAt: null,
        retentionExpiresAt: "2033-08-04T12:00:00Z",
        accessActive: true,
      }).status,
    ).toBe("in_review");
  });

  it("distinguishes approval from a currently verified clinician token role", () => {
    const parsed = platformSchemasForTesting.clinicianVerification.parse({
      verificationId: "verification-1",
      applicantUserId: "applicant-1",
      status: "verified",
      profession: "Dentist",
      licenseJurisdiction: "New Jersey",
      licenseNumberSuffix: "4821",
      organization: "Oral Health Research Clinic",
      applicantEvidenceRef: "credential-review-1",
      submittedAt: CREATED_AT,
      reviewerUserId: "admin-1",
      reviewerEvidence: {
        source: "State licensing registry",
        referenceId: "registry-check-1",
        checkedAt: CREATED_AT,
        reviewerNotes: null,
      },
      decisionReason: null,
      reviewedAt: CREATED_AT,
      retentionExpiresAt: "2033-08-04T12:00:00Z",
      identityRole: {
        requiredClaim: "https://stoma3d.app/roles",
        requiredValue: "clinician",
        observationStatus: "awaiting_token_observation",
        oidcRoleObservedAt: null,
        privilegedAccessReady: false,
      },
    });

    expect(parsed.identityRole.observationStatus).toBe(
      "awaiting_token_observation",
    );
    expect(parsed.identityRole.privilegedAccessReady).toBe(false);
  });

  it("rejects a shared record without the exact disclaimer", () => {
    expect(() =>
      platformSchemasForTesting.resourceView.parse({
        resourceType: "report",
        resourceId: "report-1",
        data: {},
        disclaimer: "Informational only.",
      }),
    ).toThrow();
  });

  it("rejects share records with unexpected fields", () => {
    expect(() =>
      platformSchemasForTesting.shareLink.parse({
        shareId: "share-1",
        patientUserId: "patient-1",
        status: "active",
        resources: [{ resourceType: "report", resourceId: "report-1" }],
        expiresAt: "2026-08-06T12:00:00Z",
        maxExchanges: 1,
        exchangeCount: 0,
        revokedAt: null,
        createdAt: "2026-08-04T12:00:00Z",
        retentionExpiresAt: "2026-09-06T12:00:00Z",
        active: true,
        secret: "must-not-be-returned",
      }),
    ).toThrow();
  });
});
