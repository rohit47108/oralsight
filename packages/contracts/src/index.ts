import { z } from "zod";

export const CONTRACT_VERSION = "1.1.0" as const;
export const DISCLAIMER = "This result is not a diagnosis." as const;

export const MOUTH_REGIONS = [
  "dorsal_tongue",
  "ventral_tongue",
  "left_buccal_mucosa",
  "right_buccal_mucosa",
  "upper_lip",
  "lower_lip",
  "upper_dental_arch",
  "lower_dental_arch",
] as const;

export const mouthRegionSchema = z.enum(MOUTH_REGIONS);
export type MouthRegion = z.infer<typeof mouthRegionSchema>;

export const MOUTH_REGION_DETAILS: ReadonlyArray<{
  id: MouthRegion;
  label: string;
  shortLabel: string;
  meshId: string;
  captureInstruction: string;
}> = [
  {
    id: "dorsal_tongue",
    label: "Top of tongue",
    shortLabel: "Tongue top",
    meshId: "tongue_dorsal",
    captureInstruction:
      "Open wide, extend the tongue, and center its upper surface.",
  },
  {
    id: "ventral_tongue",
    label: "Underside of tongue",
    shortLabel: "Tongue underside",
    meshId: "tongue_ventral",
    captureInstruction:
      "Lift the tongue toward the roof of the mouth and photograph underneath.",
  },
  {
    id: "left_buccal_mucosa",
    label: "Left inner cheek",
    shortLabel: "Left cheek",
    meshId: "buccal_left",
    captureInstruction:
      "Gently pull the left cheek outward and center the inner cheek tissue.",
  },
  {
    id: "right_buccal_mucosa",
    label: "Right inner cheek",
    shortLabel: "Right cheek",
    meshId: "buccal_right",
    captureInstruction:
      "Gently pull the right cheek outward and center the inner cheek tissue.",
  },
  {
    id: "upper_lip",
    label: "Inside upper lip",
    shortLabel: "Upper lip",
    meshId: "lip_upper",
    captureInstruction: "Lift the upper lip and center the inner lip tissue.",
  },
  {
    id: "lower_lip",
    label: "Inside lower lip",
    shortLabel: "Lower lip",
    meshId: "lip_lower",
    captureInstruction:
      "Pull the lower lip down and center the inner lip tissue.",
  },
  {
    id: "upper_dental_arch",
    label: "Upper dental arch and gums",
    shortLabel: "Upper arch",
    meshId: "arch_upper",
    captureInstruction:
      "Tilt the camera upward to include the upper teeth and surrounding gums.",
  },
  {
    id: "lower_dental_arch",
    label: "Lower dental arch and gums",
    shortLabel: "Lower arch",
    meshId: "arch_lower",
    captureInstruction:
      "Tilt the camera downward to include the lower teeth and surrounding gums.",
  },
];

export const inputOriginSchema = z.enum(["live_capture", "bundled_demo"]);
export type InputOrigin = z.infer<typeof inputOriginSchema>;

export const analysisOriginSchema = z.enum([
  "live_model",
  "cached_model_result",
  "manual_fixture",
  "unavailable",
]);
export type AnalysisOrigin = z.infer<typeof analysisOriginSchema>;

export const analysisStatusSchema = z.enum([
  "complete",
  "abstained",
  "unsupported",
  "failed",
]);
export type AnalysisStatus = z.infer<typeof analysisStatusSchema>;

export const modelHeadSchema = z.enum([
  "segmentation",
  "anatomy",
  "appearance",
  "disease_research",
  "lesion_reidentification",
]);
export type ModelHead = z.infer<typeof modelHeadSchema>;

export const appearanceClassSchema = z.enum([
  "red-patch",
  "white-patch",
  "ulcer-like",
  "mixed",
  "pigmented",
  "none-detected",
  "unsupported",
]);
export type AppearanceClass = z.infer<typeof appearanceClassSchema>;

