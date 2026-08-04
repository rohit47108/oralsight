import { useState } from "react";
import { Alert, StyleSheet, Text } from "react-native";
import { router } from "expo-router";

import { Screen } from "@/components/Screen";
import { Button, Card, SectionTitle, ToggleRow } from "@/components/Ui";
import { bundledGuidanceStatus } from "@/lib/guidanceRules";
import { useOralSightStore } from "@/store/useOralSightStore";
import { useAppTheme } from "@/theme";
import { CONTRACT_VERSION } from "@oralsight/contracts";

export default function SettingsRoute() {
  const theme = useAppTheme();
  const settings = useOralSightStore((state) => state.settings);
  const updateSettings = useOralSightStore((state) => state.updateSettings);
  const deleteEverything = useOralSightStore((state) => state.deleteEverything);
  const [deleting, setDeleting] = useState(false);
  const guidance = bundledGuidanceStatus();

  const confirmDeletion = () =>
    Alert.alert(
      "Delete all OralSight data?",
      "This removes the encrypted database, captures, reports, comparisons, and consent record, then rotates installation keys. This cannot be undone.",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete all",
          style: "destructive",
          onPress: () => {
            setDeleting(true);
            void deleteEverything()
              .then(() => router.replace("/onboarding"))
              .catch(() => {
                setDeleting(false);
                Alert.alert(
                  "Deletion incomplete",
                  "OralSight could not verify that every local file and key was removed. Your data has not been reported as deleted. Try again before sharing or uninstalling the app.",
                );
              });
          },
        },
      ],
    );

  return (
    <Screen title="Settings & safety" eyebrow="Private local controls">
      <Card>
        <SectionTitle
          title="Accessibility"
          subtitle="OralSight also follows your device text-size and appearance settings."
          icon="accessibility-outline"
        />
        <ToggleRow
          label="High contrast"
          value={settings.highContrast}
          onValueChange={(value) => updateSettings({ highContrast: value })}
        />
        <ToggleRow
          label="Larger key text"
          description="Adds extra size to shared headings, buttons, choices, and settings."
          value={settings.largeText}
          onValueChange={(value) => updateSettings({ largeText: value })}
        />
        <ToggleRow
          label="Reduce motion"
          value={settings.reducedMotion}
          onValueChange={(value) => updateSettings({ reducedMotion: value })}
        />
        <ToggleRow
          label="Haptic capture cues"
          value={settings.haptics}
          onValueChange={(value) => updateSettings({ haptics: value })}
        />
        <ToggleRow
          label="Read capture instructions"
          value={settings.voiceInstructions}
          onValueChange={(value) =>
            updateSettings({ voiceInstructions: value })
          }
        />
        <ToggleRow
          label="Caregiver-assisted mode"
          value={settings.caregiverMode}
          onValueChange={(value) => updateSettings({ caregiverMode: value })}
        />
      </Card>
      <Card accent="amber">
        <SectionTitle
          title="Review guidance is disabled"
          icon="alert-circle-outline"
        />
        <Text style={[styles.body, { color: theme.text }]}>
          {guidance.statusMessage}
        </Text>
        <Text style={[styles.body, { color: theme.secondaryText }]}>
          {guidance.message}
        </Text>
      </Card>
      <Card>
        <SectionTitle title="Transparency" icon="layers-outline" />
        <Button
          label="Open deployed model card"
          variant="secondary"
          icon="document-outline"
          onPress={() => router.push("/model-card")}
        />
        <Button
          label="View future roadmap"
          variant="ghost"
          icon="map-outline"
          onPress={() => router.push("/roadmap")}
        />
      </Card>
      <Card accent="coral">
        <SectionTitle
          title="Delete local data"
          subtitle="Deletes protected files and database, clears reports, and rotates both encryption keys."
          icon="trash-outline"
        />
        <Button
          label="Delete everything"
          variant="danger"
          icon="trash"
          loading={deleting}
          onPress={confirmDeletion}
        />
      </Card>
      <Text style={[styles.version, { color: theme.secondaryText }]}>
        OralSight research app · contract {CONTRACT_VERSION} · no accounts or
        analytics
      </Text>
    </Screen>
  );
}

const styles = StyleSheet.create({
  body: { fontSize: 13, lineHeight: 20 },
  version: { fontSize: 11, textAlign: "center" },
});
