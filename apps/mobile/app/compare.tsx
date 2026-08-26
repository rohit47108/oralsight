import { useEffect, useMemo, useRef, useState } from "react";
import { router } from "expo-router";
import {
  ActivityIndicator,
  AppState,
  StyleSheet,
  Text,
  View,
} from "react-native";
import {
  MOUTH_REGION_DETAILS,
  type ComparisonCalibrationRequest,
  type ComparisonResult,
  type MouthRegion,
} from "@oralsight/contracts";

import { ComparisonViewer } from "@/components/ComparisonViewer";
import { CaptureGuidanceMetrics } from "@/components/CaptureGuidanceMetrics";
import { Screen } from "@/components/Screen";
import {
  Button,
  Card,
  ChoiceChip,
  EmptyState,
  MetricBar,
  SectionTitle,
} from "@/components/Ui";
import {
  analysisReference,
  compareCaptures,
  type ComparisonAnalysisReference,
} from "@/lib/api";
import {
  isCrossSessionChronologicalComparison,
  isEligibleLongitudinalCapture,
} from "@/lib/longitudinalPolicy";
import { humanizeResultReason } from "@/lib/resultCopy";
import { decryptToTemporaryFile, removeTemporaryFile } from "@/lib/secureFiles";
import { useOralSightStore } from "@/store/useOralSightStore";
import { useAppTheme } from "@/theme";
import type { CaptureRecord } from "@/types";

interface PreparedComparison {
  baselineUri: string;
  currentUri: string;
  baselineId: string;
  currentId: string;
  baselineMimeType: "image/jpeg" | "image/png";
  currentMimeType: "image/jpeg" | "image/png";
  baselineAnalysis: ComparisonAnalysisReference;
  currentAnalysis: ComparisonAnalysisReference;
}

