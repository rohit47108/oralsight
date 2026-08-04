import { useEffect, useState } from "react";
import { router, useLocalSearchParams } from "expo-router";
import {
  Alert,
  AppState,
  Image,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { MOUTH_REGION_DETAILS } from "@oralsight/contracts";

import { MaskOverlay } from "@/components/MaskOverlay";
import { Screen } from "@/components/Screen";
import { Button, Card, MetricBar, SectionTitle } from "@/components/Ui";
import { analyzeCapture } from "@/lib/api";
import { captureStorageRejectionReasons } from "@/lib/analysisPolicy";
import { evaluateBundledGuidance } from "@/lib/guidanceRules";
import { analysisStatusTitle, humanizeResultReason } from "@/lib/resultCopy";
import { decryptToTemporaryFile, removeTemporaryFile } from "@/lib/secureFiles";
import { useOralSightStore } from "@/store/useOralSightStore";
import { useAppTheme } from "@/theme";

export default function ResultRoute() {
  const theme = useAppTheme();
  const { captureId } = useLocalSearchParams<{ captureId?: string }>();
  const capture = useOralSightStore((state) =>
    state.captures.find((item) => item.id === captureId),
  );
  const analysis = useOralSightStore((state) =>
    captureId ? state.analyses[captureId] : undefined,
  );
  const pinConfirmed = useOralSightStore((state) =>
    captureId
      ? state.pins.some((pin) => pin.captureIds.includes(captureId))
      : false,
  );
  const confirmObservationPin = useOralSightStore(
    (state) => state.confirmObservationPin,
  );
  const updateCaptureAnalysis = useOralSightStore(
    (state) => state.updateCaptureAnalysis,
  );
  const discardCapture = useOralSightStore((state) => state.discardCapture);
  const setActiveSession = useOralSightStore((state) => state.setActiveSession);
  const sessions = useOralSightStore((state) => state.sessions);
  const currentProfile = useOralSightStore((state) => state.profile);
  const [previewUri, setPreviewUri] = useState<string | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewEpoch, setPreviewEpoch] = useState(0);
  const [researchOpen, setResearchOpen] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [retryError, setRetryError] = useState<string | null>(null);
  const [retryNotice, setRetryNotice] = useState<string | null>(null);
  const sessionProfile =
    sessions.find((session) => session.id === capture?.sessionId)
      ?.intakeProfile ?? currentProfile;
  const guidance = evaluateBundledGuidance(
    sessionProfile,
    analysis ? [analysis] : [],
  );

  useEffect(() => {
    const subscription = AppState.addEventListener("change", (nextState) => {
      if (nextState === "active") setPreviewEpoch((value) => value + 1);
      else setPreviewUri(null);
    });
    return () => subscription.remove();
  }, []);

  useEffect(() => {
    setPreviewUri(null);
    setPreviewError(null);
    if (!capture?.encryptedUri) return undefined;
    let active = true;
    let temporary: string | null = null;
    const extension = capture.mimeType === "image/png" ? "png" : "jpg";
    void decryptToTemporaryFile(
      capture.encryptedUri,
      extension,
      `capture:${capture.id}`,
    )
      .then(async (uri) => {
        if (!active) {
          await removeTemporaryFile(uri);
          return;
        }
        temporary = uri;
        setPreviewUri(uri);
      })
      .catch(() => {
        if (active) {
          console.warn("[ORALSIGHT_RESULT_PREVIEW_FAILED]");
          setPreviewError(
            "The protected image could not be opened on this device.",
          );
        }
      });
    return () => {
      active = false;
      void removeTemporaryFile(temporary);
    };
  }, [capture?.encryptedUri, capture?.id, capture?.mimeType, previewEpoch]);

  if (!capture)
    return (
      <Screen
        title="Result unavailable"
        action={
          <Button label="Back" variant="ghost" onPress={() => router.back()} />
        }
      >
        <Card>
          <Text style={{ color: theme.text }}>
            This protected observation could not be found.
          </Text>
          <Button
            label="Back to scan"
            onPress={() => router.replace("/(tabs)/scan")}
          />
        </Card>
      </Screen>
    );

  const label =
    MOUTH_REGION_DETAILS.find((item) => item.id === capture.region)?.label ??
    capture.region;
  const complete = analysis?.status === "complete";
  const unavailable = !analysis || analysis.status === "failed";
  const statusTitle = analysisStatusTitle(
    analysis?.status,
    Boolean(analysis?.candidateMask),
  );
  const statusIcon: keyof typeof Ionicons.glyphMap =
    complete && analysis?.candidateMask
      ? "scan-outline"
      : complete
        ? "eye-off-outline"
        : analysis?.status === "abstained"
          ? "shield-outline"
          : analysis?.status === "unsupported"
            ? "ban-outline"
            : "cloud-offline-outline";
  const statusReasons = [
    ...new Set([
      ...(analysis?.abstentionReasons ?? []),
      ...(analysis?.quality.reasons ?? []),
      ...(analysis?.uncertainty.limitations ?? []),
    ]),
  ];
  const canRetry =
    capture.inputOrigin === "live_capture" &&
    Boolean(capture.encryptedUri) &&
    !complete;
  const qualityRejected = analysis?.quality.accepted === false;

  const retryAnalysis = async () => {
    if (!canRetry || !previewUri) return;
    setRetrying(true);
    setRetryError(null);
    setRetryNotice(null);
    try {
      const nextAnalysis = await analyzeCapture({
        captureId: capture.id,
        selectedRegion: capture.region,
        imageUri: previewUri,
        mimeType: capture.mimeType,
        inputOrigin: "live_capture",
        localQuality: capture.quality,
      });
      const rejectionReasons = captureStorageRejectionReasons(
        nextAnalysis,
        capture.region,
      );
      if (rejectionReasons.length > 0) {
        await discardCapture(capture.id);
        setActiveSession(capture.sessionId);
        Alert.alert(
          "Retake required",
          `${rejectionReasons.join(" ")} The rejected protected image and any report containing it were removed.`,
        );
        router.replace({
          pathname: "/capture/[region]",
          params: { region: capture.region },
        });
        return;
      }
      await updateCaptureAnalysis(capture.id, nextAnalysis);
      setRetryNotice(
        nextAnalysis.status === "complete"
          ? "Analysis completed and the saved result was updated."
          : nextAnalysis.status === "abstained"
            ? "The service reviewed this image but abstained. No result was invented."
            : nextAnalysis.status === "unsupported"
              ? "The service still considers this image unsupported."
              : "Analysis is still unavailable. The protected image remains saved locally.",
      );
    } catch (error) {
      setRetryError(
        error instanceof Error
          ? error.message
          : "The saved image could not be analyzed again.",
      );
    } finally {
      setRetrying(false);
    }
  };

  return (
    <Screen
      title="Explainable result"
      eyebrow={label}
      action={
        <Button label="Back" variant="ghost" onPress={() => router.back()} />
      }
    >
      <Card
        accent={
          complete && analysis?.candidateMask
            ? "teal"
            : complete
              ? "amber"
              : unavailable
                ? "coral"
                : "amber"
        }
      >
        <SectionTitle
          title={statusTitle}
          subtitle={`${capture.inputOrigin === "bundled_demo" ? "Bundled synthetic input" : "Live capture"} · ${analysisOriginCopy(analysis?.analysisOrigin)}`}
          icon={statusIcon}
        />
        <Text style={[styles.provenance, { color: theme.secondaryText }]}>
          Input provenance and analysis provenance are recorded separately. A
          live failure never receives a fixture result.
        </Text>
      </Card>
      {!complete &&
      analysis?.anatomyPrediction.supported &&
      analysis.anatomyPrediction.selectedRegionMatches ? (
        <Card accent="teal">
          <SectionTitle
            title="Mouth region confirmed"
            subtitle={`The live anatomy check matched ${label} with ${Math.round(analysis.anatomyPrediction.confidence * 100)}% model confidence.`}
            icon="checkmark-circle-outline"
          />
          <Text style={[styles.limitation, { color: theme.secondaryText }]}>
            This confirms only the selected photo region. It is not a finding
            about health or disease.
          </Text>
        </Card>
      ) : null}
      {analysis?.candidateMask ? (
        <MaskOverlay imageUri={previewUri} mask={analysis.candidateMask} />
      ) : previewUri ? (
        <Image
          accessible
          accessibilityLabel={`Saved ${label} observation without a candidate outline`}
          source={{ uri: previewUri }}
          resizeMode="contain"
          style={[styles.preview, { backgroundColor: theme.navy }]}
        />
      ) : (
        <View
          style={[
            styles.preview,
            styles.previewPlaceholder,
            { backgroundColor: theme.navy },
          ]}
        >
          <Text style={styles.previewPlaceholderText}>
            {previewError
              ? "Protected image preview unavailable"
              : capture.encryptedUri
                ? "Opening protected image…"
                : "No protected image is stored for this legacy observation."}
          </Text>
        </View>
      )}
      {previewError ? (
        <Text
          accessibilityRole="alert"
          style={[styles.error, { color: theme.danger }]}
        >
          {previewError}
        </Text>
      ) : null}
      {complete && analysis && !analysis.candidateMask ? (
        <Card accent="amber">
          <SectionTitle
            title="This is not an all-clear"
            subtitle="The released abnormal-area model completed this image but did not return a thresholded candidate outline."
            icon="information-circle-outline"
          />
          <Text style={[styles.limitation, { color: theme.secondaryText }]}>
            An absent outline does not prove that the tissue is healthy or that
            no condition is present. Keep the image for professional discussion
            if the area persists, changes, or worries you.
          </Text>
        </Card>
      ) : null}
      {!complete ? (
        <Card accent={unavailable ? "coral" : "amber"}>
          <SectionTitle
            title="Why no completed result is shown"
            subtitle="The saved image and the analysis state are kept separate."
            icon="information-circle-outline"
          />
          {statusReasons.length ? (
            statusReasons.map((reason) => (
              <Text
                key={reason}
                style={[styles.limitation, { color: theme.secondaryText }]}
              >
                • {humanizeResultReason(reason)}
              </Text>
            ))
          ) : (
            <Text style={[styles.limitation, { color: theme.secondaryText }]}>
              No completed analysis response is stored for this observation.
            </Text>
          )}
          {canRetry ? (
            <>
              <Button
                label="Retry analysis of this saved image"
                icon="refresh-outline"
                variant="secondary"
                loading={retrying}
                disabled={!previewUri}
                onPress={() => {
                  void retryAnalysis();
                }}
              />
              {!previewUri && !previewError ? (
                <Text
                  style={[styles.limitation, { color: theme.secondaryText }]}
                >
                  Opening the protected image before retry is available…
                </Text>
              ) : null}
            </>
          ) : null}
          {qualityRejected ? (
            <Button
              label="Retake this region"
              icon="camera-outline"
              variant="secondary"
              onPress={() => {
                setActiveSession(capture.sessionId);
                router.push({
                  pathname: "/capture/[region]",
                  params: { region: capture.region },
                });
              }}
            />
          ) : null}
          {retryNotice ? (
            <Text
              accessibilityLiveRegion="polite"
              style={[styles.notice, { color: theme.primary }]}
            >
              {retryNotice}
            </Text>
          ) : null}
          {retryError ? (
            <Text
              accessibilityRole="alert"
              style={[styles.error, { color: theme.danger }]}
            >
              {retryError}
            </Text>
          ) : null}
        </Card>
      ) : null}
      {analysis?.candidateMask ? (
        <Card accent={pinConfirmed ? "teal" : "amber"}>
          <SectionTitle
            title={
              pinConfirmed
                ? "Observation pin confirmed"
                : "Confirm map location"
            }
            subtitle="OralSight never links or re-identifies observations automatically."
            icon={pinConfirmed ? "location" : "location-outline"}
          />
          {pinConfirmed ? (
            <Text style={[styles.limitation, { color: theme.secondaryText }]}>
              This single capture is pinned to its named mesh and UV location.
              Later observations remain separate unless you explicitly confirm a
              comparison.
            </Text>
          ) : (
            <Button
              label="Confirm this observation pin"
              icon="location-outline"
              variant="secondary"
              onPress={() => confirmObservationPin(capture.id)}
            />
          )}
        </Card>
      ) : null}
      {analysis?.descriptors ? (
        <Card>
          <SectionTitle
            title="Visible characteristics"
            subtitle="Image-normalized and approximate; not millimeters."
            icon="options-outline"
          />
          <View style={styles.grid}>
            <Descriptor
              label="Area"
              value={`${(analysis.descriptors.normalizedArea * 100).toFixed(1)}%`}
            />
            <Descriptor
              label="Border irregularity"
              value={analysis.descriptors.borderIrregularity.toFixed(2)}
            />
            <Descriptor
              label="Redness"
              value={`${Math.round(analysis.descriptors.meanRedness * 100)}%`}
            />
            <Descriptor
              label="Texture contrast"
              value={`${Math.round(analysis.descriptors.textureContrast * 100)}%`}
            />
          </View>
        </Card>
      ) : null}
      {complete && analysis ? (
        <>
          <Card>
            <SectionTitle
              title="Why this result appears"
              subtitle="A fixed explanation tree derived only from returned fields."
              icon="git-branch-outline"
            />
            {[
              [
                "Quality",
                analysis.quality.accepted
                  ? "Server quality gate accepted the image."
                  : "Server quality gate did not accept the image.",
              ],
              [
                "Anatomy",
                analysis.anatomyPrediction.supported &&
                analysis.anatomyPrediction.selectedRegionMatches
                  ? "Selected anatomy was confirmed."
                  : "Selected anatomy was not confirmed.",
              ],
              [
                "Candidate",
                analysis.candidateMask
                  ? "A candidate boundary and approximate descriptors were returned."
                  : "No candidate boundary was returned.",
              ],
              [
                "Research gates",
                analysis.appearanceOutput?.enabled &&
                analysis.appearanceOutput.gatePassed
                  ? "The appearance gate passed for this deployed model."
                  : "Appearance and disease-category labels remain hidden or disabled.",
              ],
              [
                "Limitations",
                `${analysis.uncertainty.limitations.length} explicit limitation${analysis.uncertainty.limitations.length === 1 ? "" : "s"}; overall confidence ${Math.round(analysis.uncertainty.overallConfidence * 100)}%.`,
              ],
            ].map(([step, explanation], index) => (
              <View key={step} style={styles.treeStep}>
                <View
                  style={[styles.treeIndex, { backgroundColor: theme.mint }]}
                >
                  <Text style={{ color: theme.primary, fontWeight: "900" }}>
                    {index + 1}
                  </Text>
                </View>
                <View style={styles.treeCopy}>
                  <Text style={[styles.treeTitle, { color: theme.text }]}>
                    {step}
                  </Text>
                  <Text
                    style={[styles.limitation, { color: theme.secondaryText }]}
                  >
                    {explanation}
                  </Text>
                </View>
              </View>
            ))}
          </Card>
          <Card>
            <SectionTitle
              title="Confidence constellation"
              subtitle="Several factors are shown instead of one unexplained score."
              icon="analytics-outline"
            />
            <ConfidenceFactor
              label="Image quality"
              value={analysis.uncertainty.imageQualityConfidence}
            />
            <ConfidenceFactor
              label="Dataset similarity"
              value={analysis.uncertainty.datasetSimilarity}
            />
            <ConfidenceFactor
              label="Model agreement"
              value={analysis.uncertainty.modelAgreement}
            />
            {analysis.uncertainty.datasetSimilarity === null ? (
              <Text style={[styles.limitation, { color: theme.secondaryText }]}>
                Dataset similarity is not assessed because no released
                out-of-distribution model is installed.
              </Text>
            ) : null}
            {analysis.uncertainty.modelAgreement === null ? (
              <Text style={[styles.limitation, { color: theme.secondaryText }]}>
                Model agreement is not assessed because no independent ensemble
                has passed its release gate.
              </Text>
            ) : null}
            {analysis.uncertainty.limitations.map((limitation) => (
              <Text
                key={limitation}
                style={[styles.limitation, { color: theme.secondaryText }]}
              >
                • {limitation}
              </Text>
            ))}
          </Card>
        </>
      ) : null}
      {complete &&
      analysis?.appearanceOutput?.enabled &&
      analysis.appearanceOutput.gatePassed ? (
        <Card>
          <SectionTitle
            title="Appearance descriptor"
            subtitle="Pixel pattern only; it does not identify a condition."
            icon="color-palette-outline"
          />
          <Text style={[styles.appearance, { color: theme.text }]}>
            {analysis.appearanceOutput.topLabel?.replaceAll("-", " ") ??
              "Unsupported"}
          </Text>
          <Text style={[styles.limitation, { color: theme.secondaryText }]}>
            {analysis.appearanceOutput.limitation}
          </Text>
        </Card>
      ) : null}
      {complete && analysis ? (
        <Card accent="amber">
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={
              researchOpen
                ? "Hide experimental research output"
                : "Show experimental research output"
            }
            accessibilityState={{ expanded: researchOpen }}
            onPress={() => setResearchOpen((value) => !value)}
            style={({ pressed }) => [
              styles.expand,
              pressed && styles.expandPressed,
            ]}
          >
            <SectionTitle
              title="Experimental research output"
              subtitle="Hidden unless the stricter release gate passes."
              icon="flask-outline"
            />
            <Ionicons
              name={researchOpen ? "chevron-up" : "chevron-down"}
              color={theme.secondaryText}
              size={20}
            />
          </Pressable>
          {researchOpen ? (
            <Text style={[styles.limitation, { color: theme.secondaryText }]}>
              {analysis.diseaseResearchOutput?.enabled &&
              analysis.diseaseResearchOutput.gatePassed
                ? `${analysis.diseaseResearchOutput.topLabel?.replaceAll("_", " ") ?? "No label"} · ${analysis.diseaseResearchOutput.limitation}`
                : (analysis.diseaseResearchOutput?.limitation ??
                  "No disease-category research output was returned.")}
            </Text>
          ) : null}
        </Card>
      ) : null}
      <Card accent="amber">
        <SectionTitle
          title={
            guidance.enabled
              ? guidance.reviewPriority === "professional_review_suggested"
                ? "Professional review suggested"
                : "Clinician-reviewed guidance"
              : "Why no urgency level appears"
          }
          icon="information-circle-outline"
        />
        <Text style={[styles.limitation, { color: theme.text }]}>
          {guidance.statusMessage}
        </Text>
        <Text style={[styles.limitation, { color: theme.secondaryText }]}>
          {guidance.message}
        </Text>
      </Card>
      <Button
        label="Open timeline"
        icon="analytics-outline"
        onPress={() => router.push("/(tabs)/timeline")}
      />
      <Button
        label="Return to scan"
        variant="secondary"
        icon="scan-outline"
        onPress={() => router.replace("/(tabs)/scan")}
      />
    </Screen>
  );
}