export const diseaseResearchClassSchema = z.enum([
  "normal",
  "variation",
  "opmd",
  "oral_cancer",
]);
export type DiseaseResearchClass = z.infer<typeof diseaseResearchClassSchema>;

export const classScoreSchema = z
  .object({
    label: z.string().min(1),
    probability: z.number().min(0).max(1),
  })
  .strict();

export const modelOutputSchema = z
  .object({
    enabled: z.boolean(),
    gatePassed: z.boolean(),
    topLabel: z.string().min(1).nullable(),
    confidence: z.number().min(0).max(1).nullable(),
    scores: z.array(classScoreSchema),
    limitation: z.string().min(1),
  })
  .strict()
  .superRefine((value, context) => {
    if (value.enabled && !value.gatePassed) {
      context.addIssue({
        code: "custom",
        path: ["enabled"],
        message: "A model output cannot be enabled before its gate passes.",
      });
    }
    if (
      !value.enabled &&
      (value.topLabel !== null ||
        value.confidence !== null ||
        value.scores.length > 0)
    ) {
      context.addIssue({
        code: "custom",
        path: ["topLabel"],
        message: "A disabled model output cannot expose predictions.",
      });
    }
  });
export type ModelOutput = z.infer<typeof modelOutputSchema>;

export const qualityResultSchema = z
  .object({
    accepted: z.boolean(),
    blurScore: z
      .number()
      .min(0)
      .max(1)
      .describe("Pass score; higher is better."),
    exposureScore: z
      .number()
      .min(0)
      .max(1)
      .describe("Pass score; higher is better."),
    glareScore: z
      .number()
      .min(0)
      .max(1)
      .describe("Glare severity; lower is better."),
    obstructionScore: z
      .number()
      .min(0)
      .max(1)
      .describe("Obstruction severity; lower is better."),
    faceDetected: z.boolean(),
    reasons: z.array(z.string()),
  })
  .strict();
export type QualityResult = z.infer<typeof qualityResultSchema>;

export const anatomyPredictionSchema = z
  .object({
    region: mouthRegionSchema.nullable(),
    confidence: z.number().min(0).max(1),
    supported: z.boolean(),
    selectedRegionMatches: z.boolean(),
  })
  .strict();

export const candidateMaskSchema = z
  .object({
    polygon: z
      .array(z.tuple([z.number().min(0).max(1), z.number().min(0).max(1)]))
      .min(3),
    boundingBox: z.tuple([
      z.number().min(0).max(1),
      z.number().min(0).max(1),
      z.number().min(0).max(1),
      z.number().min(0).max(1),
    ]),
    normalizedArea: z.number().min(0).max(1),
  })
  .strict()
  .superRefine((value, context) => {
    const [x, y, width, height] = value.boundingBox;
    if (
      width <= 0 ||
      height <= 0 ||
      x + width > 1 + 1e-6 ||
      y + height > 1 + 1e-6
    ) {
      context.addIssue({
        code: "custom",
        path: ["boundingBox"],
        message:
          "Candidate bounding box must have positive size and stay within normalized image bounds.",
      });
    }
  });
export type CandidateMask = z.infer<typeof candidateMaskSchema>;

export const visualDescriptorsSchema = z
  .object({
    normalizedArea: z.number().min(0).max(1),
    perimeter: z.number().min(0),
    borderIrregularity: z.number().min(0),
    meanRedness: z.number().min(0).max(1),
    meanBrightness: z.number().min(0).max(1),
    textureContrast: z.number().min(0).max(1),
    measurementLabel: z.literal("approximate"),
  })
  .strict();
export type VisualDescriptors = z.infer<typeof visualDescriptorsSchema>;

export const uncertaintySchema = z
  .object({
    overallConfidence: z.number().min(0).max(1),
    imageQualityConfidence: z.number().min(0).max(1),
    datasetSimilarity: z.number().min(0).max(1).nullable(),
    modelAgreement: z.number().min(0).max(1).nullable(),
    limitations: z.array(z.string()),
  })
  .strict();