export default function CompareRoute() {
  const theme = useAppTheme();
  const captures = useOralSightStore((state) => state.captures);
  const analyses = useOralSightStore((state) => state.analyses);
  const addComparison = useOralSightStore((state) => state.addComparison);
  const [selectedRegion, setSelectedRegion] = useState<MouthRegion | null>(
    null,
  );
  const [baselineId, setBaselineId] = useState<string | null>(null);
  const [currentId, setCurrentId] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [requestKind, setRequestKind] = useState<
    "suggestion" | "comparison" | null
  >(null);
  const [error, setError] = useState<string | null>(null);
  const [suggestion, setSuggestion] = useState<ComparisonResult | null>(null);
  const [result, setResult] = useState<ComparisonResult | null>(null);
  const [prepared, setPrepared] = useState<PreparedComparison | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewEpoch, setPreviewEpoch] = useState(0);
  const requestToken = useRef(0);

  const eligibleCaptures = useMemo(
    () =>
      captures
        .filter((capture) => {
          return isEligibleLongitudinalCapture(capture, analyses[capture.id]);
        })
        .sort((a, b) => a.capturedAt.localeCompare(b.capturedAt)),
    [analyses, captures],
  );

  const eligibleRegions = useMemo(
    () =>
      MOUTH_REGION_DETAILS.filter(
        (detail) =>
          new Set(
            eligibleCaptures
              .filter((capture) => capture.region === detail.id)
              .map((capture) => capture.sessionId),
          ).size >= 2,
      ),
    [eligibleCaptures],
  );

  const regionCaptures = useMemo(
    () =>
      selectedRegion
        ? eligibleCaptures.filter(
            (capture) => capture.region === selectedRegion,
          )
        : [],
    [eligibleCaptures, selectedRegion],
  );

  useEffect(() => {
    if (
      selectedRegion &&
      eligibleRegions.some((detail) => detail.id === selectedRegion)
    ) {
      return;
    }
    setSelectedRegion(eligibleRegions[0]?.id ?? null);
  }, [eligibleRegions, selectedRegion]);

  useEffect(() => {
    const baseline = regionCaptures.at(-2);
    const current = regionCaptures.at(-1);
    setBaselineId(baseline?.id ?? null);
    setCurrentId(current?.id ?? null);
    setConfirmed(false);
    setSuggestion(null);
    setResult(null);
    setError(null);
  }, [regionCaptures]);

  const selectedBaseline = useMemo(
    () => regionCaptures.find((capture) => capture.id === baselineId),
    [baselineId, regionCaptures],
  );
  const selectedCurrent = useMemo(
    () => regionCaptures.find((capture) => capture.id === currentId),
    [currentId, regionCaptures],
  );
  const pair = useMemo<[CaptureRecord, CaptureRecord] | null>(
    () =>
      selectedBaseline &&
      selectedCurrent &&
      selectedBaseline.id !== selectedCurrent.id &&
      isCrossSessionChronologicalComparison(selectedBaseline, selectedCurrent)
        ? [selectedBaseline, selectedCurrent]
        : null,
    [selectedBaseline, selectedCurrent],
  );

  const label =
    eligibleRegions.find((region) => region.id === selectedRegion)?.label ??
    "Observation comparison";

  useEffect(() => {
    const subscription = AppState.addEventListener("change", (nextState) => {
      if (nextState === "active") {
        setPreviewEpoch((value) => value + 1);
      } else {
        requestToken.current += 1;
        setBusy(false);
        setRequestKind(null);
        setPrepared(null);
        setConfirmed(false);
        setSuggestion(null);
      }
    });
    return () => subscription.remove();
  }, []);

  useEffect(() => {
    requestToken.current += 1;
    let active = true;
    let createdUris: [string, string] | null = null;
    setPrepared(null);
    setConfirmed(false);
    setSuggestion(null);
    setResult(null);
    setPreviewError(null);
    setBusy(false);
    setRequestKind(null);

    if (!pair) {
      setPreviewLoading(false);
      return () => {
        active = false;
      };
    }

    setPreviewLoading(true);
    const preparePreview = async () => {
      let baselineUri: string | null = null;
      let currentUri: string | null = null;
      try {
        const baselineStoredAnalysis = analyses[pair[0].id];
        const currentStoredAnalysis = analyses[pair[1].id];
        if (
          !pair[0].encryptedUri ||
          !pair[1].encryptedUri ||
          !baselineStoredAnalysis ||
          !currentStoredAnalysis
        ) {
          throw new Error(
            "Both observations need a protected image and saved analysis record.",
          );
        }
        baselineUri = await decryptToTemporaryFile(
          pair[0].encryptedUri,
          pair[0].mimeType === "image/png" ? "png" : "jpg",
          `capture:${pair[0].id}`,
        );
        currentUri = await decryptToTemporaryFile(
          pair[1].encryptedUri,
          pair[1].mimeType === "image/png" ? "png" : "jpg",
          `capture:${pair[1].id}`,
        );
        createdUris = [baselineUri, currentUri];
        if (!active) {
          const staleUris = createdUris;
          createdUris = null;
          await Promise.all(staleUris.map((uri) => removeTemporaryFile(uri)));
          return;
        }
        setPrepared({
          baselineUri,
          currentUri,
          baselineId: pair[0].id,
          currentId: pair[1].id,
          baselineMimeType: pair[0].mimeType,
          currentMimeType: pair[1].mimeType,
          baselineAnalysis: analysisReference(baselineStoredAnalysis),
          currentAnalysis: analysisReference(currentStoredAnalysis),
        });
      } catch (previewFailure) {
        await Promise.all([
          removeTemporaryFile(baselineUri),
          removeTemporaryFile(currentUri),
        ]);
        if (active) {
          setPreviewError(
            previewFailure instanceof Error
              ? previewFailure.message
              : "Could not prepare the observation preview.",
          );
        }
      } finally {
        if (active) setPreviewLoading(false);
      }
    };

    void preparePreview();
    return () => {
      active = false;
      if (createdUris) {
        const staleUris = createdUris;
        createdUris = null;
        void Promise.all(staleUris.map((uri) => removeTemporaryFile(uri)));
      }
    };
  }, [analyses, pair, previewEpoch]);

  const runComparison = async (userConfirmedMatch: boolean) => {
    if (
      !prepared ||
      !pair ||
      !selectedRegion ||
      (userConfirmedMatch && !confirmed)
    ) {
      return;
    }
    setBusy(true);
    const currentRequestToken = ++requestToken.current;
    setRequestKind(userConfirmedMatch ? "comparison" : "suggestion");
    setError(null);
    if (userConfirmedMatch) {
      setResult(null);
    } else {
      setSuggestion(null);
      setConfirmed(false);
    }
    try {
      const comparison = await compareCaptures({
        baselineCaptureId: prepared.baselineId,
        currentCaptureId: prepared.currentId,
        region: selectedRegion,
        baselineImageUri: prepared.baselineUri,
        currentImageUri: prepared.currentUri,
        baselineMimeType: prepared.baselineMimeType,
        currentMimeType: prepared.currentMimeType,
        baselineAnalysis: prepared.baselineAnalysis,
        currentAnalysis: prepared.currentAnalysis,
        inputOrigin: "live_capture",
        userConfirmedMatch,
        baselineCalibration: calibrationRequest(pair[0]),
        currentCalibration: calibrationRequest(pair[1]),
      });
      if (requestToken.current !== currentRequestToken) return;
      if (userConfirmedMatch) {
        await addComparison(comparison);
        setResult(comparison);
      } else {
        setSuggestion(comparison);
      }
    } catch (comparisonError) {
      if (requestToken.current !== currentRequestToken) return;
      setError(
        comparisonError instanceof Error
          ? comparisonError.message
          : "Comparison failed.",
      );
    } finally {
      if (requestToken.current === currentRequestToken) {
        setBusy(false);
        setRequestKind(null);
      }
    }
  };

  if (eligibleRegions.length === 0) {
    return (
      <Screen
        title="Compare observations"
        eyebrow="Longitudinal review"
        action={
          <Button label="Back" variant="ghost" onPress={() => router.back()} />
        }
      >
        <EmptyState
          icon="git-compare-outline"
          title="Two real observations are needed"
          body="Capture the same mouth region in two separate observations. OralSight will not create sample images or substitute demo results."
          action={
            <Button
              label="Return to scan"
              onPress={() => router.replace("/(tabs)/scan")}
            />
          }
        />
      </Screen>
    );
  }

  return (
    <Screen
      title="Compare observations"
      eyebrow={label}
      action={
        <Button
          label="Back"
          variant="ghost"
          disabled={busy}
          onPress={() => router.back()}
        />
      }
    >
      <Card>
        <SectionTitle
          title="Choose one mouth region"
          subtitle="Only regions with at least two protected, quality-accepted observations are shown."
          icon="locate-outline"
        />
        <View accessibilityRole="radiogroup" style={styles.selectionGroup}>
          {eligibleRegions.map((region) => (
            <ChoiceChip
              key={region.id}
              label={region.shortLabel}
              selected={selectedRegion === region.id}
              accessibilityRole="radio"
              disabled={busy}
              onPress={() => setSelectedRegion(region.id)}
            />
          ))}
        </View>
      </Card>

      <Card>
        <SectionTitle
          title="Choose the earlier observation"
          subtitle="This is the baseline image."
          icon="time-outline"
        />
        <View accessibilityRole="radiogroup" style={styles.selectionGroup}>
          {regionCaptures.map((capture, index) => (
            <ChoiceChip
              key={capture.id}
              label={captureLabel(capture, index)}
              selected={baselineId === capture.id}
              accessibilityRole="radio"
              disabled={
                busy ||
                currentId === capture.id ||
                Boolean(
                  selectedCurrent &&
                  !isCrossSessionChronologicalComparison(
                    capture,
                    selectedCurrent,
                  ),
                )
              }
              onPress={() => setBaselineId(capture.id)}
            />
          ))}
        </View>
      </Card>

      <Card>
        <SectionTitle
          title="Choose the later observation"
          subtitle="This is the current image."
          icon="calendar-outline"
        />
        <View accessibilityRole="radiogroup" style={styles.selectionGroup}>
          {regionCaptures.map((capture, index) => (
            <ChoiceChip
              key={capture.id}
              label={captureLabel(capture, index)}
              selected={currentId === capture.id}
              accessibilityRole="radio"
              disabled={
                busy ||
                baselineId === capture.id ||
                Boolean(
                  selectedBaseline &&
                  !isCrossSessionChronologicalComparison(
                    selectedBaseline,
                    capture,
                  ),
                )
              }
              onPress={() => setCurrentId(capture.id)}
            />
          ))}
        </View>
      </Card>

      <Card accent="amber">
        <SectionTitle
          title="Review the selected pair"
          subtitle={`${label}, same named anatomical region. You must inspect both original captures before linking them.`}
          icon="search-circle-outline"
        />
        <Text style={[styles.note, { color: theme.secondaryText }]}>
          A released re-identification head may suggest whether these images
          could show the same observation. It never links them by itself. You
          review and confirm the pair after seeing that suggestion.
        </Text>
        {previewLoading ? (
          <View style={styles.previewLoading}>
            <ActivityIndicator color={theme.primary} />
            <Text style={[styles.note, { color: theme.secondaryText }]}>
              Decrypting both protected images for your review...
            </Text>
          </View>
        ) : null}
        {previewError ? (
          <View style={styles.errorGroup}>
            <Text
              accessibilityRole="alert"
              style={[styles.error, { color: theme.danger }]}
            >
              {previewError}
            </Text>
            <Button
              label="Retry preview"
              variant="secondary"
              onPress={() => setPreviewEpoch((value) => value + 1)}
            />
          </View>
        ) : null}
        {prepared ? (
          <>
            <ComparisonViewer
              baselineUri={prepared.baselineUri}
              currentUri={prepared.currentUri}
              baselineMask={
                pair ? (analyses[pair[0].id]?.candidateMask ?? null) : null
              }
              currentMask={
                pair ? (analyses[pair[1].id]?.candidateMask ?? null) : null
              }
              registrationAlignment={result?.registrationAlignment ?? null}
            />
            {pair?.[1].captureGuidance ? (
              <View style={styles.guidanceComparison}>
                <CaptureGuidanceMetrics
                  snapshot={pair[1].captureGuidance}
                  exposureScore={pair[1].quality.exposureScore}
                  baselineSnapshot={pair[0].captureGuidance ?? null}
                  baselineExposureScore={pair[0].quality.exposureScore}
                  baselineMillimetersPerPixel={calibratedScale(pair[0])}
                  currentMillimetersPerPixel={calibratedScale(pair[1])}
                />
              </View>
            ) : (
              <Text style={[styles.note, { color: theme.secondaryText }]}>
                Capture-condition matching is unavailable because the newer
                image predates saved device guidance readings.
              </Text>
            )}
          </>
        ) : null}
      </Card>

      <Button
        label="Check automated link availability"
        icon="sparkles-outline"
        disabled={!prepared || busy}
        loading={requestKind === "suggestion"}
        loadingLabel="Checking link availability..."
        onPress={() => {
          void runComparison(false);
        }}
      />

      {error ? (
        <Text
          accessibilityRole="alert"
          style={[styles.error, { color: theme.danger }]}
        >
          {error}
        </Text>
      ) : null}

      {suggestion ? (
        <Card
          accent={suggestion.candidateMatchScore === null ? "amber" : "teal"}
        >
          <SectionTitle
            title={
              suggestion.candidateMatchScore === null
                ? "Automated suggestion unavailable"
                : "Automated link suggestion"
            }
            subtitle="The score suggests visual similarity. You confirm whether both images show the same observation."
            icon="link-outline"
          />
          {suggestion.candidateMatchScore !== null ? (
            <MetricBar
              label="Candidate match score"
              value={suggestion.candidateMatchScore}
            />
          ) : (
            <Text style={[styles.note, { color: theme.secondaryText }]}>
              No released re-identification score was available. You can still
              record your own review, but change remains hidden unless every
              model and registration gate passes.
            </Text>
          )}
          <ChoiceChip
            label="I reviewed both images and confirm they show the same observation"
            selected={confirmed}
            onPress={() => setConfirmed((value) => !value)}
            accessibilityRole="checkbox"
          />
        </Card>
      ) : null}

      <Button
        label="Compare confirmed observations"
        icon="git-compare-outline"
        disabled={!suggestion || !confirmed || !prepared || busy}
        loading={requestKind === "comparison"}
        loadingLabel="Comparing confirmed observations..."
        onPress={() => {
          void runComparison(true);
        }}
      />

      {result ? (
        <>
          <Card accent={result.comparable ? "teal" : "amber"}>
            <SectionTitle
              title={
                result.comparable
                  ? "Images are comparable"
                  : "Insufficient comparable data"
              }
              subtitle={`${result.analysisOrigin.replaceAll("_", " ")}; user confirmation recorded`}
              icon={
                result.comparable
                  ? "checkmark-circle-outline"
                  : "alert-circle-outline"
              }
            />
            <MetricBar
              label="Registration confidence"
              value={result.registrationConfidence}
            />
            <MetricBar
              label="Matching landmark inliers"
              value={result.inlierRatio}
            />
            <Text style={[styles.note, { color: theme.secondaryText }]}>
              Alignment error:{" "}
              {(result.reprojectionErrorRatio * 100).toFixed(1)}% of the image
              diagonal. Reporting requires at least 60% landmark inliers and no
              more than 3% alignment error.
            </Text>
            {result.comparable ? (
              <>
                <View style={styles.change}>
                  <Text style={[styles.changeValue, { color: theme.primary }]}>
                    {result.normalizedChange === null
                      ? "Unavailable"
                      : `${(result.normalizedChange * 100).toFixed(1)}%`}
                  </Text>
                  <Text style={[styles.note, { color: theme.secondaryText }]}>
                    approximate normalized area change
                  </Text>
                </View>
                {result.descriptorChanges ? (
                  <>
                    <Text style={[styles.groupLabel, { color: theme.text }]}>
                      Approximate visible changes
                    </Text>
                    <Text style={[styles.note, { color: theme.secondaryText }]}>
                      Size and perimeter are normalized to the aligned images.
                      Color and texture values are image-statistic changes, not
                      disease scores.
                    </Text>
                    <View style={styles.changeGrid}>
                      <ChangeMetric
                        label="Width"
                        value={signedPercent(
                          result.descriptorChanges.normalizedWidthChange,
                        )}
                      />
                      <ChangeMetric
                        label="Height"
                        value={signedPercent(
                          result.descriptorChanges.normalizedHeightChange,
                        )}
                      />
                      <ChangeMetric
                        label="Perimeter"
                        value={signedPercent(
                          result.descriptorChanges.normalizedPerimeterChange,
                        )}
                      />
                      <ChangeMetric
                        label="Border irregularity"
                        value={signedNumber(
                          result.descriptorChanges.borderIrregularityChange,
                        )}
                      />
                      <ChangeMetric
                        label="Redness"
                        value={signedPoints(
                          result.descriptorChanges.meanRednessChange,
                        )}
                      />
                      <ChangeMetric
                        label="Brightness"
                        value={signedPoints(
                          result.descriptorChanges.meanBrightnessChange,
                        )}
                      />
                      <ChangeMetric
                        label="Texture contrast"
                        value={signedPoints(
                          result.descriptorChanges.textureContrastChange,
                        )}
                      />
                      <ChangeMetric
                        label="Ulceration-like contrast"
                        value={
                          result.descriptorChanges
                            .ulcerationLikeContrastChange === null
                            ? "Not assessed"
                            : signedPoints(
                                result.descriptorChanges
                                  .ulcerationLikeContrastChange,
                              )
                        }
                        detail="Center-to-edge image contrast only"
                      />
                    </View>
                  </>
                ) : (
                  <Text style={[styles.note, { color: theme.secondaryText }]}>
                    Detailed descriptor changes were not stored for this older
                    comparison.
                  </Text>
                )}
                {result.calibratedMeasurementChanges ? (
                  <View
                    style={[
                      styles.calibratedPanel,
                      {
                        borderColor: theme.border,
                        backgroundColor: theme.background,
                      },
                    ]}
                  >
                    <Text style={[styles.groupLabel, { color: theme.text }]}>
                      Calibrated estimate
                    </Text>
                    <Text style={[styles.note, { color: theme.secondaryText }]}>
                      Shown only because the versioned 20 mm marker and
                      same-plane checks passed in both images. These are not
                      clinical measurements.
                    </Text>
                    <View style={styles.changeGrid}>
                      <ChangeMetric
                        label="Width"
                        value={signedUnit(
                          result.calibratedMeasurementChanges.widthChangeMm,
                          "mm",
                        )}
                        detail={`${result.calibratedMeasurementChanges.baselineWidthMm.toFixed(1)} to ${result.calibratedMeasurementChanges.currentWidthMm.toFixed(1)} mm`}
                      />
                      <ChangeMetric
                        label="Height"
                        value={signedUnit(
                          result.calibratedMeasurementChanges.heightChangeMm,
                          "mm",
                        )}
                        detail={`${result.calibratedMeasurementChanges.baselineHeightMm.toFixed(1)} to ${result.calibratedMeasurementChanges.currentHeightMm.toFixed(1)} mm`}
                      />
                      <ChangeMetric
                        label="Bounding-box area"
                        value={signedUnit(
                          result.calibratedMeasurementChanges.areaChangeMm2,
                          "mm²",
                        )}
                        detail={`${result.calibratedMeasurementChanges.baselineAreaMm2.toFixed(1)} to ${result.calibratedMeasurementChanges.currentAreaMm2.toFixed(1)} mm²`}
                      />
                    </View>
                  </View>
                ) : result.calibrationSuppressionReasons?.length ? (
                  <View
                    style={[
                      styles.calibratedPanel,
                      {
                        borderColor: theme.border,
                        backgroundColor: theme.background,
                      },
                    ]}
                  >
                    <Text style={[styles.groupLabel, { color: theme.text }]}>
                      Millimeter change unavailable
                    </Text>
                    {result.calibrationSuppressionReasons.map((reason) => (
                      <Text
                        key={reason}
                        style={[styles.note, { color: theme.secondaryText }]}
                      >
                        • {humanizeResultReason(reason)}
                      </Text>
                    ))}
                  </View>
                ) : null}
              </>
            ) : (
              result.suppressionReasons.map((reason) => (
                <Text
                  key={reason}
                  style={[styles.note, { color: theme.secondaryText }]}
                >
                  • {humanizeResultReason(reason)}
                </Text>
              ))
            )}
          </Card>
          <Card>
            <SectionTitle
              title="What the comparison means"
              icon="information-circle-outline"
            />
            <Text style={[styles.note, { color: theme.text }]}>
              Change is reported only when geometric comparability clears the
              required thresholds. Tissue deformation, angle, lighting, and
              different devices can invalidate a comparison. This does not
              measure disease risk.
            </Text>
          </Card>
        </>
      ) : null}
    </Screen>
  );
}

