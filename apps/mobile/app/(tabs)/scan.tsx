import { useMemo, useState } from "react";
import { router } from "expo-router";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import {
  MOUTH_REGION_DETAILS,
  type CaptureAngle,
  type MouthRegion,
} from "@oralsight/contracts";

import { OralObservationMap } from "@/components/OralObservationMap";
import { Screen } from "@/components/Screen";
import { Button, Card, EmptyState, SectionTitle } from "@/components/Ui";
import {
  acceptedAngles,
  acceptedRegions,
  detailedScanProgress,
  requiredAnglesForProtocol,
  scanProgress,
} from "@/lib/scanLogic";
import { useOralSightStore } from "@/store/useOralSightStore";
import { useAppTheme } from "@/theme";

export default function ScanRoute() {
  const theme = useAppTheme();
  const sessions = useOralSightStore((state) => state.sessions);
  const captures = useOralSightStore((state) => state.captures);
  const activeSessionId = useOralSightStore((state) => state.activeSessionId);
  const setActiveSession = useOralSightStore((state) => state.setActiveSession);
  const [selectedRegion, setSelectedRegion] = useState<MouthRegion | null>(
    null,
  );
  const session = sessions.find((item) => item.id === activeSessionId) ?? null;
  const progress = useMemo(
    () => (activeSessionId ? scanProgress(captures, activeSessionId) : null),
    [activeSessionId, captures],
  );
  const completed = useMemo(
    () => (activeSessionId ? acceptedRegions(captures, activeSessionId) : []),
    [activeSessionId, captures],
  );

  const detailProgress = useMemo(
    () =>
      activeSessionId
        ? detailedScanProgress(
            captures,
            activeSessionId,
            session?.protocol ?? "standard_eight_region",
          )
        : null,
    [activeSessionId, captures, session?.protocol],
  );
  const openCapture = (region: MouthRegion, angle?: CaptureAngle) => {
    setSelectedRegion(region);
    router.push({
      pathname: "/capture/[region]",
      params: { region, ...(angle ? { angle } : {}) },
    });
  };

  if (!session || !progress) {
    return (
      <Screen title="Structured mouth scan" eyebrow="Eight regions">
        <Card accent="teal">
          <EmptyState
            icon="scan-circle-outline"
            title="One accepted image per region"
            body="OralSight guides each capture, rejects unusable images, and marks the scan complete only at 8 of 8."
          />
          <Button
            label="Start a new scan"
            icon="camera-outline"
            onPress={() => router.push("/onboarding")}
          />
        </Card>
        {sessions.length > 0 ? (
          <SessionList
            sessions={sessions}
            captures={captures}
            activeSessionId={activeSessionId}
            onSelect={setActiveSession}
          />
        ) : null}
      </Screen>
    );
  }

  const protocolComplete =
    detailProgress !== null &&
    detailProgress.completedViews === detailProgress.totalViews;
  const selectedAcceptedAngles = selectedRegion
    ? acceptedAngles(captures, session.id, selectedRegion)
    : [];

  return (
    <Screen title="Structured mouth scan" eyebrow="Private session">
      <Card accent={protocolComplete ? "teal" : "amber"}>
        <View style={styles.progressHeading}>
          <View>
            <Text style={[styles.progressNumber, { color: theme.text }]}>
              {detailProgress?.completedViews ?? progress.completed} of{" "}
              {detailProgress?.totalViews ?? progress.total}
            </Text>
            <Text
              style={[styles.progressLabel, { color: theme.secondaryText }]}
            >
              {session.protocol === "standard_eight_region"
                ? "quality-accepted regions"
                : "quality-accepted views"}
            </Text>
          </View>
          <View
            style={[
              styles.progressBadge,
              {
                backgroundColor: protocolComplete
                  ? theme.mint
                  : theme.warningSurface,
              },
            ]}
          >
            <Ionicons
              name={protocolComplete ? "checkmark-circle" : "hourglass-outline"}
              color={protocolComplete ? theme.primary : theme.amber}
              size={25}
            />
          </View>
        </View>
        <View style={[styles.track, { backgroundColor: theme.line }]}>
          <View
            style={[
              styles.fill,
              {
                backgroundColor: theme.primary,
                width: `${((detailProgress?.completedViews ?? progress.completed) / (detailProgress?.totalViews ?? progress.total)) * 100}%`,
              },
            ]}
          />
        </View>
        <Text style={[styles.sessionLabel, { color: theme.secondaryText }]}>
          {session.label} · {protocolLabel(session.protocol)}
        </Text>
      </Card>

      <OralObservationMap
        completedRegions={completed}
        selectedRegion={selectedRegion}
        onSelectRegion={setSelectedRegion}
      />
      {selectedRegion ? (
        session.protocol === "detailed_multi_angle" ? (
          <Card accent="teal">
            <SectionTitle
              title={`Views for ${MOUTH_REGION_DETAILS.find((item) => item.id === selectedRegion)?.shortLabel ?? selectedRegion}`}
              subtitle="Capture each named angle. A check marks views already accepted."
              icon="layers-outline"
            />
            {requiredAnglesForProtocol(session.protocol).map((angle) => (
              <Button
                key={angle}
                label={`${selectedAcceptedAngles.includes(angle) ? "✓ " : ""}${angleLabel(angle)}`}
                icon="camera-outline"
                variant={
                  selectedAcceptedAngles.includes(angle)
                    ? "secondary"
                    : "primary"
                }
                onPress={() => openCapture(selectedRegion, angle)}
              />
            ))}
          </Card>
        ) : (
          <Button
            label={`${session.protocol === "guided_video_sweep" ? "Record guided sweep" : "Capture"} · ${MOUTH_REGION_DETAILS.find((item) => item.id === selectedRegion)?.shortLabel ?? selectedRegion}`}
            icon={
              session.protocol === "guided_video_sweep"
                ? "videocam-outline"
                : "camera-outline"
            }
            onPress={() => openCapture(selectedRegion)}
          />
        )
      ) : null}

      <Card>
        <SectionTitle
          title="Capture path"
          subtitle="Green check means quality accepted. On-device rejections never upload; service rejections are removed."
          icon="git-branch-outline"
        />
        <View style={styles.regionList}>
          {MOUTH_REGION_DETAILS.map((region, index) => {
            const acceptedForRegion = acceptedAngles(
              captures,
              session.id,
              region.id,
            );
            const requiredForRegion = requiredAnglesForProtocol(
              session.protocol,
            );
            const done = requiredForRegion.every((angle) =>
              acceptedForRegion.includes(angle),
            );
            return (
              <Pressable
                key={region.id}
                accessibilityRole="button"
                accessibilityLabel={`${region.label}. ${done ? "Accepted" : "Not captured"}`}
                onPress={() => {
                  setSelectedRegion(region.id);
                  if (session.protocol !== "detailed_multi_angle") {
                    openCapture(region.id);
                  }
                }}
                style={({ pressed }) => [
                  styles.regionRow,
                  { borderBottomColor: theme.border },
                  pressed && styles.regionRowPressed,
                ]}
              >
                <View
                  style={[
                    styles.step,
                    {
                      backgroundColor: done ? theme.primary : theme.background,
                      borderColor: done ? theme.primary : theme.border,
                    },
                  ]}
                >
                  {done ? (
                    <Ionicons name="checkmark" size={16} color="#FFFFFF" />
                  ) : (
                    <Text
                      style={{ color: theme.secondaryText, fontWeight: "800" }}
                    >
                      {index + 1}
                    </Text>
                  )}
                </View>
                <View style={styles.regionCopy}>
                  <Text style={[styles.regionTitle, { color: theme.text }]}>
                    {region.label}
                  </Text>
                  <Text
                    style={[
                      styles.regionInstruction,
                      { color: theme.secondaryText },
                    ]}
                  >
                    {region.captureInstruction}
                    {session.protocol === "standard_eight_region"
                      ? ""
                      : ` · ${acceptedForRegion.length} of ${requiredForRegion.length} views`}
                  </Text>
                </View>
                <Ionicons
                  name="chevron-forward"
                  color={theme.secondaryText}
                  size={19}
                />
              </Pressable>
            );
          })}
        </View>
      </Card>
      {protocolComplete ? (
        <Button
          label="Generate local clinician report"
          icon="document-text-outline"
          onPress={() => router.push("/report")}
        />
      ) : null}
      <Button
        label="Start another scan"
        icon="add-circle-outline"
        variant="ghost"
        onPress={() => router.push("/onboarding")}
      />
      {sessions.length > 1 ? (
        <SessionList
          sessions={sessions}
          captures={captures}
          activeSessionId={activeSessionId}
          onSelect={setActiveSession}
        />
      ) : null}
    </Screen>
  );
}