const analyzeMetadataCommon = {
  contractVersion: z.literal(CONTRACT_VERSION),
  captureId: z.string().min(1).max(128),
  selectedRegion: mouthRegionSchema,
  requestedHeads: z.array(modelHeadSchema).default(["segmentation", "anatomy"]),
};

export const analyzeMetadataSchema = z.discriminatedUnion("inputOrigin", [
  z
    .object({
      ...analyzeMetadataCommon,
      inputOrigin: z.literal("live_capture"),
    })
    .strict(),
  z
    .object({
      ...analyzeMetadataCommon,
      inputOrigin: z.literal("bundled_demo"),
      fixtureSha256: z.string().regex(/^[a-f0-9]{64}$/),
    })
    .strict(),
]);
export type AnalyzeMetadata = z.infer<typeof analyzeMetadataSchema>;

export const analysisResultSchema = z
  .object({
    contractVersion: z.literal(CONTRACT_VERSION),
    captureId: z.string().min(1),
    region: mouthRegionSchema,
    quality: qualityResultSchema,
    anatomyPrediction: anatomyPredictionSchema,
    candidateMask: candidateMaskSchema.nullable(),
    descriptors: visualDescriptorsSchema.nullable(),
    appearanceOutput: modelOutputSchema.nullable(),
    diseaseResearchOutput: modelOutputSchema.nullable(),
    uncertainty: uncertaintySchema,
    abstentionReasons: z.array(z.string()),
    modelVersions: z.record(z.string(), z.string()),
    inputOrigin: inputOriginSchema,
    analysisOrigin: analysisOriginSchema,
    status: analysisStatusSchema,
    disclaimer: z.literal(DISCLAIMER),
  })
  .strict()
  .superRefine((value, context) => {
    if ((value.candidateMask === null) !== (value.descriptors === null)) {
      context.addIssue({
        code: "custom",
        path: ["descriptors"],
        message: "Candidate masks and descriptors must be present together.",
      });
    }
    if (
      value.candidateMask &&
      value.descriptors &&
      Math.abs(
        value.candidateMask.normalizedArea - value.descriptors.normalizedArea,
      ) > 1e-6
    ) {
      context.addIssue({
        code: "custom",
        path: ["descriptors", "normalizedArea"],
        message: "Candidate mask and descriptor area must match.",
      });
    }
    if (value.quality.faceDetected && value.quality.accepted) {
      context.addIssue({
        code: "custom",
        path: ["quality", "accepted"],
        message: "A face-containing capture cannot be quality accepted.",
      });
    }
    if (
      value.status === "complete" &&
      (!value.quality.accepted ||
        !value.anatomyPrediction.supported ||
        !value.anatomyPrediction.selectedRegionMatches)
    ) {
      context.addIssue({
        code: "custom",
        path: ["status"],
        message:
          "Complete analysis requires accepted quality and matching supported anatomy.",
      });
    }
    if (
      value.status !== "complete" &&
      (value.candidateMask !== null || value.descriptors !== null)
    ) {
      context.addIssue({
        code: "custom",
        path: ["candidateMask"],
        message: "Non-complete analysis cannot expose a candidate result.",
      });
    }
    if (
      (value.analysisOrigin === "cached_model_result" ||
        value.analysisOrigin === "manual_fixture") &&
      value.inputOrigin !== "bundled_demo"
    ) {
      context.addIssue({
        code: "custom",
        path: ["analysisOrigin"],
        message: "Fixture or cached output is valid only for bundled input.",
      });
    }
    const validateLabels = (
      output: ModelOutput | null,
      allowed: ReadonlySet<string>,
      path: "appearanceOutput" | "diseaseResearchOutput",
    ) => {
      if (!output) return;
      const labels = [
        ...(output.topLabel ? [output.topLabel] : []),
        ...output.scores.map((score) => score.label),
      ];
      if (labels.some((label) => !allowed.has(label))) {
        context.addIssue({
          code: "custom",
          path: [path],
          message: `${path} contains a label outside its fixed research taxonomy.`,
        });
      }
    };
    validateLabels(
      value.appearanceOutput,
      new Set(appearanceClassSchema.options),
      "appearanceOutput",
    );
    validateLabels(
      value.diseaseResearchOutput,
      new Set(diseaseResearchClassSchema.options),
      "diseaseResearchOutput",
    );
  });
