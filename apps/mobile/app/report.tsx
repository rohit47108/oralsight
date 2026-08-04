import { useState } from "react";
import { router } from "expo-router";
import { StyleSheet, Text } from "react-native";

import { Screen } from "@/components/Screen";
import { Button, Card, EmptyState, SectionTitle } from "@/components/Ui";
import {
  generateEncryptedObservationReport,
  shareEncryptedReport,
} from "@/lib/report";
import { comparisonsEndingInSession } from "@/lib/longitudinalPolicy";
import { reportContainsSyntheticData } from "@/lib/reportPolicy";
import { scanProgress } from "@/lib/scanLogic";
import { useOralSightStore } from "@/store/useOralSightStore";
import { useAppTheme } from "@/theme";

export default function ReportRoute() {
  const theme = useAppTheme();
  const activeSessionId = useOralSightStore((state) => state.activeSessionId);
  const sessions = useOralSightStore((state) => state.sessions);
  const captures = useOralSightStore((state) => state.captures);
  const analyses = useOralSightStore((state) => state.analyses);
  const comparisons = useOralSightStore((state) => state.comparisons);
  const pins = useOralSightStore((state) => state.pins);
  const reports = useOralSightStore((state) => state.reports);
  const profile = useOralSightStore((state) => state.profile);
  const consentedAt = useOralSightStore((state) => state.consentedAt);
  const addReport = useOralSightStore((state) => state.addReport);
  const [busy, setBusy] = useState(false);
  const [shareBusy, setShareBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const session = sessions.find((item) => item.id === activeSessionId);
  const sessionCaptures = captures.filter(
    (capture) => capture.sessionId === activeSessionId,
  );
  const sessionCaptureIds = new Set(
    sessionCaptures.map((capture) => capture.id),
  );
  const sessionComparisons = comparisonsEndingInSession(
    comparisons,
    sessionCaptureIds,
  );
  const comparisonCaptureIds = new Set(
    sessionComparisons.flatMap((comparison) => [
      comparison.baselineCaptureId,
      comparison.currentCaptureId,
    ]),
  );
  const comparisonCaptures = captures.filter((capture) =>
    comparisonCaptureIds.has(capture.id),
  );
  const sessionPins = pins.filter((pin) =>
    pin.captureIds.some((captureId) => sessionCaptureIds.has(captureId)),
  );
  const latest = reports
    .filter((report) => report.sessionId === activeSessionId)
    .at(-1);
  const progress = activeSessionId
    ? scanProgress(captures, activeSessionId)
    : null;
  const syntheticReport = session
    ? reportContainsSyntheticData(session, sessionCaptures)
    : false;

  const generate = async () => {
    if (!session) return;
    setBusy(true);
    setError(null);
    try {
      await addReport(
        await generateEncryptedObservationReport({
          session,
          captures: sessionCaptures,
          comparisonCaptures,
          analyses,
          comparisons: sessionComparisons,
          pins: sessionPins,
          profile: session.intakeProfile ?? profile,
          consentedAt: session.consentedAt ?? consentedAt,
        }),
      );
    } catch (reportError) {
      setError(
        reportError instanceof Error
          ? reportError.message
          : "Report generation failed.",
      );
    } finally {
      setBusy(false);
    }
  };

  if (!session || !progress || progress.completed < progress.total)
    return (
      <Screen title="Local report">
        <Card>
          <EmptyState
            icon="document-outline"
            title={
              session
                ? `Complete all eight regions (${progress?.completed ?? 0}/8)`
                : "No active session"
            }
            body="A local observation report for clinician discussion is generated only after one quality-accepted capture exists for every canonical region."
            action={
              <Button
                label="Go to scan"
                onPress={() => router.replace("/(tabs)/scan")}
              />
            }
          />
        </Card>
      </Screen>
    );
  return (
    <Screen
      title={
        syntheticReport
          ? "Synthetic demonstration report"
          : "Local observation report"
      }
      eyebrow={
        syntheticReport
          ? "Not patient data"
          : latest
            ? "Generated and encrypted locally"
            : "Ready to generate locally"
      }
      action={
        <Button label="Back" variant="ghost" onPress={() => router.back()} />
      }
    >
      {syntheticReport ? (
        <Card accent="coral">
          <SectionTitle
            title="Synthetic demonstration - not patient data"
            subtitle="The generated PDF carries the same watermark and must not be used for care or represented as a patient report."
            icon="flask-outline"
          />
        </Card>
      ) : null}
      <Card accent="teal">
        <SectionTitle title="What is included" icon="document-text-outline" />
        <Text style={[styles.body, { color: theme.text }]}>
          Consent status, session-snapshotted intake context, eight-region
          coverage, protected images when available, observation-map pins,
          user-confirmed comparisons, segmentation-derived descriptors,
          uncertainty, provenance, and model versions.
        </Text>
        <Text style={[styles.body, { color: theme.secondaryText }]}>
          The PDF repeats the non-diagnostic statement and labels every
          image-normalized measurement approximate.
        </Text>
      </Card>
      <Button
        label={latest ? "Regenerate report" : "Generate protected PDF"}
        icon="document-lock-outline"
        loading={busy}
        loadingLabel="Generating and protecting PDF..."
        disabled={busy || shareBusy}
        onPress={() => {
          void generate();
        }}
      />
      {latest ? (
        <Card>
          <SectionTitle
            title="Report ready"
            subtitle={`Generated ${new Date(latest.createdAt).toLocaleString()}`}
            icon="checkmark-circle-outline"
          />
          <Button
            label="Share a temporary decrypted copy"
            variant="secondary"
            icon="share-outline"
            loading={shareBusy}
            loadingLabel="Opening secure share sheet..."
            disabled={busy || shareBusy}
            onPress={() => {
              setShareBusy(true);
              setError(null);
              void shareEncryptedReport(latest)
                .catch((shareError: unknown) =>
                  setError(
                    shareError instanceof Error
                      ? shareError.message
                      : "Sharing failed.",
                  ),
                )
                .finally(() => setShareBusy(false));
            }}
          />
          <Text style={[styles.small, { color: theme.secondaryText }]}>
            The app decrypts a temporary copy only for the operating-system
            share sheet and deletes it afterward. No QR link or cloud portal is
            created.
          </Text>
        </Card>
      ) : null}
      {error ? (
        <Text
          accessibilityRole="alert"
          style={[styles.error, { color: theme.danger }]}
        >
          {error}
        </Text>
      ) : null}
    </Screen>
  );
}

const styles = StyleSheet.create({
  body: { fontSize: 13, lineHeight: 20 },
  small: { fontSize: 11, lineHeight: 17 },
  error: { textAlign: "center", fontSize: 13, fontWeight: "700" },
});
