import { useMemo, useState } from "react";
import { router } from "expo-router";
import { StyleSheet, Text } from "react-native";
import { MOUTH_REGION_DETAILS, type MouthRegion } from "@oralsight/contracts";

import { OralObservationMap } from "@/components/OralObservationMap";
import { Screen } from "@/components/Screen";
import { Button, Card, SectionTitle } from "@/components/Ui";
import { acceptedRegions } from "@/lib/scanLogic";
import { useOralSightStore } from "@/store/useOralSightStore";
import { useAppTheme } from "@/theme";

export default function MapRoute() {
  const theme = useAppTheme();
  const captures = useOralSightStore((state) => state.captures);
  const pins = useOralSightStore((state) => state.pins);
  const activeSessionId = useOralSightStore((state) => state.activeSessionId);
  const [selected, setSelected] = useState<MouthRegion | null>(null);
  const completed = useMemo(
    () => (activeSessionId ? acceptedRegions(captures, activeSessionId) : []),
    [activeSessionId, captures],
  );
  const detail = MOUTH_REGION_DETAILS.find((region) => region.id === selected);
  const regionPins = pins.filter((pin) => pin.region === selected);

  return (
    <Screen title="Oral observation map" eyebrow="Named oral regions">
      <Text style={[styles.intro, { color: theme.secondaryText }]}>
        Rotate, zoom, explode layers, fade the dental arches, and select a named
        region. This generic map is not a personalized digital twin.
      </Text>
      <OralObservationMap
        completedRegions={completed}
        selectedRegion={selected}
        onSelectRegion={setSelected}
        pins={pins}
        showRegionList
      />
      <Card accent={regionPins.length ? "amber" : "teal"}>
        <SectionTitle
          title={detail?.label ?? "Select a region"}
          subtitle={
            detail?.captureInstruction ??
            "Use the model or scan list to inspect a named anatomical region."
          }
          icon="location-outline"
        />
        {detail ? (
          <Text style={[styles.meta, { color: theme.secondaryText }]}>
            {completed.includes(detail.id)
              ? "Captured in active session"
              : "Not captured in active session"}{" "}
            - {regionPins.length} observation pin
            {regionPins.length === 1 ? "" : "s"}
          </Text>
        ) : null}
        {regionPins.map((pin) => (
          <Text
            key={pin.id}
            style={[styles.pin, { color: theme.secondaryText }]}
          >
            {pin.status.replaceAll("_", " ")} - {pin.captureIds.length} linked
            observation{pin.captureIds.length === 1 ? "" : "s"}
          </Text>
        ))}
        {detail && activeSessionId ? (
          <Button
            label="Capture this region"
            icon="camera-outline"
            variant="secondary"
            onPress={() =>
              router.push({
                pathname: "/capture/[region]",
                params: { region: detail.id },
              })
            }
          />
        ) : null}
        {detail && !activeSessionId ? (
          <Button
            label="Start a structured scan"
            icon="scan-outline"
            variant="secondary"
            onPress={() => router.push("/(tabs)/scan")}
          />
        ) : null}
        {regionPins.length ? (
          <Button
            label="Open visual timeline"
            icon="analytics-outline"
            variant="ghost"
            onPress={() => router.push("/(tabs)/timeline")}
          />
        ) : null}
      </Card>
    </Screen>
  );
}

const styles = StyleSheet.create({
  intro: { fontSize: 13, lineHeight: 20 },
  meta: { fontSize: 13, fontWeight: "700" },
  pin: { fontSize: 12, lineHeight: 18, textTransform: "capitalize" },
});
