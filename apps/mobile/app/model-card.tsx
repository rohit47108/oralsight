import { useEffect, useState } from "react";
import { router } from "expo-router";
import { ActivityIndicator, StyleSheet, Text, View } from "react-native";
import type { ModelCard } from "@stoma3d/contracts";

import { Screen } from "@/components/Screen";
import { Button, Card, SectionTitle } from "@/components/Ui";
import { fetchModelCard } from "@/lib/api";
import { useAppTheme } from "@/theme";

export default function ModelCardRoute() {
  const theme = useAppTheme();
  const [card, setCard] = useState<ModelCard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [requestEpoch, setRequestEpoch] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    void fetchModelCard(controller.signal)
      .then(setCard)
      .catch((fetchError: unknown) => {
        if (!controller.signal.aborted)
          setError(
            fetchError instanceof Error
              ? fetchError.message
              : "Model card unavailable.",
          );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [requestEpoch]);
  return (
    <Screen
      title="Deployed model card"
      eyebrow="Live transparency endpoint"
      action={
        <Button label="Back" variant="ghost" onPress={() => router.back()} />
      }
    >
      {loading ? (
        <View
          accessibilityLiveRegion="polite"
          accessibilityLabel="Loading deployed model card"
          style={styles.loading}
        >
          <ActivityIndicator color={theme.primary} />
          <Text style={[styles.body, { color: theme.secondaryText }]}>
            Loading the deployed gate status...
          </Text>
        </View>
      ) : null}
      {error ? (
        <Card accent="amber">
          <SectionTitle
            title="Model card unavailable"
            icon="cloud-offline-outline"
          />
          <Text style={[styles.body, { color: theme.text }]}>{error}</Text>
          <Text style={[styles.body, { color: theme.secondaryText }]}>
            No cached model claims are substituted.
          </Text>
          <Button
            label="Retry model card"
            variant="secondary"
            icon="refresh-outline"
            disabled={loading}
            onPress={() => setRequestEpoch((value) => value + 1)}
          />
        </Card>
      ) : null}
      {card ? (
        <>
          <Card>
            <SectionTitle
              title={`Service ${card.serviceVersion}`}
              subtitle={card.intendedUse}
              icon="server-outline"
            />
          </Card>
          {card.releaseGates.map((gate) => (
            <Card key={gate.head} accent={gate.passed ? "teal" : "amber"}>
              <View style={styles.row}>
                <Text style={[styles.head, { color: theme.text }]}>
                  {gate.head.replaceAll("_", " ")}
                </Text>
                <Text
                  style={[
                    styles.status,
                    { color: gate.passed ? theme.primary : theme.amber },
                  ]}
                >
                  {gate.passed ? "GATE PASSED" : "DISABLED"}
                </Text>
              </View>
              {gate.unmetRequirements.map((item) => (
                <Text
                  key={item}
                  style={[styles.body, { color: theme.secondaryText }]}
                >
                  • {item}
                </Text>
              ))}
            </Card>
          ))}
          <Card accent="coral">
            <SectionTitle title="Forbidden claims" icon="ban-outline" />
            {card.forbiddenClaims.map((claim) => (
              <Text
                key={claim}
                style={[styles.body, { color: theme.secondaryText }]}
              >
                • {claim}
              </Text>
            ))}
          </Card>
        </>
      ) : null}
    </Screen>
  );
}

const styles = StyleSheet.create({
  loading: { alignItems: "center", gap: 10, paddingVertical: 18 },
  row: { flexDirection: "row", justifyContent: "space-between", gap: 12 },
  head: { fontSize: 15, fontWeight: "900", textTransform: "capitalize" },
  status: { fontSize: 11, fontWeight: "900" },
  body: { fontSize: 13, lineHeight: 20 },
});
