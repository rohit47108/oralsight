import { useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { router } from "expo-router";

import {
  shareGeneratedArtifact,
  shareReportArtifact,
} from "@/cloud/artifactDownload";
import { shareDataExportArtifact } from "@/cloud/exportCrypto";
import { shareableCloudResources } from "@/cloud/productSync";
import { useCloudStore } from "@/cloud/useCloudStore";
import { Screen } from "@/components/Screen";
import { Button, Card, ChoiceChip, SectionTitle } from "@/components/Ui";
import { useOralSightStore } from "@/store/useOralSightStore";
import { useAppTheme } from "@/theme";

function jobLabel(type: string): string {
  const labels: Record<string, string> = {
    analysis: "Image analysis",
    comparison: "Observation comparison",
    reconstruction: "Observation surface",
    report: "Clinician PDF",
    summary_video: "Scan summary video",
    data_export: "Account export",
    account_deletion: "Account deletion",
    delete_all: "Delete all data",
  };
  return labels[type] ?? type.replaceAll("_", " ");
}

export default function JobsRoute() {
  const theme = useAppTheme();
  const cloud = useCloudStore();
  const sessions = useOralSightStore((state) => state.sessions);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [syncedSessionIds, setSyncedSessionIds] = useState<string[]>([]);

  useEffect(() => {
    void shareableCloudResources().then((resources) => {
      const ids = resources
        .filter((resource) => resource.resourceType === "scan_session")
        .map((resource) => resource.localId);
      setSyncedSessionIds(ids);
      setSessionId((current) => current ?? ids.at(-1) ?? null);
    });
    void cloud.refreshAccountData();
  }, []);

  useEffect(() => {
    const running = cloud.jobs.filter(
      (job) => job.status === "queued" || job.status === "running",
    );
    if (running.length === 0) return;
    const timer = setInterval(() => {
      for (const job of running) void cloud.refreshJob(job.jobId);
    }, 5_000);
    return () => clearInterval(timer);
  }, [cloud.jobs]);

  const start = (
    type: "reconstruction" | "report" | "summary_video" | "data_export",
  ) => {
    if (type !== "data_export" && !sessionId) return;
    void cloud.startJob(type, sessionId).catch(() => undefined);
  };

  return (
    <Screen
      title="Processing jobs"
      eyebrow="Durable work with visible status"
      action={
        <Button label="Back" variant="ghost" onPress={() => router.back()} />
      }
    >
      <Card>
        <SectionTitle
          title="Create a file or surface"
          subtitle="Choose a synced scan. Jobs continue if you close the app, and their status remains visible here."
          icon="construct-outline"
        />
        <View style={styles.chips}>
          {sessions
            .filter((session) => syncedSessionIds.includes(session.id))
            .map((session) => (
              <ChoiceChip
                key={session.id}
                label={session.label}
                selected={sessionId === session.id}
                onPress={() => setSessionId(session.id)}
              />
            ))}
        </View>
        {syncedSessionIds.length === 0 ? (
          <Text style={[styles.body, { color: theme.secondaryText }]}>
            Sync a scan before starting scan-based processing.
          </Text>
        ) : null}
        <Button
          label="Build observation surface"
          variant="secondary"
          icon="cube-outline"
          disabled={!sessionId || cloud.busy}
          onPress={() => start("reconstruction")}
        />
        <Button
          label="Create clinician PDF"
          variant="secondary"
          icon="document-text-outline"
          disabled={!sessionId || cloud.busy}
          onPress={() => start("report")}
        />
        <Button
          label="Create captioned summary video"
          variant="secondary"
          icon="videocam-outline"
          disabled={!sessionId || cloud.busy}
          onPress={() => start("summary_video")}
        />
        <Button
          label="Prepare encrypted account export"
          variant="ghost"
          icon="archive-outline"
          disabled={cloud.busy}
          onPress={() => start("data_export")}
        />
      </Card>

      {cloud.jobs.length === 0 ? (
        <Card>
          <Text style={[styles.body, { color: theme.secondaryText }]}>
            No cloud jobs yet.
          </Text>
        </Card>
      ) : (
        cloud.jobs.map((job) => (
          <Card
            key={job.jobId}
            accent={job.status === "failed" ? "amber" : undefined}
          >
            <View style={styles.heading}>
              <View style={styles.copy}>
                <Text style={[styles.title, { color: theme.text }]}>
                  {jobLabel(job.type)}
                </Text>
                <Text style={[styles.meta, { color: theme.secondaryText }]}>
                  {job.status.replaceAll("_", " ")} · attempt {job.attempt}/
                  {job.maxAttempts}
                </Text>
              </View>
              <Text style={[styles.progress, { color: theme.primary }]}>
                {Math.round(job.progress * 100)}%
              </Text>
            </View>
            {job.errorMessage ? (
              <Text style={[styles.body, { color: theme.danger }]}>
                {job.errorMessage}
              </Text>
            ) : null}
            {job.reasonCode && !job.errorMessage ? (
              <Text style={[styles.body, { color: theme.secondaryText }]}>
                Result: {job.reasonCode.replaceAll("_", " ")}
              </Text>
            ) : null}
            {job.status === "queued" || job.status === "running" ? (
              <>
                <Button
                  label="Refresh status"
                  variant="ghost"
                  onPress={() => void cloud.refreshJob(job.jobId)}
                />
                <Button
                  label="Cancel job"
                  variant="danger"
                  onPress={() => void cloud.cancelJob(job.jobId)}
                />
              </>
            ) : null}
            {([
              "reconstruction",
              "summary_video",
              "report",
              "data_export",
            ].includes(job.type)
              ? job.outputRefs
              : []
            ).map((artifactId) => {
              const artifact = cloud.artifacts[artifactId];
              const report = cloud.reportArtifacts[artifactId];
              const dataExport = cloud.dataExports[artifactId];
              return artifact ? (
                <Button
                  key={artifactId}
                  label={`Open ${artifact.filename}`}
                  variant="secondary"
                  icon="share-outline"
                  onPress={() =>
                    void shareGeneratedArtifact(artifact).catch(() => undefined)
                  }
                />
              ) : report ? (
                <Button
                  key={artifactId}
                  label="Open clinician PDF"
                  variant="secondary"
                  icon="document-text-outline"
                  onPress={() =>
                    void shareReportArtifact(report).catch(() => undefined)
                  }
                />
              ) : dataExport ? (
                <Button
                  key={artifactId}
                  label="Open account export"
                  variant="secondary"
                  icon="archive-outline"
                  onPress={() =>
                    void shareDataExportArtifact(dataExport).catch(
                      () => undefined,
                    )
                  }
                />
              ) : (
                <Button
                  key={artifactId}
                  label="Load result file"
                  variant="secondary"
                  icon="download-outline"
                  onPress={() => void cloud.loadJobOutput(job.type, artifactId)}
                />
              );
            })}
          </Card>
        ))
      )}
      {cloud.error ? (
        <Text
          accessibilityRole="alert"
          style={[styles.error, { color: theme.danger }]}
        >
          {cloud.error}
        </Text>
      ) : null}
    </Screen>
  );
}

const styles = StyleSheet.create({
  heading: {
    flexDirection: "row",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: 12,
  },
  copy: { flex: 1, gap: 3 },
  title: { fontSize: 16, fontWeight: "800" },
  meta: { fontSize: 12, lineHeight: 18 },
  progress: { fontSize: 18, fontWeight: "900", fontVariant: ["tabular-nums"] },
  body: { fontSize: 14, lineHeight: 21 },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  error: { fontSize: 13, lineHeight: 20, fontWeight: "700" },
});