export type AnalysisResult = z.infer<typeof analysisResultSchema>;

export const priorAnalysisMetadataSchema = z
  .object({
    captureId: z.string().min(1).max(128),
    region: mouthRegionSchema,
    status: analysisStatusSchema,
    analysisOrigin: analysisOriginSchema,
    qualityAccepted: z.boolean(),
    candidateNormalizedArea: z.number().min(0).max(1).nullable(),
    modelVersions: z.record(z.string(), z.string()),
  })
  .strict();
export type PriorAnalysisMetadata = z.infer<typeof priorAnalysisMetadataSchema>;

export const compareMetadataSchema = z
  .object({
    contractVersion: z.literal(CONTRACT_VERSION),
    baselineCaptureId: z.string().min(1).max(128),
    currentCaptureId: z.string().min(1).max(128),
    region: mouthRegionSchema,
    userConfirmedMatch: z.boolean(),
    inputOrigin: inputOriginSchema,
    baselineAnalysis: priorAnalysisMetadataSchema,
    currentAnalysis: priorAnalysisMetadataSchema,
  })
  .strict()
  .superRefine((value, context) => {
    const checks: ReadonlyArray<{
      matches: boolean;
      path: (string | number)[];
      message: string;
    }> = [
      {
        matches: value.baselineCaptureId !== value.currentCaptureId,
        path: ["currentCaptureId"],
        message: "A comparison requires two distinct capture IDs.",
      },
      {
        matches: value.baselineAnalysis.captureId === value.baselineCaptureId,
        path: ["baselineAnalysis", "captureId"],
        message: "Baseline analysis must belong to the baseline capture.",
      },
      {
        matches: value.currentAnalysis.captureId === value.currentCaptureId,
        path: ["currentAnalysis", "captureId"],
        message: "Current analysis must belong to the current capture.",
      },
      {
        matches: value.baselineAnalysis.region === value.region,
        path: ["baselineAnalysis", "region"],
        message: "Baseline analysis must use the requested region.",
      },
      {
        matches: value.currentAnalysis.region === value.region,
        path: ["currentAnalysis", "region"],
        message: "Current analysis must use the requested region.",
      },
    ];
    for (const check of checks) {
      if (!check.matches) {
        context.addIssue({
          code: "custom",
          path: check.path,
          message: check.message,
        });
      }
    }
  });
export type CompareMetadata = z.infer<typeof compareMetadataSchema>;

