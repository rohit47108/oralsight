import { StyleSheet, Text, View } from "react-native";
import { type Href, router } from "expo-router";

import { Screen } from "@/components/Screen";
import { Button, Card, SectionTitle } from "@/components/Ui";
import { useCloudStore } from "@/cloud/useCloudStore";
import { useAppTheme } from "@/theme";

function when(value: string | null): string {
  return value ? new Date(value).toLocaleString() : "Not yet synced";
}

export default function CloudSyncRoute() {
  const theme = useAppTheme();
  const cloud = useCloudStore();
  return (
    <Screen
      title="Sync and backup"
      eyebrow="Encrypted, resumable, optional"
      action={
        <Button label="Back" variant="ghost" onPress={() => router.back()} />
      }
    >
      <Card
        accent={!cloud.productConsent || cloud.syncError ? "amber" : "teal"}
      >
        <SectionTitle
          title={
            !cloud.productConsent
              ? "Cloud consent required"
              : cloud.syncError
                ? "Sync needs attention"
                : "Cloud sync ready"
          }
          icon={
            !cloud.productConsent || cloud.syncError
              ? "alert-circle-outline"
              : "shield-checkmark-outline"
          }
        />
        <View style={styles.metricRow}>
          <View style={styles.metric}>
            <Text style={[styles.metricValue, { color: theme.text }]}>
              {cloud.pendingOperations}
            </Text>
            <Text style={[styles.metricLabel, { color: theme.secondaryText }]}>
              waiting
            </Text>
          </View>
          <View style={styles.metricWide}>
            <Text style={[styles.metricValueSmall, { color: theme.text }]}>
              {when(cloud.lastSyncAt)}
            </Text>
            <Text style={[styles.metricLabel, { color: theme.secondaryText }]}>
              last completed
            </Text>
          </View>
        </View>
        {cloud.syncError ? (
          <Text
            accessibilityRole="alert"
            style={[styles.body, { color: theme.danger }]}
          >
            {cloud.syncError}
          </Text>
        ) : null}
        <Button
          label={cloud.productConsent ? "Sync now" : "Review cloud consent"}
          icon="sync-outline"
          loading={cloud.busy}
          loadingLabel="Syncing protected records..."
          onPress={() =>
            cloud.productConsent
              ? void cloud.syncNow(true)
              : router.push("/account" as Href)
          }
        />
      </Card>
      <Card>
        <SectionTitle title="What sync does" icon="layers-outline" />
        <Text style={[styles.body, { color: theme.text }]}>
          Changes are saved locally first. Accepted images are checksum-verified
          during upload and stored behind your account access controls. Your
          record timeline is separately end-to-end encrypted with your recovery
          key.
        </Text>
        <Text style={[styles.body, { color: theme.secondaryText }]}>
          If the network drops, the durable queue stays in the protected
          database and retries when the app returns or a background window
          becomes available.
        </Text>
      </Card>
      <Card>
        <SectionTitle
          title="Local use stays available"
          icon="phone-portrait-outline"
        />
        <Text style={[styles.body, { color: theme.text }]}>
          Signing out, losing service, or going offline does not remove local
          scans or stop local reports and comparisons.
        </Text>
      </Card>
    </Screen>
  );
}

const styles = StyleSheet.create({
  body: { fontSize: 14, lineHeight: 21 },
  metricRow: { flexDirection: "row", gap: 18, alignItems: "flex-start" },
  metric: { minWidth: 70, gap: 2 },
  metricWide: { flex: 1, gap: 2 },
  metricValue: {
    fontSize: 28,
    fontWeight: "900",
    fontVariant: ["tabular-nums"],
  },
  metricValueSmall: { fontSize: 14, lineHeight: 20, fontWeight: "800" },
  metricLabel: { fontSize: 12, fontWeight: "700" },
});
