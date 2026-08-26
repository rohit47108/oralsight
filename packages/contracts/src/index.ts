import { z } from "zod";

import { platformApiReviewAnnotationResponseSchema } from "./platform-api";

export * from "./platform-api";

export const CONTRACT_VERSION = "1.1.0" as const;
export const PLATFORM_CONTRACT_VERSION = "2.0.0" as const;
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
  "quality_control",
  "oral_tissue_segmentation",
  "out_of_distribution",
  "secondary_segmentation",
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

export const analysisCalibrationRequestSchema = z
  .object({
    cardVersion: z.literal("oralsight-calibration-v1"),
    markerId: z.literal(17),
    markerSideMm: z.literal(20),
    planeConfirmed: z.boolean(),
  })
  .strict();
export type AnalysisCalibrationRequest = z.infer<
  typeof analysisCalibrationRequestSchema
>;

const analyzeMetadataCommon = {
  contractVersion: z.literal(CONTRACT_VERSION),
  captureId: z.string().min(1).max(128),
  selectedRegion: mouthRegionSchema,
  requestedHeads: z.array(modelHeadSchema).default(["segmentation", "anatomy"]),
  calibration: analysisCalibrationRequestSchema.nullable().optional(),
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

export const comparisonCalibrationRequestSchema = z
  .object({
    cardVersion: z.literal("oralsight-calibration-v1"),
    markerId: z.literal(17),
    markerSideMm: z.literal(20),
    planeConfirmed: z.literal(true),
  })
  .strict();
export type ComparisonCalibrationRequest = z.infer<
  typeof comparisonCalibrationRequestSchema
>;

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
    baselineCalibration: comparisonCalibrationRequestSchema
      .nullable()
      .optional(),
    currentCalibration: comparisonCalibrationRequestSchema
      .nullable()
      .optional(),
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

export const descriptorChangesSchema = z
  .object({
    normalizedWidthChange: z.number().min(-1),
    normalizedHeightChange: z.number().min(-1),
    normalizedPerimeterChange: z.number().min(-1),
    borderIrregularityChange: z.number(),
    meanRednessChange: z.number().min(-1).max(1),
    meanBrightnessChange: z.number().min(-1).max(1),
    textureContrastChange: z.number().min(-1).max(1),
    ulcerationLikeContrastChange: z.number().min(-1).max(1).nullable(),
    measurementLabel: z.literal("approximate image-normalized change"),
  })
  .strict();
export type DescriptorChanges = z.infer<typeof descriptorChangesSchema>;

export const calibratedMeasurementChangesSchema = z
  .object({
    cardVersion: z.literal("oralsight-calibration-v1"),
    markerId: z.literal(17),
    markerSideMm: z.literal(20),
    baselineWidthMm: z.number().positive(),
    currentWidthMm: z.number().positive(),
    widthChangeMm: z.number(),
    baselineHeightMm: z.number().positive(),
    currentHeightMm: z.number().positive(),
    heightChangeMm: z.number(),
    baselineAreaMm2: z.number().positive(),
    currentAreaMm2: z.number().positive(),
    areaChangeMm2: z.number(),
    baselineConfidence: z.number().min(0).max(1),
    currentConfidence: z.number().min(0).max(1),
    measurementLabel: z.literal("calibrated estimate"),
  })
  .strict();
export type CalibratedMeasurementChanges = z.infer<
  typeof calibratedMeasurementChangesSchema
>;

export const imagePixelSizeSchema = z
  .object({
    widthPx: z.number().int().min(1).max(2048),
    heightPx: z.number().int().min(1).max(2048),
  })
  .strict();
export type ImagePixelSize = z.infer<typeof imagePixelSizeSchema>;

const homographyMatrixSchema = z
  .tuple([
    z.number().finite(),
    z.number().finite(),
    z.number().finite(),
    z.number().finite(),
    z.number().finite(),
    z.number().finite(),
    z.number().finite(),
    z.number().finite(),
    z.number().finite(),
  ])
  .superRefine((matrix, context) => {
    if (Math.abs(matrix[8] - 1) > 1e-6) {
      context.addIssue({
        code: "custom",
        message: "Registration alignment matrix must be normalized.",
      });
    }
    const determinant =
      matrix[0] * (matrix[4] * matrix[8] - matrix[5] * matrix[7]) -
      matrix[1] * (matrix[3] * matrix[8] - matrix[5] * matrix[6]) +
      matrix[2] * (matrix[3] * matrix[7] - matrix[4] * matrix[6]);
    if (!Number.isFinite(determinant) || Math.abs(determinant) < 1e-10) {
      context.addIssue({
        code: "custom",
        message: "Registration alignment matrix must be invertible.",
      });
    }
    for (const x of [0, 0.5, 1]) {
      for (const y of [0, 0.5, 1]) {
        const denominator = matrix[6] * x + matrix[7] * y + matrix[8];
        if (Math.abs(denominator) < 1e-6) {
          context.addIssue({
            code: "custom",
            message: "Registration alignment has an unsafe projective horizon.",
          });
          continue;
        }
        const projectedX =
          (matrix[0] * x + matrix[1] * y + matrix[2]) / denominator;
        const projectedY =
          (matrix[3] * x + matrix[4] * y + matrix[5]) / denominator;
        if (
          !Number.isFinite(projectedX) ||
          !Number.isFinite(projectedY) ||
          Math.max(Math.abs(projectedX), Math.abs(projectedY)) > 16
        ) {
          context.addIssue({
            code: "custom",
            message:
              "Registration alignment projects outside the safe render range.",
          });
        }
      }
    }
  });

export const registrationAlignmentSchema = z
  .object({
    method: z.literal("orb_ransac_homography"),
    coordinateSpace: z.literal("normalized_image_coordinates"),
    mapsFrom: z.literal("current"),
    mapsTo: z.literal("baseline"),
    matrix: homographyMatrixSchema,
    sourceImageSize: imagePixelSizeSchema,
    targetImageSize: imagePixelSizeSchema,
  })
  .strict();
export type RegistrationAlignment = z.infer<typeof registrationAlignmentSchema>;

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
    repeatedCaptureAreaError: z.number().min(0).max(0.1).nullable(),
    repeatabilityGatePassed: z.boolean(),
    registrationAlignment: registrationAlignmentSchema.nullable(),
    normalizedChange: z.number().min(-1).nullable(),
    descriptorChanges: descriptorChangesSchema.nullable().optional(),
    calibratedMeasurementChanges: calibratedMeasurementChangesSchema
      .nullable()
      .optional(),
    calibrationSuppressionReasons: z.array(z.string()).optional(),
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
      value.repeatabilityGatePassed !==
      (value.repeatedCaptureAreaError !== null)
    ) {
      context.addIssue({
        code: "custom",
        path: ["repeatabilityGatePassed"],
        message:
          "Repeatability gate status requires matching released evidence.",
      });
    }
    if (
      value.calibratedMeasurementChanges != null &&
      value.repeatabilityGatePassed === false
    ) {
      context.addIssue({
        code: "custom",
        path: ["calibratedMeasurementChanges"],
        message:
          "Calibrated physical change requires released repeatability evidence.",
      });
    }
    if (
      value.registrationAlignment != null &&
      (value.inlierRatio < 0.6 ||
        value.reprojectionErrorRatio > 0.03 ||
        value.analysisOrigin !== "live_model")
    ) {
      context.addIssue({
        code: "custom",
        path: ["registrationAlignment"],
        message:
          "Registration alignment requires a gated live-model homography.",
      });
    }
    if (
      value.comparable &&
      (!value.userConfirmedMatch ||
        !value.repeatabilityGatePassed ||
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
      !value.comparable &&
      (value.descriptorChanges != null ||
        value.calibratedMeasurementChanges != null)
    ) {
      context.addIssue({
        code: "custom",
        path: ["descriptorChanges"],
        message:
          "Suppressed comparison cannot expose descriptor or calibrated change.",
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
    comparisonRepeatedCaptureAreaError: z
      .number()
      .min(0)
      .max(0.1)
      .nullable()
      .optional(),
    comparisonRepeatabilityGatePassed: z.boolean().optional(),
    limitations: z.array(z.string()),
    disclaimer: z.literal(DISCLAIMER),
  })
  .strict()
  .superRefine((value, context) => {
    if (
      value.comparisonRepeatabilityGatePassed !== undefined &&
      value.comparisonRepeatabilityGatePassed !==
        (value.comparisonRepeatedCaptureAreaError !== null &&
          value.comparisonRepeatedCaptureAreaError !== undefined)
    ) {
      context.addIssue({
        code: "custom",
        path: ["comparisonRepeatabilityGatePassed"],
        message:
          "Comparison repeatability status requires matching released evidence.",
      });
    }
    const gates = new Map(value.releaseGates.map((gate) => [gate.head, gate]));
    const artifactName: Record<ModelHead, string> = {
      segmentation: "segmentation_weights",
      anatomy: "anatomy_weights",
      appearance: "appearance_weights",
      disease_research: "disease_research_weights",
      lesion_reidentification: "lesion_reidentification_weights",
      quality_control: "quality_control_weights",
      oral_tissue_segmentation: "oral_tissue_segmentation_weights",
      out_of_distribution: "out_of_distribution_weights",
      secondary_segmentation: "secondary_segmentation_weights",
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

/**
 * Platform contract v2 is additive. The public inference contract above remains
 * pinned to 1.1.0 so deployed v1 clients and services continue to interoperate.
 */

export const ANATOMICAL_SITES = [
  "dorsal_tongue",
  "ventral_tongue",
  "left_lateral_tongue",
  "right_lateral_tongue",
  "floor_of_mouth",
  "hard_palate",
  "soft_palate",
  "oropharynx",
  "left_buccal_mucosa",
  "right_buccal_mucosa",
  "upper_labial_mucosa",
  "lower_labial_mucosa",
  "upper_gingiva",
  "lower_gingiva",
  "upper_teeth",
  "lower_teeth",
  "other_visible_oral_tissue",
] as const;

export const anatomicalSiteSchema = z.enum(ANATOMICAL_SITES);
export type AnatomicalSite = z.infer<typeof anatomicalSiteSchema>;

export const CAPTURE_PROTOCOLS = [
  "standard_eight_region",
  "detailed_multi_angle",
  "guided_video_sweep",
] as const;
export const captureProtocolSchema = z.enum(CAPTURE_PROTOCOLS);
export type CaptureProtocol = z.infer<typeof captureProtocolSchema>;

export const CAPTURE_ANGLES = [
  "primary",
  "straight",
  "left_oblique",
  "right_oblique",
  "superior",
  "inferior",
] as const;
export const captureAngleSchema = z.enum(CAPTURE_ANGLES);
export type CaptureAngle = z.infer<typeof captureAngleSchema>;

export const MEDIA_KINDS = ["image", "video", "video_frame"] as const;
export const mediaKindSchema = z.enum(MEDIA_KINDS);
export type MediaKind = z.infer<typeof mediaKindSchema>;

const platformIdSchema = z.string().min(1).max(128);
const sha256Schema = z.string().regex(/^[a-f0-9]{64}$/);
const base64UrlSignatureSchema = z
  .string()
  .min(43)
  .max(512)
  .regex(/^[A-Za-z0-9_-]+={0,2}$/);

export const captureAssetSchema = z
  .object({
    assetId: platformIdSchema,
    mediaKind: mediaKindSchema,
    mimeType: z.string().min(3).max(128),
    byteSize: z.number().int().positive().max(2_147_483_647),
    sha256: sha256Schema,
    widthPx: z.number().int().positive().max(32_768),
    heightPx: z.number().int().positive().max(32_768),
    durationMs: z.number().int().positive().max(60_000).nullable(),
    inputOrigin: inputOriginSchema,
    encrypted: z.literal(true),
    createdAt: z.string().datetime(),
    retentionExpiresAt: z.string().datetime().nullable(),
  })
  .strict()
  .superRefine((value, context) => {
    if (value.mediaKind === "video" && value.durationMs === null) {
      context.addIssue({
        code: "custom",
        path: ["durationMs"],
        message: "Video assets require a duration.",
      });
    }
    if (value.mediaKind !== "video" && value.durationMs !== null) {
      context.addIssue({
        code: "custom",
        path: ["durationMs"],
        message: "Only video assets may expose a duration.",
      });
    }
    if (
      value.retentionExpiresAt &&
      Date.parse(value.retentionExpiresAt) <= Date.parse(value.createdAt)
    ) {
      context.addIssue({
        code: "custom",
        path: ["retentionExpiresAt"],
        message: "Asset retention expiry must be later than creation.",
      });
    }
  });
export type CaptureAsset = z.infer<typeof captureAssetSchema>;

export const captureViewSchema = z
  .object({
    captureViewId: platformIdSchema,
    captureSetId: platformIdSchema,
    region: mouthRegionSchema,
    anatomicalSite: anatomicalSiteSchema.nullable(),
    angle: captureAngleSchema,
    asset: captureAssetSchema,
    sourceVideoAssetId: platformIdSchema.nullable(),
    qualityAccepted: z.boolean(),
    qualityReasons: z.array(z.string().min(1).max(256)).max(32),
    ordinal: z.number().int().min(0).max(31),
    capturedAt: z.string().datetime(),
  })
  .strict()
  .superRefine((value, context) => {
    if (value.asset.mediaKind === "video") {
      context.addIssue({
        code: "custom",
        path: ["asset", "mediaKind"],
        message: "A capture view must reference an image or extracted frame.",
      });
    }
    if (
      (value.asset.mediaKind === "video_frame") !==
      (value.sourceVideoAssetId !== null)
    ) {
      context.addIssue({
        code: "custom",
        path: ["sourceVideoAssetId"],
        message: "Extracted frames require their source video asset ID.",
      });
    }
  });
export type CaptureView = z.infer<typeof captureViewSchema>;

export const captureSetSchema = z
  .object({
    contractVersion: z.literal(PLATFORM_CONTRACT_VERSION),
    captureSetId: platformIdSchema,
    scanSessionId: platformIdSchema,
    region: mouthRegionSchema,
    protocol: captureProtocolSchema,
    primaryViewId: platformIdSchema.nullable(),
    views: z.array(captureViewSchema).max(12),
    complete: z.boolean(),
    createdAt: z.string().datetime(),
    updatedAt: z.string().datetime(),
  })
  .strict()
  .superRefine((value, context) => {
    const viewIds = new Set<string>();
    for (const [index, view] of value.views.entries()) {
      if (view.captureSetId !== value.captureSetId) {
        context.addIssue({
          code: "custom",
          path: ["views", index, "captureSetId"],
          message: "Every view must belong to its containing capture set.",
        });
      }
      if (view.region !== value.region) {
        context.addIssue({
          code: "custom",
          path: ["views", index, "region"],
          message: "Every view must use its capture set region.",
        });
      }
      if (viewIds.has(view.captureViewId)) {
        context.addIssue({
          code: "custom",
          path: ["views", index, "captureViewId"],
          message: "Capture view IDs must be unique within a set.",
        });
      }
      viewIds.add(view.captureViewId);
    }

    const primary = value.views.find(
      (view) => view.captureViewId === value.primaryViewId,
    );
    if (value.primaryViewId !== null && !primary) {
      context.addIssue({
        code: "custom",
        path: ["primaryViewId"],
        message: "The primary view must exist in this capture set.",
      });
    }
    if (primary && !primary.qualityAccepted) {
      context.addIssue({
        code: "custom",
        path: ["primaryViewId"],
        message: "The primary view must be quality accepted.",
      });
    }

    if (value.protocol === "standard_eight_region" && value.views.length > 1) {
      context.addIssue({
        code: "custom",
        path: ["views"],
        message: "A standard region retains at most one accepted image.",
      });
    }

    if (!value.complete) return;
    if (!primary) {
      context.addIssue({
        code: "custom",
        path: ["complete"],
        message: "A complete capture set requires an accepted primary view.",
      });
      return;
    }

    if (value.protocol !== "standard_eight_region") {
      const acceptedAngles = new Set(
        value.views
          .filter((view) => view.qualityAccepted)
          .map((view) => view.angle),
      );
      for (const angle of [
        "straight",
        "left_oblique",
        "right_oblique",
      ] as const) {
        if (!acceptedAngles.has(angle)) {
          context.addIssue({
            code: "custom",
            path: ["complete"],
            message:
              "A complete detailed capture requires accepted straight, left, and right views.",
          });
          break;
        }
      }
    }
  });
export type CaptureSet = z.infer<typeof captureSetSchema>;

export const calibrationStatusSchema = z.enum([
  "not_attempted",
  "valid",
  "invalid",
]);
export type CalibrationStatus = z.infer<typeof calibrationStatusSchema>;

export const calibrationResultSchema = z
  .object({
    calibrationId: platformIdSchema,
    captureViewId: platformIdSchema,
    status: calibrationStatusSchema,
    method: z.literal("versioned_reference_card"),
    cardVersion: z.string().min(1).max(64).nullable(),
    markerId: z.string().min(1).max(64).nullable(),
    referenceWidthMm: z.number().positive().max(1_000).nullable(),
    millimetersPerPixel: z.number().positive().max(100).nullable(),
    estimatedWidthMm: z.number().nonnegative().max(1_000).nullable(),
    estimatedHeightMm: z.number().nonnegative().max(1_000).nullable(),
    estimatedAreaMm2: z.number().nonnegative().max(1_000_000).nullable(),
    confidence: z.number().min(0).max(1).nullable(),
    gateReasons: z.array(z.string().min(1).max(256)).max(32),
    calibratedAt: z.string().datetime().nullable(),
    modelVersions: z.record(z.string(), z.string().min(1)),
    measurementLabel: z.literal("calibrated estimate"),
  })
  .strict()
  .superRefine((value, context) => {
    const millimeterFields = [
      value.referenceWidthMm,
      value.millimetersPerPixel,
      value.estimatedWidthMm,
      value.estimatedHeightMm,
      value.estimatedAreaMm2,
    ];
    if (
      value.status !== "valid" &&
      millimeterFields.some((item) => item !== null)
    ) {
      context.addIssue({
        code: "custom",
        path: ["estimatedWidthMm"],
        message:
          "Millimeter values must remain null unless physical calibration is valid.",
      });
    }
    if (
      value.status === "valid" &&
      (value.cardVersion === null ||
        value.markerId === null ||
        value.referenceWidthMm === null ||
        value.millimetersPerPixel === null ||
        value.confidence === null ||
        value.calibratedAt === null ||
        value.gateReasons.length > 0)
    ) {
      context.addIssue({
        code: "custom",
        path: ["status"],
        message:
          "Valid calibration requires a versioned marker, scale, confidence, timestamp, and no failed gates.",
      });
    }
    if (value.status === "invalid" && value.gateReasons.length === 0) {
      context.addIssue({
        code: "custom",
        path: ["gateReasons"],
        message: "Invalid calibration must state why its gates failed.",
      });
    }
  });
export type CalibrationResult = z.infer<typeof calibrationResultSchema>;

export const candidateObservationSchema = z
  .object({
    observationId: platformIdSchema,
    analysisRunId: platformIdSchema,
    captureViewId: platformIdSchema,
    region: mouthRegionSchema,
    anatomicalSite: anatomicalSiteSchema.nullable(),
    candidateMask: candidateMaskSchema,
    descriptors: visualDescriptorsSchema,
    calibration: calibrationResultSchema.nullable(),
    appearanceOutput: modelOutputSchema.nullable(),
    diseaseResearchOutput: modelOutputSchema.nullable(),
    uncertainty: uncertaintySchema,
    namedMesh: z.string().min(1).max(128).nullable(),
    uvCoordinates: z
      .tuple([z.number().min(0).max(1), z.number().min(0).max(1)])
      .nullable(),
    assetVersion: z.string().min(1).max(128).nullable(),
    limitations: z.array(z.string().min(1).max(512)).max(64),
    createdAt: z.string().datetime(),
  })
  .strict()
  .superRefine((value, context) => {
    if (
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
    if (
      value.calibration?.captureViewId !== undefined &&
      value.calibration.captureViewId !== value.captureViewId
    ) {
      context.addIssue({
        code: "custom",
        path: ["calibration", "captureViewId"],
        message: "Calibration must belong to the observation capture view.",
      });
    }
    const mappingParts = [
      value.namedMesh,
      value.uvCoordinates,
      value.assetVersion,
    ];
    const mappedParts = mappingParts.filter((part) => part !== null).length;
    if (mappedParts !== 0 && mappedParts !== mappingParts.length) {
      context.addIssue({
        code: "custom",
        path: ["uvCoordinates"],
        message:
          "A 3D observation mapping requires mesh, UV coordinates, and asset version together.",
      });
    }
  });
export type CandidateObservation = z.infer<typeof candidateObservationSchema>;

export const analysisRunSchema = z
  .object({
    contractVersion: z.literal(PLATFORM_CONTRACT_VERSION),
    analysisRunId: platformIdSchema,
    captureSetId: platformIdSchema,
    requestedHeads: z.array(modelHeadSchema).min(1),
    status: analysisStatusSchema,
    observations: z.array(candidateObservationSchema),
    inputOrigin: inputOriginSchema,
    analysisOrigin: analysisOriginSchema,
    sourceAssetSha256: z.array(sha256Schema).min(1),
    modelVersions: z.record(z.string(), z.string().min(1)),
    artifactHashes: z.record(z.string(), sha256Schema),
    abstentionReasons: z.array(z.string().min(1).max(512)).max(64),
    startedAt: z.string().datetime(),
    completedAt: z.string().datetime().nullable(),
    persisted: z.boolean(),
    signedEnvelopeId: platformIdSchema.nullable(),
    disclaimer: z.literal(DISCLAIMER),
  })
  .strict()
  .superRefine((value, context) => {
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
    if (value.persisted && value.signedEnvelopeId === null) {
      context.addIssue({
        code: "custom",
        path: ["signedEnvelopeId"],
        message: "Persistent analysis requires a signed provenance envelope.",
      });
    }
    if (!value.persisted && value.signedEnvelopeId !== null) {
      context.addIssue({
        code: "custom",
        path: ["signedEnvelopeId"],
        message:
          "An ephemeral analysis cannot reference a persistent envelope.",
      });
    }
    if (value.persisted && Object.keys(value.modelVersions).length === 0) {
      context.addIssue({
        code: "custom",
        path: ["modelVersions"],
        message: "Persistent analysis requires model-version provenance.",
      });
    }
    if (
      value.persisted &&
      value.analysisOrigin === "live_model" &&
      Object.keys(value.artifactHashes).length === 0
    ) {
      context.addIssue({
        code: "custom",
        path: ["artifactHashes"],
        message: "Persistent live analysis requires pinned artifact hashes.",
      });
    }
    if (value.status === "complete" && value.completedAt === null) {
      context.addIssue({
        code: "custom",
        path: ["completedAt"],
        message: "Complete analysis requires a completion timestamp.",
      });
    }
    if (value.status !== "complete" && value.observations.length > 0) {
      context.addIssue({
        code: "custom",
        path: ["observations"],
        message: "Non-complete analysis cannot expose candidate observations.",
      });
    }
    if (
      value.observations.some(
        (item) => item.analysisRunId !== value.analysisRunId,
      )
    ) {
      context.addIssue({
        code: "custom",
        path: ["observations"],
        message:
          "Every observation must belong to its containing analysis run.",
      });
    }
  });
export type AnalysisRun = z.infer<typeof analysisRunSchema>;

export const matchProposalSchema = z
  .object({
    proposalId: platformIdSchema,
    currentObservationId: platformIdSchema,
    candidatePriorObservationId: platformIdSchema,
    candidateLesionId: platformIdSchema.nullable(),
    proposalOrigin: z.enum(["automatic_model", "user_selected"]),
    score: z.number().min(0).max(1).nullable(),
    rank: z.number().int().positive().max(100).nullable(),
    state: z.literal("proposed"),
    automaticallyConfirmed: z.literal(false),
    modelVersions: z.record(z.string(), z.string().min(1)),
    generatedAt: z.string().datetime(),
    expiresAt: z.string().datetime().nullable(),
  })
  .strict()
  .superRefine((value, context) => {
    if (value.currentObservationId === value.candidatePriorObservationId) {
      context.addIssue({
        code: "custom",
        path: ["candidatePriorObservationId"],
        message: "A match proposal requires two distinct observations.",
      });
    }
    const invalidAutomatic =
      value.proposalOrigin === "automatic_model" &&
      (value.score === null ||
        value.rank === null ||
        Object.keys(value.modelVersions).length === 0);
    const invalidUserSelected =
      value.proposalOrigin === "user_selected" &&
      (value.score !== null ||
        value.rank !== null ||
        Object.keys(value.modelVersions).length > 0);
    if (invalidAutomatic || invalidUserSelected) {
      context.addIssue({
        code: "custom",
        path: ["proposalOrigin"],
        message:
          "Automatic proposals require a score, rank, and model versions; user-selected proposals require none.",
      });
    }
  });
export type MatchProposal = z.infer<typeof matchProposalSchema>;

export const matchDecisionSchema = z
  .object({
    decisionId: platformIdSchema,
    proposalId: platformIdSchema,
    decision: z.enum(["confirmed", "rejected", "deferred"]),
    decidedBy: z.literal("patient"),
    actorId: platformIdSchema,
    rationale: z.string().min(1).max(1_000).nullable(),
    decidedAt: z.string().datetime(),
    lesionId: platformIdSchema.nullable(),
  })
  .strict();
export type MatchDecision = z.infer<typeof matchDecisionSchema>;

export const lesionRecordSchema = z
  .object({
    lesionId: platformIdSchema,
    region: mouthRegionSchema,
    anatomicalSite: anatomicalSiteSchema.nullable(),
    label: z.string().min(1).max(128).nullable(),
    status: z.enum(["tracking", "archived"]),
    confirmedObservationIds: z.array(platformIdSchema).min(1),
    matchDecisionIds: z.array(platformIdSchema),
    version: z.number().int().positive(),
    createdAt: z.string().datetime(),
    updatedAt: z.string().datetime(),
  })
  .strict()
  .superRefine((value, context) => {
    if (
      new Set(value.confirmedObservationIds).size !==
      value.confirmedObservationIds.length
    ) {
      context.addIssue({
        code: "custom",
        path: ["confirmedObservationIds"],
        message: "A lesion timeline cannot repeat an observation.",
      });
    }
    if (
      value.confirmedObservationIds.length > 1 &&
      value.matchDecisionIds.length < value.confirmedObservationIds.length - 1
    ) {
      context.addIssue({
        code: "custom",
        path: ["matchDecisionIds"],
        message:
          "Every added observation requires a user or clinician match decision.",
      });
    }
  });
export type LesionRecord = z.infer<typeof lesionRecordSchema>;

export const JOB_TYPES = [
  "analysis",
  "comparison",
  "reconstruction",
  "report",
  "summary_video",
  "data_export",
  "account_deletion",
  "delete_all",
] as const;
export const jobTypeSchema = z.enum(JOB_TYPES);
export type JobType = z.infer<typeof jobTypeSchema>;

export const JOB_STATUSES = [
  "queued",
  "running",
  "succeeded",
  "failed",
  "cancelled",
  "expired",
] as const;
export const jobStatusSchema = z.enum(JOB_STATUSES);
export type JobStatus = z.infer<typeof jobStatusSchema>;

export const jobSchema = z
  .object({
    jobId: platformIdSchema,
    ownerId: platformIdSchema,
    type: jobTypeSchema,
    status: jobStatusSchema,
    inputRefs: z.array(platformIdSchema).max(128),
    outputRefs: z.array(platformIdSchema).max(128),
    progress: z.number().min(0).max(1),
    attempt: z.number().int().nonnegative(),
    maxAttempts: z.number().int().positive().max(20),
    errorCode: z.string().min(1).max(128).nullable(),
    errorMessage: z.string().min(1).max(1_000).nullable(),
    createdAt: z.string().datetime(),
    startedAt: z.string().datetime().nullable(),
    completedAt: z.string().datetime().nullable(),
    expiresAt: z.string().datetime(),
    outcome: z
      .enum(["complete", "unavailable", "cancelled", "failed"])
      .nullable(),
    reasonCode: z.string().min(1).max(128).nullable(),
    result: z.record(z.string(), z.unknown()).nullable(),
    cancellationRequested: z.boolean(),
  })
  .strict()
  .superRefine((value, context) => {
    const terminal = new Set<JobStatus>([
      "succeeded",
      "failed",
      "cancelled",
      "expired",
    ]);
    if (terminal.has(value.status) !== (value.completedAt !== null)) {
      context.addIssue({
        code: "custom",
        path: ["completedAt"],
        message: "Exactly terminal jobs require a completion timestamp.",
      });
    }
    if (value.status === "succeeded" && value.progress !== 1) {
      context.addIssue({
        code: "custom",
        path: ["progress"],
        message: "A succeeded job must report complete progress.",
      });
    }
    if (value.status !== "failed" && (value.errorCode || value.errorMessage)) {
      context.addIssue({
        code: "custom",
        path: ["errorCode"],
        message: "Only a failed job may expose error details.",
      });
    }
  });
export type Job = z.infer<typeof jobSchema>;

export const shareScopeSchema = z.enum([
  "scan:view",
  "report:view",
  "report:download",
  "annotation:write",
  "follow_up:request",
]);
export type ShareScope = z.infer<typeof shareScopeSchema>;

const SEVEN_DAYS_MS = 7 * 24 * 60 * 60 * 1_000;

export const shareGrantSchema = z
  .object({
    shareGrantId: platformIdSchema,
    patientId: platformIdSchema,
    secretHash: sha256Schema,
    scopes: z.array(shareScopeSchema).min(1),
    resourceIds: z.array(platformIdSchema).min(1).max(256),
    allowDownloads: z.boolean(),
    maxDownloads: z.number().int().positive().max(100).nullable(),
    downloadCount: z.number().int().nonnegative().max(100),
    createdAt: z.string().datetime(),
    expiresAt: z.string().datetime(),
    revokedAt: z.string().datetime().nullable(),
  })
  .strict()
  .superRefine((value, context) => {
    const lifetime = Date.parse(value.expiresAt) - Date.parse(value.createdAt);
    if (lifetime <= 0 || lifetime > SEVEN_DAYS_MS) {
      context.addIssue({
        code: "custom",
        path: ["expiresAt"],
        message:
          "A share must expire after creation and no later than seven days.",
      });
    }
    if (!value.allowDownloads && value.maxDownloads !== null) {
      context.addIssue({
        code: "custom",
        path: ["maxDownloads"],
        message: "Download limits are valid only when downloads are allowed.",
      });
    }
    if (
      value.maxDownloads !== null &&
      value.downloadCount > value.maxDownloads
    ) {
      context.addIssue({
        code: "custom",
        path: ["downloadCount"],
        message: "Download count cannot exceed its grant limit.",
      });
    }
    if (
      value.revokedAt &&
      Date.parse(value.revokedAt) < Date.parse(value.createdAt)
    ) {
      context.addIssue({
        code: "custom",
        path: ["revokedAt"],
        message: "A share cannot be revoked before it is created.",
      });
    }
  });
export type ShareGrant = z.infer<typeof shareGrantSchema>;

// Backwards-compatible export name backed by the exact current platform wire schema.
export const clinicianAnnotationSchema =
  platformApiReviewAnnotationResponseSchema;
export type ClinicianAnnotation = z.infer<typeof clinicianAnnotationSchema>;

export const auditEventSchema = z
  .object({
    auditEventId: platformIdSchema,
    actorType: z.enum(["patient", "clinician", "admin", "service", "guest"]),
    actorId: platformIdSchema.nullable(),
    action: z.enum([
      "create",
      "view",
      "update",
      "delete",
      "share",
      "revoke",
      "export",
      "sign_in",
      "sign_out",
    ]),
    resourceType: z.enum([
      "account",
      "scan",
      "capture",
      "analysis",
      "observation",
      "report",
      "share",
      "annotation",
      "job",
    ]),
    resourceIdHash: sha256Schema,
    outcome: z.enum(["success", "denied", "failed"]),
    requestId: platformIdSchema,
    clientPlatform: z.enum(["ios", "android", "web", "service"]).nullable(),
    appVersion: z.string().min(1).max(64).nullable(),
    reasonCode: z.string().min(1).max(128).nullable(),
    occurredAt: z.string().datetime(),
  })
  .strict();
export type AuditEvent = z.infer<typeof auditEventSchema>;

export const signedResultTypeSchema = z.enum([
  "analysis",
  "comparison",
  "reconstruction",
  "report",
  "guidance",
]);
export type SignedResultType = z.infer<typeof signedResultTypeSchema>;

export const signedResultEnvelopeSchema = z
  .object({
    contractVersion: z.literal(PLATFORM_CONTRACT_VERSION),
    envelopeId: platformIdSchema,
    resultType: signedResultTypeSchema,
    subjectId: platformIdSchema,
    schemaId: z.string().url(),
    payload: z.record(z.string(), z.unknown()),
    payloadSha256: sha256Schema,
    sourceAssetSha256: z.array(sha256Schema).min(1),
    inputOrigin: inputOriginSchema,
    analysisOrigin: analysisOriginSchema,
    modelVersions: z.record(z.string(), z.string().min(1)),
    artifactHashes: z.record(z.string(), sha256Schema),
    createdAt: z.string().datetime(),
    signingKeyId: z.string().min(1).max(128),
    signatureAlgorithm: z.literal("Ed25519"),
    signature: base64UrlSignatureSchema,
  })
  .strict()
  .superRefine((value, context) => {
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
    if (Object.keys(value.modelVersions).length === 0) {
      context.addIssue({
        code: "custom",
        path: ["modelVersions"],
        message: "Persistent results require model-version provenance.",
      });
    }
  });
export type SignedResultEnvelope = z.infer<typeof signedResultEnvelopeSchema>;

const syncOperationCommon = {
  contractVersion: z.literal(PLATFORM_CONTRACT_VERSION),
  operationId: platformIdSchema,
  idempotencyKey: z.string().min(16).max(256),
  deviceId: platformIdSchema,
  entityType: z.enum([
    "scan_session",
    "capture_set",
    "capture_view",
    "analysis_run",
    "observation",
    "lesion",
    "match_decision",
    "report",
  ]),
  entityId: platformIdSchema,
  version: z.number().int().positive(),
  sequence: z.number().int().nonnegative(),
  occurredAt: z.string().datetime(),
};

export const syncOperationSchema = z.discriminatedUnion("operation", [
  z
    .object({
      ...syncOperationCommon,
      operation: z.literal("upsert"),
      encryptedPayload: z.string().min(16),
      tombstone: z.literal(false),
    })
    .strict(),
  z
    .object({
      ...syncOperationCommon,
      operation: z.literal("delete"),
      encryptedPayload: z.null(),
      tombstone: z.literal(true),
    })
    .strict(),
]);
export type SyncOperation = z.infer<typeof syncOperationSchema>;

export const syncCursorSchema = z
  .object({
    contractVersion: z.literal(PLATFORM_CONTRACT_VERSION),
    cursor: z.string().min(16).max(2_048),
    highWatermark: z.number().int().nonnegative(),
    issuedAt: z.string().datetime(),
    expiresAt: z.string().datetime(),
  })
  .strict()
  .superRefine((value, context) => {
    if (Date.parse(value.expiresAt) <= Date.parse(value.issuedAt)) {
      context.addIssue({
        code: "custom",
        path: ["expiresAt"],
        message: "A sync cursor must expire after it is issued.",
      });
    }
  });
export type SyncCursor = z.infer<typeof syncCursorSchema>;

export const clinicianApprovalSchema = z
  .object({
    clinicianId: platformIdSchema,
    reviewedAt: z.string().datetime(),
    scope: z.string().min(1).max(512),
    configurationSha256: sha256Schema,
  })
  .strict();
export type ClinicianApproval = z.infer<typeof clinicianApprovalSchema>;

export const ruleReleaseSchema = z
  .object({
    contractVersion: z.literal(PLATFORM_CONTRACT_VERSION),
    ruleReleaseId: platformIdSchema,
    version: z.string().min(1).max(64),
    status: z.enum(["draft", "enabled", "retired"]),
    urgencyEnabled: z.boolean(),
    rulesSha256: sha256Schema,
    intendedUse: z.string().min(1).max(2_000),
    limitations: z.array(z.string().min(1).max(512)).min(1),
    clinicianApproval: clinicianApprovalSchema.nullable(),
    signedAt: z.string().datetime().nullable(),
    signingKeyId: z.string().min(1).max(128).nullable(),
    signatureAlgorithm: z.literal("Ed25519").nullable(),
    signature: base64UrlSignatureSchema.nullable(),
    createdAt: z.string().datetime(),
  })
  .strict()
  .superRefine((value, context) => {
    const signed =
      value.signedAt !== null &&
      value.signingKeyId !== null &&
      value.signatureAlgorithm !== null &&
      value.signature !== null;
    const anySignaturePart =
      value.signedAt !== null ||
      value.signingKeyId !== null ||
      value.signatureAlgorithm !== null ||
      value.signature !== null;
    if (anySignaturePart && !signed) {
      context.addIssue({
        code: "custom",
        path: ["signature"],
        message: "Rule-release signature fields must be present together.",
      });
    }
    if (
      value.urgencyEnabled &&
      (value.status !== "enabled" ||
        !signed ||
        value.clinicianApproval === null)
    ) {
      context.addIssue({
        code: "custom",
        path: ["urgencyEnabled"],
        message:
          "Urgency guidance requires an enabled, signed, clinician-approved rule release.",
      });
    }
  });
export type RuleRelease = z.infer<typeof ruleReleaseSchema>;

export const reportArtifactSchema = z
  .object({
    contractVersion: z.literal(PLATFORM_CONTRACT_VERSION),
    reportArtifactId: platformIdSchema,
    patientId: platformIdSchema,
    scanSessionIds: z.array(platformIdSchema).min(1).max(64),
    format: z.enum([
      "pdf",
      "html",
      "fhir_r4_bundle",
      "summary_video",
      "transcript",
    ]),
    assetId: platformIdSchema,
    sha256: sha256Schema,
    byteSize: z.number().int().positive().max(2_147_483_647),
    locale: z.string().min(2).max(35),
    accessible: z.boolean(),
    inputOrigins: z.array(inputOriginSchema).min(1),
    analysisOrigins: z.array(analysisOriginSchema).min(1),
    modelVersions: z.record(z.string(), z.string().min(1)),
    signedEnvelopeId: platformIdSchema,
    createdAt: z.string().datetime(),
    retentionExpiresAt: z.string().datetime().nullable(),
    disclaimer: z.literal(DISCLAIMER),
  })
  .strict()
  .superRefine((value, context) => {
    if (
      value.retentionExpiresAt &&
      Date.parse(value.retentionExpiresAt) <= Date.parse(value.createdAt)
    ) {
      context.addIssue({
        code: "custom",
        path: ["retentionExpiresAt"],
        message: "Report retention expiry must be later than creation.",
      });
    }
    if (
      value.analysisOrigins.some(
        (origin) =>
          origin === "cached_model_result" || origin === "manual_fixture",
      ) &&
      value.inputOrigins.some((origin) => origin !== "bundled_demo")
    ) {
      context.addIssue({
        code: "custom",
        path: ["analysisOrigins"],
        message: "Fixture analysis provenance cannot be mixed with live input.",
      });
    }
  });
export type ReportArtifact = z.infer<typeof reportArtifactSchema>;
