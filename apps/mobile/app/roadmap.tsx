import { router } from "expo-router";
import { StyleSheet, Text, View } from "react-native";

import { Screen } from "@/components/Screen";
import { Button, Card, SectionTitle } from "@/components/Ui";
import { useAppTheme } from "@/theme";

const roadmap = [
  [
    "Independent clinical study",
    "Prospective evaluation with external clinicians, representative participants, locked models, and published methods. Engineering tests cannot substitute for this evidence.",
  ],
  [
    "Regulated clinical claims",
    "Any future diagnostic or clinical-accuracy claim would require the evidence, quality system, legal review, and regulatory path appropriate to its intended use.",
  ],
  [
    "Deformable anatomical reconstruction",
    "OralSight can build a personalized multi-view observation surface for coverage and location. Reconstructing a true patient-specific, deformable mouth anatomy remains a research problem.",
  ],
  [
    "Expanded model releases",
    "Appearance, disease-category, and automated re-identification heads stay behind their published evidence gates until suitable patient-disjoint data and clinical review exist.",
  ],
  [
    "Language packs and reviewed education",
    "Additional written languages and larger licensed education libraries can be added after native-speaker and clinician review.",
  ],
] as const;

export default function RoadmapRoute() {
  const theme = useAppTheme();
  return (
    <Screen
      title="Research roadmap"
      eyebrow="Beyond the OralSight product"
      action={
        <Button label="Back" variant="ghost" onPress={() => router.back()} />
      }
    >
      <Card accent="amber">
        <SectionTitle title="What remains research" icon="flag-outline" />
        <Text style={[styles.body, { color: theme.text }]}>
          Capture, comparison, reporting, sharing, clinician review, the
          observation map, and the education tools belong to OralSight. The
          items below require work outside that product build or evidence that
          cannot be created in software alone.
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
