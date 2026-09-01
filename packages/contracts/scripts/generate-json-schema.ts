import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { z, type ZodType } from "zod";

import {
  analysisRunSchema,
  analysisResultSchema,
  analyzeMetadataSchema,
  anatomicalSiteSchema,
  auditEventSchema,
  calibrationResultSchema,
  candidateObservationSchema,
  captureAngleSchema,
  captureAssetSchema,
  captureProtocolSchema,
  captureSetSchema,
  captureViewSchema,
  clinicianAnnotationSchema,
  compareMetadataSchema,
  comparisonResultSchema,
  jobSchema,
  jobStatusSchema,
  jobTypeSchema,
  lesionRecordSchema,
  matchDecisionSchema,
  matchProposalSchema,
  mediaKindSchema,
  modelCardSchema,
  mouthRegionSchema,
  platformApiAccessGrantResponseSchema,
  platformApiAnalysisRunResponseSchema,
  platformApiAnalyticsEventInputSchema,
  platformApiCaptureAssetResponseSchema,
  platformApiCaptureSetResponseSchema,
  platformApiClinicianIdentityRoleResponseSchema,
  platformApiClinicianReviewResponseSchema,
  platformApiClinicianVerificationQueueSchema,
  platformApiClinicianVerificationResponseSchema,
  platformApiConsentResponseSchema,
  platformApiDataExportArtifactResponseSchema,
  platformApiDeletionRequestResponseSchema,
  platformApiGeneratedArtifactResponseSchema,
  platformApiJobCreateSchema,
  platformApiJobResponseSchema,
  platformApiMatchDecisionResponseSchema,
  platformApiMatchProposalResponseSchema,
  platformApiMeResponseSchema,
  platformApiReportResponseSchema,
  platformApiReviewAnnotationResponseSchema,
  platformApiScanSessionResponseSchema,
  platformApiShareLinkResponseSchema,
  platformApiSyncOperationInputSchema,
  platformApiSyncPullResponseSchema,
  platformApiSyncPushResponseSchema,
  reportArtifactSchema,
  ruleReleaseSchema,
  shareGrantSchema,
  signedResultEnvelopeSchema,
  syncCursorSchema,
  syncOperationSchema,
} from "../src/index.ts";

function definition(schema: ZodType): Record<string, unknown> {
  const generated = z.toJSONSchema(schema) as Record<string, unknown>;
  const { $schema: _dialect, ...body } = generated;
  return body;
}

const v1Document = {
  $schema: "https://json-schema.org/draft/2020-12/schema",
  $id: "https://stoma3d.local/contracts/v1/stoma3d-contracts.schema.json",
  title: "Stoma3D public API contracts",
  description:
    "Generated from the canonical Zod schemas. This result is not a diagnosis.",
  $defs: {
    MouthRegion: definition(mouthRegionSchema),
    AnalyzeMetadata: definition(analyzeMetadataSchema),
    AnalysisResult: definition(analysisResultSchema),
    CompareMetadata: definition(compareMetadataSchema),
    ComparisonResult: definition(comparisonResultSchema),
    ModelCard: definition(modelCardSchema),
  },
};