function captureLabel(capture: CaptureRecord, index: number): string {
  const date = new Date(capture.capturedAt);
  const formatted = Number.isNaN(date.getTime())
    ? capture.capturedAt
    : date.toLocaleString();
  return `Observation ${index + 1}: ${formatted}`;
}

function calibrationRequest(
  capture: CaptureRecord,
): ComparisonCalibrationRequest | null {
  if (
    capture.calibrationRequested !== true ||
    capture.calibrationPlaneConfirmed !== true ||
    capture.calibrationCardVersion !== "oralsight-calibration-v1"
  ) {
    return null;
  }
  return {
    cardVersion: "oralsight-calibration-v1",
    markerId: 17,
    markerSideMm: 20,
    planeConfirmed: true,
  };
}

function calibratedScale(capture: CaptureRecord): number | null {
  return capture.calibration?.status === "valid"
    ? capture.calibration.millimetersPerPixel
    : null;
}

function signedPercent(value: number): string {
  return `${value >= 0 ? "+" : ""}${(value * 100).toFixed(1)}%`;
}

function signedPoints(value: number): string {
  return `${value >= 0 ? "+" : ""}${(value * 100).toFixed(1)} points`;
}

function signedNumber(value: number): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}`;
}

function signedUnit(value: number, unit: string): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(1)} ${unit}`;
}