function protocolLabel(
  protocol: ReturnType<
    typeof useOralSightStore.getState
  >["sessions"][number]["protocol"],
): string {
  if (protocol === "detailed_multi_angle") return "Detailed photos";
  if (protocol === "guided_video_sweep") return "Guided sweeps";
  return "Standard photos";
}

function angleLabel(angle: CaptureAngle): string {
  if (angle === "straight") return "Straight view";
  if (angle === "left_oblique") return "Left view";
  if (angle === "right_oblique") return "Right view";
  if (angle === "superior") return "Upper view";
  if (angle === "inferior") return "Lower view";
  return "Primary view";
}

function SessionList({
  sessions,
  captures,
  activeSessionId,
  onSelect,
}: {
  sessions: ReturnType<typeof useOralSightStore.getState>["sessions"];
  captures: ReturnType<typeof useOralSightStore.getState>["captures"];
  activeSessionId: string | null;
  onSelect: (sessionId: string) => void;
}) {
  const theme = useAppTheme();
  const realSessions = sessions.filter((session) => !session.demo);
  if (realSessions.length === 0) return null;
  return (
    <Card>
      <SectionTitle
        title="Saved scan sessions"
        subtitle="Choose an earlier session to resume it or open its report."
        icon="folder-open-outline"
      />
      {realSessions
        .slice()
        .reverse()
        .map((item) => {
          const detail = detailedScanProgress(captures, item.id, item.protocol);
          const active = item.id === activeSessionId;
          return (
            <Pressable
              key={item.id}
              accessibilityRole="button"
              accessibilityState={{ selected: active }}
              accessibilityLabel={`${new Date(item.createdAt).toLocaleString()}, ${detail.completedViews} of ${detail.totalViews} accepted views${active ? ", active session" : ""}`}
              onPress={() => onSelect(item.id)}
              style={({ pressed }) => [
                styles.sessionRow,
                { borderColor: active ? theme.primary : theme.border },
                pressed && styles.sessionPressed,
              ]}
            >
              <View style={styles.sessionCopy}>
                <Text style={[styles.sessionTitle, { color: theme.text }]}>
                  {new Date(item.createdAt).toLocaleString()}
                </Text>
                <Text
                  style={[styles.sessionMeta, { color: theme.secondaryText }]}
                >
                  {protocolLabel(item.protocol)} · {detail.completedViews} of{" "}
                  {detail.totalViews} views
                  {detail.completedViews === detail.totalViews
                    ? " · report ready"
                    : ""}
                </Text>
              </View>
              <Ionicons
                name={active ? "checkmark-circle" : "chevron-forward"}
                color={active ? theme.primary : theme.secondaryText}
                size={21}
              />
            </Pressable>
          );
        })}
    </Card>
  );
}