const platformDocument = {
  $schema: "https://json-schema.org/draft/2020-12/schema",
  $id: "https://stoma3d.local/contracts/v2/stoma3d-platform-contracts.schema.json",
  title: "Stoma3D platform contracts v2",
  description:
    "Generated from the additive Stoma3D platform Zod schemas. This result is not a diagnosis.",
  $defs: {
    MouthRegion: definition(mouthRegionSchema),
    AnatomicalSite: definition(anatomicalSiteSchema),
    CaptureProtocol: definition(captureProtocolSchema),
    CaptureAngle: definition(captureAngleSchema),
    MediaKind: definition(mediaKindSchema),
    CaptureAsset: definition(captureAssetSchema),
    CaptureView: definition(captureViewSchema),
    CaptureSet: definition(captureSetSchema),
    CalibrationResult: definition(calibrationResultSchema),
    CandidateObservation: definition(candidateObservationSchema),
    AnalysisRun: definition(analysisRunSchema),
    MatchProposal: definition(matchProposalSchema),
    MatchDecision: definition(matchDecisionSchema),
    LesionRecord: definition(lesionRecordSchema),
    JobType: definition(jobTypeSchema),
    JobStatus: definition(jobStatusSchema),
    Job: definition(jobSchema),
    ShareGrant: definition(shareGrantSchema),
    ClinicianAnnotation: definition(clinicianAnnotationSchema),
    AuditEvent: definition(auditEventSchema),
    SignedResultEnvelope: definition(signedResultEnvelopeSchema),
    SyncOperation: definition(syncOperationSchema),
    SyncCursor: definition(syncCursorSchema),
    RuleRelease: definition(ruleReleaseSchema),
    ReportArtifact: definition(reportArtifactSchema),
    PlatformApiMeResponse: definition(platformApiMeResponseSchema),
    PlatformApiConsentResponse: definition(platformApiConsentResponseSchema),
    PlatformApiScanSessionResponse: definition(
      platformApiScanSessionResponseSchema,
    ),
    PlatformApiCaptureAssetResponse: definition(
      platformApiCaptureAssetResponseSchema,
    ),
    PlatformApiCaptureSetResponse: definition(
      platformApiCaptureSetResponseSchema,
    ),
    PlatformApiAnalysisRunResponse: definition(
      platformApiAnalysisRunResponseSchema,
    ),
    PlatformApiMatchProposalResponse: definition(
      platformApiMatchProposalResponseSchema,
    ),
    PlatformApiMatchDecisionResponse: definition(
      platformApiMatchDecisionResponseSchema,
    ),
    PlatformApiJobCreate: definition(platformApiJobCreateSchema),
    PlatformApiJobResponse: definition(platformApiJobResponseSchema),
    PlatformApiReportResponse: definition(platformApiReportResponseSchema),
    PlatformApiGeneratedArtifactResponse: definition(
      platformApiGeneratedArtifactResponseSchema,
    ),
    PlatformApiDataExportArtifactResponse: definition(
      platformApiDataExportArtifactResponseSchema,
    ),
    PlatformApiDeletionRequestResponse: definition(
      platformApiDeletionRequestResponseSchema,
    ),
    PlatformApiSyncOperationInput: definition(
      platformApiSyncOperationInputSchema,
    ),
    PlatformApiSyncPushResponse: definition(platformApiSyncPushResponseSchema),
    PlatformApiSyncPullResponse: definition(platformApiSyncPullResponseSchema),
    PlatformApiShareLinkResponse: definition(
      platformApiShareLinkResponseSchema,
    ),
    PlatformApiAccessGrantResponse: definition(
      platformApiAccessGrantResponseSchema,
    ),
    PlatformApiClinicianIdentityRoleResponse: definition(
      platformApiClinicianIdentityRoleResponseSchema,
    ),
    PlatformApiClinicianVerificationResponse: definition(
      platformApiClinicianVerificationResponseSchema,
    ),
    PlatformApiClinicianVerificationQueue: definition(
      platformApiClinicianVerificationQueueSchema,
    ),
    PlatformApiReviewAnnotationResponse: definition(
      platformApiReviewAnnotationResponseSchema,
    ),
    PlatformApiClinicianReviewResponse: definition(
      platformApiClinicianReviewResponseSchema,
    ),
    PlatformApiAnalyticsEventInput: definition(
      platformApiAnalyticsEventInputSchema,
    ),
  },
};

const scriptDirectory = dirname(fileURLToPath(import.meta.url));

function writeDocument(
  filename: string,
  document: Record<string, unknown>,
): void {
  const outputPath = resolve(scriptDirectory, "../generated", filename);
  mkdirSync(dirname(outputPath), { recursive: true });
  writeFileSync(outputPath, `${JSON.stringify(document, null, 2)}\n`, "utf8");
  console.log(`Generated ${outputPath}`);
}

writeDocument("stoma3d-contracts.schema.json", v1Document);
writeDocument("stoma3d-platform-contracts.schema.json", platformDocument);
