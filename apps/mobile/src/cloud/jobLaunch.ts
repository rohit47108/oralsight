import type { PersistedAppState } from "../types";
import { useOralSightStore } from "../store/useOralSightStore";

import { PlatformClient } from "./client";
import type { AnalysisRun, JobResponse } from "./contracts";
import { createDataExportPayload } from "./exportCrypto";
import { requireActiveProductConsent } from "./consent";
import {
  readCloudResourceMappings,
  type CloudResourceMapping,
} from "./productSync";
import { localComparisonId } from "./syncModel";

export type UserJobType =
  "reconstruction" | "report" | "summary_video" | "data_export";

export interface PreparedJobRequest {
  payload: Record<string, unknown>;
  inputRefs: string[];
}

function requireSession(
  state: PersistedAppState,
  localSessionId: string | null,
) {
  const session = state.sessions.find((value) => value.id === localSessionId);
  if (!session) throw new Error("Choose a synced scan first.");
  return session;
}

function mappingIndex(mappings: readonly CloudResourceMapping[]) {
  return new Map(
    mappings.map((mapping) => [`${mapping.kind}:${mapping.localId}`, mapping]),
  );
}

function assetPointer(mapping: CloudResourceMapping) {
  if (
    !mapping.uploaded ||
    !mapping.assetId ||
    !mapping.sha256 ||
    !mapping.byteSize ||
    !mapping.mimeType
  ) {
    throw new Error(
      "Finish syncing the selected scan before starting this job.",
    );
  }
  return {
    assetId: mapping.assetId,
    sha256: mapping.sha256,
    mediaType: mapping.mimeType,
    sizeBytes: mapping.byteSize,
  };
}

async function analysisRunsForSession(options: {
  client: PlatformClient;
  state: PersistedAppState;
  localSessionId: string;
  mappings: readonly CloudResourceMapping[];
}): Promise<AnalysisRun[]> {
  const captureIds = new Set(
    options.state.captures
      .filter((capture) => capture.sessionId === options.localSessionId)
      .map((capture) => capture.id),
  );
  const analysisJobs = options.mappings.filter(
    (mapping) =>
      mapping.kind === "analysis_job" && captureIds.has(mapping.localId),
  );
  const jobs = await Promise.allSettled(
    analysisJobs.map((mapping) => options.client.job(mapping.remoteId)),
  );
  const runIds = jobs.flatMap((result) =>
    result.status === "fulfilled" &&
    result.value.status === "succeeded" &&
    result.value.outcome === "complete"
      ? result.value.outputRefs
      : [],
  );
  const runs = await Promise.allSettled(
    [...new Set(runIds)].map((id) => options.client.analysisRun(id)),
  );
  return runs.flatMap((result) =>
    result.status === "fulfilled" ? [result.value] : [],
  );
}

function qualityScore(capture: PersistedAppState["captures"][number]): number {
  return Math.max(
    0,
    Math.min(
      1,
      capture.quality.blurScore,
      capture.quality.exposureScore,
      1 - capture.quality.glareScore,
      1 - capture.quality.obstructionScore,
    ),
  );
}

const appearanceLabels = new Set([
  "red-patch",
  "white-patch",
  "ulcer-like",
  "mixed",
  "pigmented",
  "none-detected",
  "unsupported",
]);