function Descriptor({ label, value }: { label: string; value: string }) {
  const theme = useAppTheme();
  return (
    <View style={[styles.descriptor, { backgroundColor: theme.background }]}>
      <Text style={[styles.descriptorValue, { color: theme.primary }]}>
        {value}
      </Text>
      <Text style={[styles.descriptorLabel, { color: theme.secondaryText }]}>
        {label}
      </Text>
    </View>
  );
}

function ConfidenceFactor({
  label,
  value,
}: {
  label: string;
  value: number | null;
}) {
  const theme = useAppTheme();
  if (value !== null) return <MetricBar label={label} value={value} />;
  return (
    <View
      accessible
      accessibilityLabel={`${label}: not assessed`}
      style={[
        styles.unavailableFactor,
        { borderColor: theme.border, backgroundColor: theme.background },
      ]}
    >
      <Text style={[styles.unavailableFactorLabel, { color: theme.text }]}>
        {label}
      </Text>
      <Text
        style={[styles.unavailableFactorValue, { color: theme.secondaryText }]}
      >
        Not assessed
      </Text>
    </View>
  );
}

function analysisOriginCopy(
  origin:
    | "live_model"
    | "cached_model_result"
    | "manual_fixture"
    | "unavailable"
    | undefined,
): string {
  if (origin === "live_model") return "Live model response";
  if (origin === "cached_model_result") return "Hash-matched cached result";
  if (origin === "manual_fixture") return "Bundled demonstration result";
  return "Analysis unavailable";
}

