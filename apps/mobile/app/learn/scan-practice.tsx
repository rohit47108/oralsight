import { useMemo, useState } from "react";
import { router } from "expo-router";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { Screen } from "@/components/Screen";
import { Button, Card, SectionTitle } from "@/components/Ui";
import { QUALITY_PRACTICE_SCENARIOS } from "@/lib/education";
import { useAppTheme } from "@/theme";

export default function ScanPracticeRoute() {
  const theme = useAppTheme();
  const [index, setIndex] = useState(0);
  const [answer, setAnswer] = useState<string | null>(null);
  const scenario =
    QUALITY_PRACTICE_SCENARIOS[index] ?? QUALITY_PRACTICE_SCENARIOS[0]!;
  const correct = answer === scenario.correctChoice;
  const cameraLines = useMemo(
    () => Array.from({ length: 7 }, (_, line) => line),
    [],
  );

  const next = () => {
    setAnswer(null);
    setIndex((value) => (value + 1) % QUALITY_PRACTICE_SCENARIOS.length);
  };

  return (
    <Screen
      title="Capture practice"
      eyebrow={`${index + 1} of ${QUALITY_PRACTICE_SCENARIOS.length}`}
      action={
        <Button label="Back" variant="ghost" onPress={() => router.back()} />
      }
    >
      <View
        accessible
        accessibilityLabel={`Practice camera illustration: ${scenario.title}`}
        style={[
          styles.preview,
          {
            backgroundColor:
              scenario.visual === "dark" ? theme.navy : theme.mint,
            borderColor: theme.border,
            opacity: scenario.visual === "blur" ? 0.72 : 1,
          },
        ]}
      >
        {cameraLines.map((line) => (
          <View
            key={line}
            style={[
              styles.contour,
              {
                width: `${82 - line * 8}%`,
                height: 22 + line * 11,
                borderColor: theme.primary,
              },
            ]}
          />
        ))}
        {scenario.visual === "glare" ? <View style={styles.glare} /> : null}
        {scenario.visual === "obstruction" ? (
          <View style={[styles.obstruction, { backgroundColor: theme.navy }]} />
        ) : null}
        <View style={[styles.focusCorner, styles.topLeft]} />
        <View style={[styles.focusCorner, styles.topRight]} />
        <View style={[styles.focusCorner, styles.bottomLeft]} />
        <View style={[styles.focusCorner, styles.bottomRight]} />
      </View>

      <Card>
        <SectionTitle
          title={scenario.title}
          subtitle={scenario.prompt}
          icon="scan-outline"
        />
        <View accessibilityRole="radiogroup" style={styles.choices}>
          {scenario.choices.map((choice) => {
            const selected = answer === choice;
            return (
              <Pressable
                key={choice}
                accessibilityRole="radio"
                accessibilityState={{
                  checked: selected,
                  disabled: answer !== null,
                }}
                disabled={answer !== null}
                onPress={() => setAnswer(choice)}
                style={({ pressed }) => [
                  styles.choice,
                  {
                    borderColor: selected ? theme.primary : theme.border,
                    backgroundColor: selected ? theme.mint : theme.surface,
                  },
                  pressed && styles.pressed,
                ]}
              >
                <Text style={[styles.choiceText, { color: theme.text }]}>
                  {choice}
                </Text>
              </Pressable>
            );
          })}
        </View>
      </Card>

      {answer ? (
        <Card accent={correct ? "teal" : "amber"}>
          <View style={styles.feedbackHeading}>
            <Ionicons
              name={correct ? "checkmark-circle" : "refresh-circle"}
              color={correct ? theme.primary : theme.amber}
              size={23}
            />
            <Text style={[styles.feedbackTitle, { color: theme.text }]}>
              {correct
                ? "That is the useful next step"
                : "Try the safer correction"}
            </Text>
          </View>
          <Text style={[styles.feedbackBody, { color: theme.secondaryText }]}>
            {scenario.correction}
          </Text>
          <Button label="Next example" onPress={next} />
        </Card>
      ) : null}
    </Screen>
  );
}

const styles = StyleSheet.create({
  preview: {
    height: 270,
    borderWidth: 1,
    borderRadius: 22,
    overflow: "hidden",
    alignItems: "center",
    justifyContent: "center",
  },
  contour: {
    position: "absolute",
    borderWidth: 2,
    borderRadius: 999,
    opacity: 0.65,
  },
  glare: {
    position: "absolute",
    top: 46,
    right: 54,
    width: 92,
    height: 92,
    borderRadius: 46,
    backgroundColor: "#FFFFFF",
    opacity: 0.92,
  },
  obstruction: {
    position: "absolute",
    bottom: -26,
    left: -16,
    width: 144,
    height: 132,
    borderTopRightRadius: 70,
    opacity: 0.88,
  },
  focusCorner: {
    position: "absolute",
    width: 28,
    height: 28,
    borderColor: "#FFFFFF",
  },
  topLeft: { top: 34, left: 34, borderTopWidth: 3, borderLeftWidth: 3 },
  topRight: { top: 34, right: 34, borderTopWidth: 3, borderRightWidth: 3 },
  bottomLeft: {
    bottom: 34,
    left: 34,
    borderBottomWidth: 3,
    borderLeftWidth: 3,
  },
  bottomRight: {
    bottom: 34,
    right: 34,
    borderBottomWidth: 3,
    borderRightWidth: 3,
  },
  choices: { gap: 9 },
  choice: {
    minHeight: 50,
    borderWidth: 1,
    borderRadius: 14,
    padding: 14,
    justifyContent: "center",
  },
  choiceText: { fontSize: 14, lineHeight: 20, fontWeight: "700" },
  pressed: { opacity: 0.82, transform: [{ scale: 0.99 }] },
  feedbackHeading: { flexDirection: "row", alignItems: "center", gap: 8 },
  feedbackTitle: { flex: 1, fontSize: 16, lineHeight: 21, fontWeight: "800" },
  feedbackBody: { fontSize: 14, lineHeight: 21 },
});
