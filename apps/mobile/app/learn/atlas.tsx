import { useState } from "react";
import { router } from "expo-router";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import type { MouthRegion } from "@oralsight/contracts";

import { Screen } from "@/components/Screen";
import { Button, Card, SectionTitle } from "@/components/Ui";
import { ANATOMY_LESSONS } from "@/lib/education";
import { useAppTheme } from "@/theme";

export default function AnatomyAtlasRoute() {
  const theme = useAppTheme();
  const [selected, setSelected] = useState<MouthRegion>("dorsal_tongue");
  const lesson = ANATOMY_LESSONS.find((item) => item.region === selected)!;

  return (
    <Screen
      title="Oral anatomy atlas"
      eyebrow="Eight-region guide"
      action={
        <Button label="Back" variant="ghost" onPress={() => router.back()} />
      }
    >
      <View
        accessibilityRole="radiogroup"
        style={[styles.regionGrid, { borderColor: theme.border }]}
      >
        {ANATOMY_LESSONS.map((item, index) => {
          const active = item.region === selected;
          return (
            <Pressable
              key={item.region}
              accessibilityRole="radio"
              accessibilityLabel={`${index + 1}. ${item.name}`}
              accessibilityState={{ checked: active }}
              onPress={() => setSelected(item.region)}
              style={({ pressed }) => [
                styles.region,
                {
                  backgroundColor: active ? theme.primary : theme.surface,
                  borderColor: active ? theme.primary : theme.border,
                },
                pressed && styles.pressed,
              ]}
            >
              <Text
                style={[
                  styles.regionNumber,
                  { color: active ? theme.white : theme.primary },
                ]}
              >
                {index + 1}
              </Text>
              <Text
                style={[
                  styles.regionLabel,
                  { color: active ? theme.white : theme.text },
                ]}
              >
                {item.shortName}
              </Text>
            </Pressable>
          );
        })}
      </View>

      <Card accent="teal">
        <SectionTitle title={lesson.name} icon="locate-outline" />
        <Text style={[styles.lead, { color: theme.text }]}>
          {lesson.purpose}
        </Text>
        <View style={[styles.rule, { backgroundColor: theme.border }]} />
        <Text style={[styles.kicker, { color: theme.primary }]}>
          How to frame it
        </Text>
        <Text style={[styles.body, { color: theme.text }]}>
          {lesson.captureInstruction}
        </Text>
        <Text style={[styles.kicker, { color: theme.primary }]}>
          Useful context
        </Text>
        <Text style={[styles.body, { color: theme.text }]}>
          {lesson.observationPrompt}
        </Text>
      </Card>

      <Card accent="amber">
        <View style={styles.noteHeading}>
          <Ionicons
            name="information-circle-outline"
            size={21}
            color={theme.amber}
          />
          <Text style={[styles.noteTitle, { color: theme.text }]}>
            Normal appearance varies
          </Text>
        </View>
        <Text style={[styles.body, { color: theme.secondaryText }]}>
          Symmetry, color, surface texture, veins, and small folds can differ
          between people and across regions. This atlas helps name and
          photograph a location. Do not use it to decide that a visible area is
          harmless.
        </Text>
      </Card>
    </Screen>
  );
}

const styles = StyleSheet.create({
  regionGrid: {
    borderTopWidth: 1,
    borderLeftWidth: 1,
    flexDirection: "row",
    flexWrap: "wrap",
  },
  region: {
    width: "50%",
    minHeight: 72,
    borderRightWidth: 1,
    borderBottomWidth: 1,
    padding: 12,
    gap: 5,
  },
  regionNumber: { fontSize: 11, fontWeight: "900" },
  regionLabel: { fontSize: 13, fontWeight: "800", lineHeight: 17 },
  pressed: { opacity: 0.82 },
  lead: { fontSize: 16, lineHeight: 23, fontWeight: "600" },
  rule: { height: StyleSheet.hairlineWidth },
  kicker: {
    fontSize: 11,
    fontWeight: "900",
    letterSpacing: 0.5,
    textTransform: "uppercase",
  },
  body: { fontSize: 14, lineHeight: 21 },
  noteHeading: { flexDirection: "row", alignItems: "center", gap: 8 },
  noteTitle: { fontSize: 16, fontWeight: "800" },
});