const styles = StyleSheet.create({
  provenance: { fontSize: 12, lineHeight: 18 },
  preview: { width: "100%", minHeight: 260, borderRadius: 22 },
  previewPlaceholder: { alignItems: "center", justifyContent: "center" },
  previewPlaceholderText: { color: "#FFFFFF", fontWeight: "700" },
  grid: { flexDirection: "row", flexWrap: "wrap", gap: 9 },
  descriptor: { width: "48%", padding: 12, borderRadius: 14, gap: 3 },
  descriptorValue: {
    fontSize: 21,
    fontWeight: "900",
    fontVariant: ["tabular-nums"],
  },
  descriptorLabel: { fontSize: 11, fontWeight: "700" },
  limitation: { fontSize: 13, lineHeight: 19 },
  unavailableFactor: {
    minHeight: 48,
    borderWidth: 1,
    borderRadius: 12,
    paddingHorizontal: 12,
    paddingVertical: 9,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12,
  },
  unavailableFactorLabel: { flex: 1, fontSize: 13, fontWeight: "800" },
  unavailableFactorValue: { fontSize: 13, fontWeight: "700" },
  appearance: { fontSize: 23, fontWeight: "900", textTransform: "capitalize" },
  expand: {
    minHeight: 48,
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  expandPressed: { opacity: 0.8, transform: [{ scale: 0.99 }] },
  treeStep: { flexDirection: "row", gap: 10, alignItems: "flex-start" },
  treeIndex: {
    width: 28,
    height: 28,
    borderRadius: 10,
    alignItems: "center",
    justifyContent: "center",
  },
  treeCopy: { flex: 1, gap: 2 },
  treeTitle: { fontSize: 13, fontWeight: "800" },
  notice: { fontSize: 13, lineHeight: 19, fontWeight: "700" },
  error: { fontSize: 13, lineHeight: 19, fontWeight: "700" },
});
