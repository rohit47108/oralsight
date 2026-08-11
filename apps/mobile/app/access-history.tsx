import { useEffect } from "react";
import { StyleSheet, Text, View } from "react-native";
import { router } from "expo-router";

import { useCloudStore } from "@/cloud/useCloudStore";
import { Screen } from "@/components/Screen";
import { Button, Card, SectionTitle } from "@/components/Ui";
import { useAppTheme } from "@/theme";

const eventLabels: Record<string, string> = {
  grant_created: "Clinician access granted",
  grant_revoked: "Clinician access revoked",
  share_created: "QR link created",
  share_revoked: "QR link revoked",
  share_exchanged: "QR link opened",
  resource_viewed: "Shared record viewed",
  review_status_changed: "Review status changed",
  annotation_created: "Clinician note added",
};

export default function AccessHistoryRoute() {
  const theme = useAppTheme();
  const cloud = useCloudStore();
  useEffect(() => {
    void cloud.refreshAccountData();
  }, []);
  return (
    <Screen
      title="Access history"
      eyebrow="Who accessed shared records"
      action={
        <Button label="Back" variant="ghost" onPress={() => router.back()} />
      }
    >
      <Card>
        <SectionTitle
          title="Account access log"
          subtitle="Share openings, clinician access, views, and review changes are recorded by the server."
          icon="eye-outline"
        />
        <Button
          label="Refresh"
          variant="ghost"
          icon="refresh-outline"
          loading={cloud.busy}
          onPress={() => void cloud.refreshAccountData()}
        />
      </Card>
      {cloud.accessHistory.length === 0 ? (
        <Card>
          <Text style={[styles.body, { color: theme.secondaryText }]}>
            No shared-record access has been recorded.
          </Text>
        </Card>
      ) : (
        cloud.accessHistory.map((event) => (
          <Card key={event.eventId}>
            <View style={styles.row}>
              <View style={[styles.dot, { backgroundColor: theme.mint }]} />
              <View style={styles.copy}>
                <Text style={[styles.title, { color: theme.text }]}>
                  {eventLabels[event.eventType] ??
                    event.eventType.replaceAll("_", " ")}
                </Text>
                <Text style={[styles.meta, { color: theme.secondaryText }]}>
                  {event.actorType.replaceAll("_", " ")} ·{" "}
                  {new Date(event.createdAt).toLocaleString()}
                </Text>
                <Text style={[styles.meta, { color: theme.secondaryText }]}>
                  {event.resourceType.replaceAll("_", " ")}
                </Text>
              </View>
            </View>
          </Card>
        ))
      )}
      {cloud.error ? (
        <Text
          accessibilityRole="alert"
          style={[styles.error, { color: theme.danger }]}
        >
          {cloud.error}
        </Text>
      ) : null}
    </Screen>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", gap: 12 },
  dot: { width: 12, height: 12, borderRadius: 6, marginTop: 5 },
  copy: { flex: 1, gap: 3 },
  title: { fontSize: 15, fontWeight: "800" },
  body: { fontSize: 14, lineHeight: 21 },
  meta: { fontSize: 12, lineHeight: 18 },
  error: { fontSize: 13, lineHeight: 20, fontWeight: "700" },
});