const styles = StyleSheet.create({
  progressHeading: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  progressNumber: {
    fontSize: 27,
    fontWeight: "900",
    fontVariant: ["tabular-nums"],
  },
  progressLabel: { fontSize: 13 },
  progressBadge: {
    width: 48,
    height: 48,
    borderRadius: 16,
    alignItems: "center",
    justifyContent: "center",
  },
  track: { height: 10, borderRadius: 999, overflow: "hidden" },
  fill: { height: "100%", borderRadius: 999 },
  sessionLabel: { fontSize: 12, fontWeight: "700" },
  regionList: { gap: 0 },
  regionRow: {
    minHeight: 76,
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    borderBottomWidth: StyleSheet.hairlineWidth,
    paddingVertical: 10,
  },
  step: {
    width: 32,
    height: 32,
    borderRadius: 11,
    borderWidth: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  regionCopy: { flex: 1, gap: 3 },
  regionTitle: { fontSize: 14, fontWeight: "800" },
  regionInstruction: { fontSize: 11, lineHeight: 15 },
  regionRowPressed: { opacity: 0.8, transform: [{ scale: 0.99 }] },
  sessionRow: {
    minHeight: 60,
    borderWidth: 1,
    borderRadius: 14,
    paddingHorizontal: 14,
    paddingVertical: 10,
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  sessionPressed: { opacity: 0.82, transform: [{ scale: 0.99 }] },
  sessionCopy: { flex: 1, gap: 2 },
  sessionTitle: { fontSize: 14, fontWeight: "800" },
  sessionMeta: { fontSize: 12 },
});
