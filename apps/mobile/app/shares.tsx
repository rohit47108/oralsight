import { useEffect, useMemo, useState } from "react";
import { Share, StyleSheet, Text, View } from "react-native";
import { router } from "expo-router";
import QRCode from "react-native-qrcode-svg";

import { shareableCloudResources } from "@/cloud/productSync";
import type { ResourceRef } from "@/cloud/contracts";
import { shareSecretStaysInFragment } from "@/cloud/shareUrl";
import { useCloudStore } from "@/cloud/useCloudStore";
import { Screen } from "@/components/Screen";
import { Button, Card, ChoiceChip, SectionTitle } from "@/components/Ui";
import { useOralSightStore } from "@/store/useOralSightStore";
import { useAppTheme } from "@/theme";

const expiryChoices = [
  { label: "1 hour", seconds: 3_600 },
  { label: "24 hours", seconds: 86_400 },
  { label: "7 days", seconds: 604_800 },
] as const;

export default function SharesRoute() {
  const theme = useAppTheme();
  const cloud = useCloudStore();
  const sessions = useOralSightStore((state) => state.sessions);
  const [resources, setResources] = useState<
    Awaited<ReturnType<typeof shareableCloudResources>>
  >([]);
  const [selectedLocalId, setSelectedLocalId] = useState<string | null>(null);
  const [expirySeconds, setExpirySeconds] = useState(86_400);
  const [maxExchanges, setMaxExchanges] = useState(1);
  const [activeUrl, setActiveUrl] = useState<string | null>(null);

  useEffect(() => {
    void shareableCloudResources(cloud.jobs).then((items) => {
      setResources(items);
      setSelectedLocalId((current) => current ?? items.at(-1)?.localId ?? null);
    });
  }, [cloud.jobs, cloud.lastSyncAt]);

  useEffect(() => {
    void cloud.refreshAccountData();
  }, []);

  const selected = resources.find((value) => value.localId === selectedLocalId);
  const sessionLabels = useMemo(
    () => new Map(sessions.map((session) => [session.id, session.label])),
    [sessions],
  );
  const create = async () => {
    if (!selected) return;
    const refs: ResourceRef[] = [
      {
        resourceType: selected.resourceType,
        resourceId: selected.resourceId,
      },
    ];
    const url = await cloud.createShare(refs, {
      expiresInSeconds: expirySeconds,
      maxExchanges,
    });
    if (!shareSecretStaysInFragment(url)) {
      throw new Error("The share secret was not isolated in the URL fragment.");
    }
    setActiveUrl(url);
  };

  return (
    <Screen
      title="Secure QR sharing"
      eyebrow="Time-limited, revocable access"
      action={
        <Button label="Back" variant="ghost" onPress={() => router.back()} />
      }
    >
      {resources.length === 0 ? (
        <Card accent="amber">
          <SectionTitle
            title="Sync a scan or create a report before sharing"
            icon="sync-outline"
          />
          <Text style={[styles.body, { color: theme.text }]}>
            A QR link points only to one selected cloud scan or clinician PDF.
            Sync a scan first, then create a PDF if that is what you want to
            share.
          </Text>
          <Button
            label="Sync now"
            icon="sync-outline"
            loading={cloud.busy}
            onPress={() => void cloud.syncNow(true)}
          />
        </Card>
      ) : (
        <Card>
          <SectionTitle
            title="Choose what to share"
            subtitle="Only the selected scan or report is included. Other account data stays private."
            icon="folder-open-outline"
          />
          <View style={styles.chips}>
            {resources.map((resource) => (
              <ChoiceChip
                key={resource.localId}
                label={
                  resource.resourceType === "report"
                    ? `Clinician PDF${resource.createdAt ? ` · ${new Date(resource.createdAt).toLocaleDateString()}` : ""}`
                    : (sessionLabels.get(resource.localId) ??
                      "Structured mouth scan")
                }
                selected={selectedLocalId === resource.localId}
                onPress={() => setSelectedLocalId(resource.localId)}
              />
            ))}
          </View>
          <Text style={[styles.label, { color: theme.text }]}>
            Link lifetime
          </Text>
          <View style={styles.chips}>
            {expiryChoices.map((choice) => (
              <ChoiceChip
                key={choice.seconds}
                label={choice.label}
                selected={expirySeconds === choice.seconds}
                onPress={() => setExpirySeconds(choice.seconds)}
              />
            ))}
          </View>
          <Text style={[styles.label, { color: theme.text }]}>
            Number of link exchanges
          </Text>
          <View style={styles.chips}>
            {[1, 3].map((count) => (
              <ChoiceChip
                key={count}
                label={count === 1 ? "One viewer" : "Up to three"}
                selected={maxExchanges === count}
                onPress={() => setMaxExchanges(count)}
              />
            ))}
          </View>
          <Button
            label={
              selected?.resourceType === "report"
                ? "Create report QR link"
                : "Create scan QR link"
            }
            icon="qr-code-outline"
            loading={cloud.busy}
            disabled={!selected}
            onPress={() => void create()}
          />
        </Card>
      )}

      {activeUrl ? (
        <Card accent="teal">
          <SectionTitle
            title="QR link ready"
            subtitle="The access secret stays after # in the link, so it is not sent in a normal web request."
            icon="shield-checkmark-outline"
          />
          <View
            accessible
            accessibilityLabel="Secure OralSight sharing QR code"
            style={styles.qr}
          >
            <QRCode
              value={activeUrl}
              size={220}
              quietZone={12}
              color="#102A43"
              backgroundColor="#FFFFFF"
            />
          </View>
          <Button
            label="Share link"
            variant="secondary"
            icon="share-outline"
            onPress={() =>
              void Share.share({
                title: "OralSight observation link",
                message: activeUrl,
              })
            }
          />
          <Button
            label="Hide QR"
            variant="ghost"
            onPress={() => setActiveUrl(null)}
          />
        </Card>
      ) : null}

      <Card>
        <SectionTitle title="Your links" icon="link-outline" />
        {cloud.shares.length === 0 ? (
          <Text style={[styles.body, { color: theme.secondaryText }]}>
            No QR links yet.
          </Text>
        ) : (
          cloud.shares.map((share) => (
            <View
              key={share.shareId}
              style={[styles.shareRow, { borderTopColor: theme.border }]}
            >
              <View style={styles.shareCopy}>
                <Text style={[styles.shareTitle, { color: theme.text }]}>
                  {share.active ? "Active link" : "Closed link"}
                </Text>
                <Text style={[styles.meta, { color: theme.secondaryText }]}>
                  Expires {new Date(share.expiresAt).toLocaleString()} ·{" "}
                  {share.exchangeCount}/{share.maxExchanges} exchanges
                </Text>
              </View>
              {share.active && cloud.shareUrls[share.shareId] ? (
                <Button
                  label="View QR"
                  variant="ghost"
                  onPress={() =>
                    setActiveUrl(cloud.shareUrls[share.shareId] ?? null)
                  }
                />
              ) : null}
              {share.active ? (
                <Button
                  label="Revoke"
                  variant="danger"
                  onPress={() => void cloud.revokeShare(share.shareId)}
                />
              ) : null}
            </View>
          ))
        )}
      </Card>
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
  body: { fontSize: 14, lineHeight: 21 },
  label: { fontSize: 13, fontWeight: "800" },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  qr: {
    alignSelf: "center",
    padding: 8,
    borderRadius: 18,
    backgroundColor: "#FFFFFF",
  },
  shareRow: {
    gap: 10,
    paddingTop: 14,
    borderTopWidth: StyleSheet.hairlineWidth,
  },
  shareCopy: { gap: 2 },
  shareTitle: { fontSize: 15, fontWeight: "800" },
  meta: { fontSize: 12, lineHeight: 18 },
  error: { fontSize: 13, lineHeight: 20, fontWeight: "700" },
});