function ChangeMetric({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail?: string;
}) {
  const theme = useAppTheme();
  return (
    <View
      accessible
      accessibilityLabel={`${label}: ${value}${detail ? `. ${detail}` : ""}`}
      style={[
        styles.changeMetric,
        { backgroundColor: theme.surface, borderColor: theme.border },
      ]}
    >
      <Text style={[styles.changeMetricValue, { color: theme.primary }]}>
        {value}
      </Text>
      <Text style={[styles.changeMetricLabel, { color: theme.text }]}>
        {label}
      </Text>
      {detail ? (
        <Text
          style={[styles.changeMetricDetail, { color: theme.secondaryText }]}
        >
          {detail}
        </Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  selectionGroup: { gap: 8 },
  note: { fontSize: 13, lineHeight: 20 },
  error: { fontSize: 13, fontWeight: "700", textAlign: "center" },
  errorGroup: { gap: 10 },
  previewLoading: { alignItems: "center", gap: 9, paddingVertical: 16 },
  guidanceComparison: { marginTop: 14 },
  change: { alignItems: "center", padding: 10 },
  changeValue: {
    fontSize: 30,
    fontWeight: "900",
    fontVariant: ["tabular-nums"],
  },
  groupLabel: { fontSize: 15, fontWeight: "900", marginTop: 8 },
  changeGrid: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  changeMetric: {
    width: "48%",
    minHeight: 82,
    borderWidth: 1,
    borderRadius: 14,
    padding: 11,
    gap: 3,
  },
  changeMetricValue: {
    fontSize: 18,
    fontWeight: "900",
    fontVariant: ["tabular-nums"],
  },
  changeMetricLabel: { fontSize: 12, fontWeight: "800" },
  changeMetricDetail: { fontSize: 11, lineHeight: 15 },
  calibratedPanel: { borderWidth: 1, borderRadius: 16, padding: 12, gap: 8 },
});