export async function prepareCloudJob(
  type: UserJobType,
  localSessionId: string | null,
  existingJobs: readonly JobResponse[],
  client = new PlatformClient(),
): Promise<PreparedJobRequest> {
  if (type === "data_export") {
    const request = await createDataExportPayload();
    return { payload: request.payload, inputRefs: [] };
  }

  const state = useOralSightStore.getState() as PersistedAppState;
  const session = requireSession(state, localSessionId);
  const mappings = await readCloudResourceMappings();
  const indexed = mappingIndex(mappings);
  const remoteSession = indexed.get(`scan_session:${session.id}`);
  if (!remoteSession) {
    throw new Error("Sync this scan before starting cloud processing.");
  }

  if (type === "reconstruction") {
    const byRegion = new Map<string, PersistedAppState["captures"]>();
    for (const capture of state.captures.filter(
      (value) => value.sessionId === session.id,
    )) {
      byRegion.set(capture.region, [
        ...(byRegion.get(capture.region) ?? []),
        capture,
      ]);
    }
    const candidate = [...byRegion.entries()].find(([, captures]) => {
      const angles = new Set(captures.map((capture) => capture.angle));
      return (
        ["straight", "left_oblique", "right_oblique"].every((angle) =>
          angles.has(angle as (typeof captures)[number]["angle"]),
        ) &&
        captures.every(
          (capture) =>
            indexed.get(`capture_view:${capture.id}`)?.uploaded === true,
        )
      );
    });
    if (!candidate) {
      throw new Error(
        "An observation surface needs synced straight, left, and right views of one region.",
      );
    }
    const [region, captures] = candidate;
    const localSetId = `capture-set:${session.id}:${region}`;
    const remoteSet = indexed.get(`capture_set:${localSetId}`);
    if (!remoteSet)
      throw new Error("The detailed capture set is not synced yet.");
    const angleLabel: Record<string, string> = {
      primary: "center",
      straight: "center",
      left_oblique: "left",
      right_oblique: "right",
      superior: "up",
      inferior: "down",
    };
    const runs = await analysisRunsForSession({
      client,
      state,
      localSessionId: session.id,
      mappings,
    });
    const observationsByCaptureId = new Map(
      runs
        .flatMap((run) => run.observations)
        .map((observation) => [observation.captureViewId, observation]),
    );
    const pins = state.pins.flatMap((pin) => {
      if (
        !pin.userConfirmed ||
        pin.region !== region ||
        !indexed.has(`lesion:${pin.id}`)
      ) {
        return [];
      }
      const localCapture = pin.captureIds
        .map((captureId) =>
          state.captures.find((item) => item.id === captureId),
        )
        .filter((item) => item !== undefined)
        .filter(
          (item) => item.sessionId === session.id && item.region === pin.region,
        )
        .sort((left, right) =>
          right.capturedAt.localeCompare(left.capturedAt),
        )[0];
      if (!localCapture) return [];
      const captureMapping = indexed.get(`capture_view:${localCapture.id}`);
      const observation = captureMapping
        ? observationsByCaptureId.get(captureMapping.remoteId)
        : undefined;
      if (
        !observation?.namedMesh ||
        !observation.uvCoordinates ||
        !observation.assetVersion
      ) {
        return [];
      }
      const calibratedArea =
        observation.calibration?.status === "valid" &&
        observation.calibration.estimatedAreaMm2 !== null &&
        observation.calibration.estimatedAreaMm2 <= 100_000
          ? observation.calibration.estimatedAreaMm2
          : null;
      return [
        {
          observationId: observation.observationId,
          region: observation.region,
          meshName: observation.namedMesh,
          uvCoordinates: observation.uvCoordinates,
          assetVersion: observation.assetVersion,
          observedAt: localCapture.capturedAt,
          status: pin.status === "monitoring" ? "tracking" : pin.status,
          userConfirmed: true,
          estimatedAreaMm2: calibratedArea,
          measurementLabel:
            calibratedArea === null ? "approximate" : "calibrated estimate",
        },
      ];
    });
    return {
      inputRefs: [],
      payload: {
        kind: "reconstruction",
        captureSetId: remoteSet.remoteId,
        views: captures.map((capture) => {
          const mapping = indexed.get(`capture_view:${capture.id}`);
          if (!mapping) throw new Error("A detailed view is not synced yet.");
          return {
            captureId: mapping.remoteId,
            image: assetPointer(mapping),
            region: capture.region,
            angleLabel: angleLabel[capture.angle],
          };
        }),
        pins,
        requestedFormat: "glb",
        approximationLabel: "oral observation surface",
      },
    };
  }

  const runs = await analysisRunsForSession({
    client,
    state,
    localSessionId: session.id,
    mappings,
  });
  const observations = runs.flatMap((run) => run.observations);
  if (observations.length === 0) {
    throw new Error(
      "No completed cloud observations are ready yet. Refresh jobs after analysis finishes.",
    );
  }

  if (type === "report") {
    const consent = await requireActiveProductConsent(client);
    const profile =
      session.intakeProfile === undefined
        ? state.profile
        : session.intakeProfile;
    const comparisonIds = state.comparisons.flatMap((comparison) => {
      const current = state.captures.find(
        (capture) => capture.id === comparison.currentCaptureId,
      );
      const mapping = indexed.get(
        `match_decision:${localComparisonId(comparison)}`,
      );
      return comparison.userConfirmedMatch &&
        current?.sessionId === session.id &&
        mapping
        ? [mapping.remoteId]
        : [];
    });
    return {
      inputRefs: [],
      payload: {
        kind: "report",
        scanSessionId: remoteSession.remoteId,
        consentRecordId: consent.consentRecordId,
        observationIds: observations.map((value) => value.observationId),
        comparisonIds,
        patientProfile: profile
          ? { ageRange: profile.ageRange, assisted: profile.assisted }
          : null,
        intakeSummary: profile
          ? {
              firstNoticed: profile.firstNoticed,
              durationDays: profile.durationDays ?? null,
              symptoms: profile.symptoms,
              bleedingFrequency: profile.bleedingFrequency ?? null,
              bleedingDuration: profile.bleedingDuration ?? null,
              change: profile.change,
              tobaccoExposure: profile.tobaccoExposure,
              alcoholExposure: profile.alcoholExposure,
              previousConditions: profile.previousConditions,
              professionallyExamined: profile.professionallyExamined,
            }
          : null,
        appointmentQuestions: [
          "What does this visible area look like during an in-person examination?",
          "Would a professional photograph or another form of evaluation be useful?",
          "Which visible changes, if any, should prompt an earlier follow-up?",
          "When, if at all, should this area be checked again?",
        ],
        locale: "en-US",
        includeExperimentalResearchOutput: true,
        disclaimer: "This result is not a diagnosis.",
      },
    };
  }

  const currentJobs =
    existingJobs.length > 0 ? existingJobs : (await client.listJobs()).items;
  const reportJob = currentJobs.find(
    (job) =>
      job.type === "report" &&
      job.status === "succeeded" &&
      job.outcome === "complete" &&
      job.inputRefs.includes(remoteSession.remoteId) &&
      job.outputRefs.length > 0,
  );
  const reportId = reportJob?.outputRefs[0];
  if (!reportId) {
    throw new Error(
      "Create and finish a cloud report before making a summary video.",
    );
  }
  const captureByRemoteId = new Map(
    mappings
      .filter((mapping) => mapping.kind === "capture_view")
      .map((mapping) => [mapping.remoteId, mapping]),
  );
  const selected = observations
    .flatMap((observation) => {
      const mapping = captureByRemoteId.get(observation.captureViewId);
      const capture = mapping
        ? state.captures.find((value) => value.id === mapping.localId)
        : undefined;
      if (!mapping || !capture || capture.sessionId !== session.id) return [];
      const topLabel = observation.appearanceOutput?.enabled
        ? observation.appearanceOutput.topLabel
        : null;
      const calibrated = observation.calibration?.status === "valid";
      const comparison = state.comparisons
        .filter(
          (value) =>
            value.currentCaptureId === capture.id &&
            value.userConfirmedMatch === true,
        )
        .sort(
          (left, right) => Number(right.comparable) - Number(left.comparable),
        )[0];
      const baseline = comparison
        ? state.captures.find(
            (value) => value.id === comparison.baselineCaptureId,
          )
        : undefined;
      const baselineMapping = baseline
        ? indexed.get(`capture_view:${baseline.id}`)
        : undefined;
      const baselineAnalysis = baseline
        ? state.analyses[baseline.id]
        : undefined;
      const includeBaseline = Boolean(
        comparison &&
        baseline &&
        baselineMapping?.uploaded &&
        baselineMapping.assetId &&
        baselineMapping.sha256 &&
        baselineMapping.byteSize &&
        baselineMapping.mimeType,
      );
      return [
        {
          observationId: observation.observationId,
          region: observation.region,
          currentCaptureId: observation.captureViewId,
          currentObservedAt: capture.capturedAt,
          currentImage: assetPointer(mapping),
          currentCandidateMask: {
            polygon: observation.candidateMask.polygon,
            boundingBox: observation.candidateMask.boundingBox,
            normalizedArea: observation.candidateMask.normalizedArea,
          },
          ...(includeBaseline && comparison && baseline && baselineMapping
            ? {
                baselineCaptureId: baselineMapping.remoteId,
                baselineObservedAt: baseline.capturedAt,
                baselineImage: assetPointer(baselineMapping),
                baselineCandidateMask: baselineAnalysis?.candidateMask ?? null,
                userConfirmedMatch: true,
                comparable: comparison.comparable,
                normalizedChange: comparison.comparable
                  ? comparison.normalizedChange
                  : null,
                registrationConfidence: comparison.registrationConfidence,
              }
            : {
                userConfirmedMatch: false,
                comparable: false,
              }),
          appearanceLabel:
            topLabel && appearanceLabels.has(topLabel) ? topLabel : null,
          qualityScore: qualityScore(capture),
          estimatedAreaMm2: calibrated
            ? (observation.calibration?.estimatedAreaMm2 ?? null)
            : null,
          measurementLabel: calibrated ? "calibrated estimate" : "approximate",
        },
      ];
    })
    .slice(0, 3);
  if (selected.length === 0) {
    throw new Error(
      "No verified observation images are ready for the summary video.",
    );
  }
  return {
    inputRefs: [],
    payload: {
      kind: "summary_video",
      scanSessionId: remoteSession.remoteId,
      reportId,
      templateVersion: "oralsight-summary-v1",
      selectedObservations: selected,
      guidance: {
        code: "neutral_seek_care_information",
        source: "neutral",
        ruleVersion: null,
      },
      durationSeconds: 30,
      captionsRequired: true,
      includeAudio: false,
      disclaimer: "This result is not a diagnosis.",
    },
  };
}
