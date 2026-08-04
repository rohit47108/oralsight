import { router } from "expo-router";
import { StyleSheet, Text, View } from "react-native";

import { Screen } from "@/components/Screen";
import { Button, Card, SectionTitle } from "@/components/Ui";
import { useAppTheme } from "@/theme";

const roadmap = [
  [
    "NeuroSight",
    "A future multimodal neurological-pattern research module. No assessment is implemented in this release.",
  ],
  [
    "Personalized 3D reconstruction",
    "Research into multi-view mapping; the current oral observation map remains generic and region-based.",
  ],
  [
    "Clinician portal and annotations",
    "Future human-review workflows after privacy, consent, and governance design.",
  ],
  [
    "Expiring QR sharing",
    "Deferred. This release creates an encrypted local PDF and uses the operating system share sheet only on request.",
  ],
  [
    "Scan-summary video",
    "Deferred until the core capture, explanation, comparison, and report experience is validated.",
  ],
  [
    "Expanded capture and measurement",
    "Multi-angle capture, video sweeps, physical calibration references, and millimeter measurements are deferred beyond this one-image-per-region release.",
  ],
  [
    "Expanded scan guidance",
    "Automatic stability capture, mirrored directions, an animated virtual-phone scan path, and camera-pose scoring remain future usability research.",
  ],
  [
    "Expanded longitudinal views",
    "Time-lapse morphing, change animations, trajectory connections without passed comparison gates, and adaptive reminder scheduling are not active in this release.",
  ],
  [
    "Symptom body map",
    "An interactive head-and-neck symptom diagram is deferred. The current intake stores structured symptoms and includes them in the local report.",
  ],
  [
    "Education modules",
    "The oral anatomy atlas, normal-variation gallery, scan simulator, and knowledge challenges are deferred until licensed content can be clinically reviewed.",
  ],
  [
    "3D heatmap",
    "A surface heatmap is deferred. The current map shows only user-confirmed, versioned observation pins.",
  ],
] as const;

export default function RoadmapRoute() {
  const theme = useAppTheme();
  return (
    <Screen
      title="Research roadmap"
      eyebrow="Static, not implemented"
      action={
        <Button label="Back" variant="ghost" onPress={() => router.back()} />
      }
    >
      <Card accent="amber">
        <SectionTitle title="OralSight first" icon="flag-outline" />
        <Text style={[styles.body, { color: theme.text }]}>
          Future concepts are shown for transparency only. None are represented
          as working medical capabilities.
        </Text>
      </Card>
      {roadmap.map(([title, body]) => (
        <Card key={title}>
          <View style={styles.row}>
            <View style={[styles.number, { backgroundColor: theme.mint }]}>
              <Text style={{ color: theme.primary, fontWeight: "900" }}>R</Text>
            </View>
            <View style={styles.copy}>
              <Text style={[styles.title, { color: theme.text }]}>{title}</Text>
              <Text style={[styles.body, { color: theme.secondaryText }]}>
                {body}
              </Text>
            </View>
          </View>
        </Card>
      ))}
    </Screen>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", gap: 13 },
  number: {
    width: 38,
    height: 38,
    borderRadius: 13,
    alignItems: "center",
    justifyContent: "center",
  },
  copy: { flex: 1, gap: 4 },
  title: { fontSize: 16, fontWeight: "800" },
  body: { fontSize: 13, lineHeight: 20 },
});
