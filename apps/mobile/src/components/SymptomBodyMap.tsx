import { Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { useAppTheme } from "@/theme";

const POINTS = [
  { value: "ear pain", label: "Ear", top: 82, left: 11 },
  { value: "jaw pain", label: "Jaw", top: 132, left: 18 },
  { value: "pain", label: "Mouth", top: 112, left: 52 },
  { value: "numbness", label: "Numb", top: 112, left: 73 },
  { value: "difficulty swallowing", label: "Swallow", top: 178, left: 30 },
  { value: "neck lump", label: "Neck", top: 206, left: 65 },
] as const;

interface SymptomBodyMapProps {
  selected: readonly string[];
  onToggle: (value: string) => void;
}

export function SymptomBodyMap({ selected, onToggle }: SymptomBodyMapProps) {
  const theme = useAppTheme();
  return (
    <View
      accessible={false}
      style={[
        styles.shell,
        { backgroundColor: theme.background, borderColor: theme.border },
      ]}
    >
      <View
        pointerEvents="none"
        style={[styles.head, { borderColor: theme.border }]}
      >
        <View
          style={[styles.ear, styles.leftEar, { borderColor: theme.border }]}
        />
        <View
          style={[styles.ear, styles.rightEar, { borderColor: theme.border }]}
        />
        <View style={[styles.faceLine, { backgroundColor: theme.border }]} />
        <View style={[styles.mouthLine, { backgroundColor: theme.primary }]} />
      </View>
      <View
        pointerEvents="none"
        style={[styles.neck, { borderColor: theme.border }]}
      />
      {POINTS.map((point) => {
        const active = selected.includes(point.value);
        return (
          <Pressable
            key={point.value}
            accessibilityRole="checkbox"
            accessibilityLabel={point.value}
            accessibilityState={{ checked: active }}
            onPress={() => onToggle(point.value)}
            style={({ pressed }) => [
              styles.point,
              { top: point.top, left: `${point.left}%` },
              {
                backgroundColor: active ? theme.primary : theme.surface,
                borderColor: active ? theme.primary : theme.border,
              },
              pressed && styles.pressed,
            ]}
          >
            <Ionicons
              name={active ? "checkmark" : "add"}
              color={active ? theme.white : theme.primary}
              size={15}
            />
            <Text
              style={[
                styles.pointLabel,
                { color: active ? theme.white : theme.text },
              ]}
            >
              {point.label}
            </Text>
          </Pressable>
        );
      })}
      <Text style={[styles.hint, { color: theme.secondaryText }]}>
        Tap every place that applies. The selections are report context only.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  shell: {
    minHeight: 300,
    overflow: "hidden",
    borderWidth: 1,
    borderRadius: 18,
    position: "relative",
    paddingBottom: 40,
  },
  head: {
    position: "absolute",
    top: 22,
    left: "37%",
    width: "26%",
    height: 142,
    borderWidth: 2,
    borderRadius: 56,
  },
  ear: {
    position: "absolute",
    top: 48,
    width: 12,
    height: 30,
    borderWidth: 2,
    borderRadius: 9,
  },
  leftEar: { left: -10 },
  rightEar: { right: -10 },
  faceLine: {
    position: "absolute",
    top: 78,
    left: "28%",
    right: "28%",
    height: 1,
  },
  mouthLine: {
    position: "absolute",
    top: 108,
    left: "31%",
    right: "31%",
    height: 3,
    borderRadius: 2,
  },
  neck: {
    position: "absolute",
    top: 150,
    left: "42%",
    width: "16%",
    height: 96,
    borderLeftWidth: 2,
    borderRightWidth: 2,
    borderBottomWidth: 2,
    borderBottomLeftRadius: 26,
    borderBottomRightRadius: 26,
  },
  point: {
    position: "absolute",
    minWidth: 76,
    minHeight: 48,
    paddingHorizontal: 9,
    borderWidth: 1,
    borderRadius: 13,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 4,
  },
  pointLabel: { fontSize: 11, fontWeight: "800" },
  pressed: { opacity: 0.82, transform: [{ scale: 0.98 }] },
  hint: {
    position: "absolute",
    bottom: 11,
    left: 14,
    right: 14,
    textAlign: "center",
    fontSize: 11,
    lineHeight: 15,
  },
});