export const comparisonResultSchema = z
  .object({
    contractVersion: z.literal(CONTRACT_VERSION),
    baselineCaptureId: z.string().min(1),
    currentCaptureId: z.string().min(1),
    region: mouthRegionSchema,
    candidateMatchScore: z.number().min(0).max(1).nullable(),
    userConfirmedMatch: z.boolean(),
    registrationConfidence: z.number().min(0).max(1),
    inlierRatio: z.number().min(0).max(1),
    reprojectionErrorRatio: z.number().min(0),
    normalizedChange: z.number().min(-1).nullable(),
    comparable: z.boolean(),
    suppressionReasons: z.array(z.string()),
    modelVersions: z.record(z.string(), z.string()),
    inputOrigin: inputOriginSchema,
    analysisOrigin: analysisOriginSchema,
    disclaimer: z.literal(DISCLAIMER),
  })
  .strict()
  .superRefine((value, context) => {
    if (
      value.comparable &&
      (!value.userConfirmedMatch ||
        value.normalizedChange === null ||
        value.inlierRatio < 0.6 ||
        value.reprojectionErrorRatio > 0.03 ||
        value.suppressionReasons.length > 0)
    ) {
      context.addIssue({
        code: "custom",
        path: ["comparable"],
        message:
          "Comparable change requires confirmation and every registration gate.",
      });
    }
    if (!value.comparable && value.normalizedChange !== null) {
      context.addIssue({
        code: "custom",
        path: ["normalizedChange"],
        message: "Suppressed comparison cannot expose normalized change.",
      });
    }
    if (
      (value.analysisOrigin === "cached_model_result" ||
        value.analysisOrigin === "manual_fixture") &&
      value.inputOrigin !== "bundled_demo"
    ) {
      context.addIssue({
        code: "custom",
        path: ["analysisOrigin"],
        message: "Fixture or cached output is valid only for bundled input.",
      });
    }
  });
export type ComparisonResult = z.infer<typeof comparisonResultSchema>;

export const releaseGateSchema = z
  .object({
    head: modelHeadSchema,
    passed: z.boolean(),
    evaluatedAt: z.string().datetime().nullable(),
    metrics: z.record(z.string(), z.number()),
    unmetRequirements: z.array(z.string()),
    reviewerApproved: z.boolean(),
  })
  .strict();

export const modelCardSchema = z
  .object({
    contractVersion: z.literal(CONTRACT_VERSION),
    serviceVersion: z.string().min(1),
    intendedUse: z.string().min(1),
    forbiddenClaims: z.array(z.string()),
    modelVersions: z.record(z.string(), z.string()),
    artifactHashes: z.record(
      z.string(),
      z
        .string()
        .regex(/^[a-f0-9]{64}$/)
        .nullable(),
    ),
    enabledHeads: z.array(modelHeadSchema),
    releaseGates: z.array(releaseGateSchema),
    limitations: z.array(z.string()),
    disclaimer: z.literal(DISCLAIMER),
  })
  .strict()
  .superRefine((value, context) => {
    const gates = new Map(value.releaseGates.map((gate) => [gate.head, gate]));
    const artifactName: Record<ModelHead, string> = {
      segmentation: "segmentation_weights",
      anatomy: "anatomy_weights",
      appearance: "appearance_weights",
      disease_research: "disease_research_weights",
      lesion_reidentification: "lesion_reidentification_weights",
    };
    for (const head of value.enabledHeads) {
      const gate = gates.get(head);
      if (
        !gate?.passed ||
        !gate.evaluatedAt ||
        Object.keys(gate.metrics).length === 0 ||
        gate.unmetRequirements.length > 0 ||
        !gate.reviewerApproved ||
        !value.artifactHashes[artifactName[head]]
      ) {
        context.addIssue({
          code: "custom",
          path: ["enabledHeads"],
          message:
            "Enabled heads require a dated passed gate, metrics, review approval, and a pinned weight hash.",
        });
      }
    }
  });
export type ModelCard = z.infer<typeof modelCardSchema>;

export const guidanceLevelSchema = z.enum([
  "guidance_unavailable",
  "image_unusable",
  "no_elevated_visual_signal",
  "repeat_scan",
  "professional_review",
  "prompt_professional_review",
]);
export type GuidanceLevel = z.infer<typeof guidanceLevelSchema>;

export const apiErrorSchema = z
  .object({
    error: z
      .object({
        code: z.string().min(1),
        message: z.string().min(1),
        requestId: z.string().min(1),
      })
      .strict(),
  })
  .strict();

export function isCompleteRegionSet(regions: Iterable<MouthRegion>): boolean {
  const completed = new Set(regions);
  return MOUTH_REGIONS.every((region) => completed.has(region));
}
