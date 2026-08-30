import type {
  AnalysisResult,
  ComparisonResult,
  MouthRegion,
  QualityResult,
} from "@oralsight/contracts";

interface TrajectoryCapture {
  id: string;
  region: MouthRegion;
  capturedAt: string;
  inputOrigin: "live_capture" | "bundled_demo";
  quality: QualityResult;
  samplePlaceholder?: boolean;
}

export interface TrajectoryPoint {
  captureId: string;
  capturedAt: string;
  normalizedArea: number;
  qualityScore: number;
  confidence: number;
  comparableFromPrevious: boolean;
}

export interface TrajectorySeries {
  region: MouthRegion;
  points: TrajectoryPoint[];
}

const clamp = (value: number) => Math.min(1, Math.max(0, value));

export function captureQualityScore(quality: QualityResult): number {
  const factors = [
    quality.blurScore,
    quality.exposureScore,
    1 - quality.glareScore,
    1 - quality.obstructionScore,
  ];
  return clamp(factors.reduce((total, factor) => total + factor, 0) / 4);
}

export function buildTrajectorySeries(
  captures: readonly TrajectoryCapture[],
  analyses: Readonly<Record<string, AnalysisResult | undefined>>,
  comparisons: readonly ComparisonResult[],
): TrajectorySeries[] {
  const pointsByRegion = new Map<MouthRegion, TrajectoryPoint[]>();

  for (const capture of captures) {
    const analysis = analyses[capture.id];
    if (
      capture.inputOrigin !== "live_capture" ||
      capture.samplePlaceholder ||
      !capture.quality.accepted ||
      !Number.isFinite(Date.parse(capture.capturedAt)) ||
      analysis?.captureId !== capture.id ||
      analysis.region !== capture.region ||
      analysis.inputOrigin !== "live_capture" ||
      analysis.analysisOrigin !== "live_model" ||
      analysis.status !== "complete" ||
      !analysis.quality.accepted ||
      !analysis.descriptors
    ) {
      continue;
    }

    const points = pointsByRegion.get(capture.region) ?? [];
    points.push({
      captureId: capture.id,
      capturedAt: capture.capturedAt,
      normalizedArea: analysis.descriptors.normalizedArea,
      qualityScore: captureQualityScore(capture.quality),
      confidence: analysis.uncertainty.overallConfidence,
      comparableFromPrevious: false,
    });
    pointsByRegion.set(capture.region, points);
  }

  return [...pointsByRegion.entries()]
    .map(([region, unsortedPoints]) => {
      const points = unsortedPoints
        .slice()
        .sort(
          (left, right) =>
            Date.parse(left.capturedAt) - Date.parse(right.capturedAt),
        );
      return {
        region,
        points: points.map((point, index) => {
          const previous = points[index - 1];
          if (!previous) return point;
          const comparison = comparisons.find(
            (candidate) =>
              candidate.region === region &&
              candidate.baselineCaptureId === previous.captureId &&
              candidate.currentCaptureId === point.captureId &&
              candidate.inputOrigin === "live_capture" &&
              candidate.analysisOrigin === "live_model" &&
              candidate.userConfirmedMatch &&
              candidate.comparable,
          );
          return {
            ...point,
            comparableFromPrevious: Boolean(comparison),
          };
        }),
      };
    })
    .sort((left, right) => left.region.localeCompare(right.region));
}
