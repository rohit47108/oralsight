import { useMemo, useState } from "react";
import { router } from "expo-router";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { MOUTH_REGION_DETAILS, type MouthRegion } from "@oralsight/contracts";

import { OralObservationMap } from "@/components/OralObservationMap";
import { Screen } from "@/components/Screen";
import { Button, Card, EmptyState, SectionTitle } from "@/components/Ui";
import { scanProgress, acceptedRegions } from "@/lib/scanLogic";
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

  const openCapture = (region: MouthRegion) => {
    setSelectedRegion(region);
    router.push({ pathname: "/capture/[region]", params: { region } });
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

  return (
    <Screen title="Structured mouth scan" eyebrow="Private session">
      <Card accent={progress.completed === 8 ? "teal" : "amber"}>
        <View style={styles.progressHeading}>
          <View>
            <Text style={[styles.progressNumber, { color: theme.text }]}>
              {progress.completed} of {progress.total}
            </Text>
            <Text
              style={[styles.progressLabel, { color: theme.secondaryText }]}
            >
              quality-accepted regions
            </Text>
          </View>
          <View
            style={[
              styles.progressBadge,
              {
                backgroundColor:
                  progress.completed === 8 ? theme.mint : theme.warningSurface,
              },
            ]}
          >
            <Ionicons
              name={
                progress.completed === 8
                  ? "checkmark-circle"
                  : "hourglass-outline"
              }
              color={progress.completed === 8 ? theme.primary : theme.amber}
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
                width: `${progress.percent * 100}%`,
              },
            ]}
          />
        </View>
        <Text style={[styles.sessionLabel, { color: theme.secondaryText }]}>
          {session.label}
        </Text>
      </Card>

      <OralObservationMap
        completedRegions={completed}
        selectedRegion={selectedRegion}
        onSelectRegion={setSelectedRegion}
      />
      {selectedRegion ? (
        <Button
          label={`Capture ${MOUTH_REGION_DETAILS.find((item) => item.id === selectedRegion)?.shortLabel ?? selectedRegion}`}
          icon="camera-outline"
          onPress={() => openCapture(selectedRegion)}
        />
      ) : null}

      <Card>
        <SectionTitle
          title="Capture path"
          subtitle="Green check means quality accepted. On-device rejections never upload; service rejections are removed."
          icon="git-branch-outline"
        />
        <View style={styles.regionList}>
          {MOUTH_REGION_DETAILS.map((region, index) => {
            const done = completed.includes(region.id);
            return (
              <Pressable
                key={region.id}
                accessibilityRole="button"
                accessibilityLabel={`${region.label}. ${done ? "Accepted" : "Not captured"}`}
                onPress={() => openCapture(region.id)}
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
      {progress.completed === 8 ? (
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
          const progress = scanProgress(captures, item.id);
          const active = item.id === activeSessionId;
          return (
            <Pressable
              key={item.id}
              accessibilityRole="button"
              accessibilityState={{ selected: active }}
              accessibilityLabel={`${new Date(item.createdAt).toLocaleString()}, ${progress.completed} of 8 regions${active ? ", active session" : ""}`}
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
                  {progress.completed} of 8 regions
                  {progress.completed === 8 ? " - report ready" : ""}
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
