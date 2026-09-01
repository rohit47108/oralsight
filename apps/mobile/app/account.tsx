import { useState } from "react";
import { Alert, Share, StyleSheet, Text, TextInput, View } from "react-native";
import { type Href, router } from "expo-router";

import { Screen } from "@/components/Screen";
import { Button, Card, SectionTitle } from "@/components/Ui";
import { useCloudStore } from "@/cloud/useCloudStore";
import { useStoma3DStore } from "@/store/useStoma3DStore";
import { useAppTheme } from "@/theme";

function readableRole(value: string): string {
  return value
    .replaceAll("_", " ")
    .replace(/^./, (letter) => letter.toUpperCase());
}

export default function AccountRoute() {
  const theme = useAppTheme();
  const cloud = useCloudStore();
  const deleteLocalData = useStoma3DStore((state) => state.deleteEverything);
  const [showRecovery, setShowRecovery] = useState(false);
  const [recoveryInput, setRecoveryInput] = useState("");
  const [deletingEverywhere, setDeletingEverywhere] = useState(false);

  const confirmCloudDeletion = () =>
    Alert.alert(
      "Delete cloud account data?",
      "This starts permanent deletion of synced records, uploaded files, shares, reviews, and generated files. Local data remains on this device until you delete it separately.",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete cloud data",
          style: "destructive",
          onPress: () =>
            void cloud.requestCloudDeletion().catch(() => undefined),
        },
      ],
    );

  const confirmEverywhereDeletion = () =>
    Alert.alert(
      "Delete cloud and local data?",
      "This starts permanent cloud deletion, then removes this device's protected database, images, reports, reminders, and local encryption keys. This cannot be undone.",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete everywhere",
          style: "destructive",
          onPress: () => {
            setDeletingEverywhere(true);
            void cloud
              .requestCloudDeletion()
              .then(() => deleteLocalData())
              .then(() => router.replace("/onboarding"))
              .catch(() => setDeletingEverywhere(false));
          },
        },
      ],
    );

  const confirmConsentWithdrawal = () =>
    Alert.alert(
      "Withdraw cloud consent?",
      "This stops new cloud sync and report work, cancels unfinished processing, and revokes active shares and clinician access. Existing stored records remain until you delete cloud data.",
      [
        { text: "Keep consent", style: "cancel" },
        {
          text: "Withdraw consent",
          style: "destructive",
          onPress: () =>
            void cloud.revokeProductConsent().catch(() => undefined),
        },
      ],
    );

  return (
    <Screen
      title="Account"
      eyebrow="Optional sync and sharing"
      action={
        <Button label="Back" variant="ghost" onPress={() => router.back()} />
      }
    >
      {cloud.deletion?.status === "completed" ? (
        <Card accent="teal">
          <SectionTitle
            title="Cloud data deleted"
            subtitle="The account session, sync key, links, and cloud metadata were removed from this device. Local scans remain until you delete them separately."
            icon="checkmark-circle-outline"
          />
        </Card>
      ) : null}
      {cloud.sessionStatus === "deletion_pending" ? (
        <Card accent="amber">
          <SectionTitle
            title={
              cloud.deletion?.status === "failed"
                ? "Cloud deletion needs attention"
                : "Cloud deletion in progress"
            }
            subtitle="Sync, sharing, processing, analytics, and account setup stay paused until deletion and device cleanup finish. Local features remain available."
            icon="time-outline"
          />
          {cloud.deletion ? (
            <Text style={[styles.body, { color: theme.text }]}>
              Status: {cloud.deletion.status.replaceAll("_", " ")}
            </Text>
          ) : null}
          <Button
            label="Check deletion status"
            variant="secondary"
            loading={cloud.busy}
            loadingLabel="Checking status..."
            onPress={() => void cloud.refreshDeletion()}
          />
        </Card>
      ) : cloud.sessionStatus === "recreation_required" ? (
        <Card accent="amber">
          <SectionTitle
            title="Confirm account recreation"
            subtitle="This account was deleted. Create a new empty account to use cloud sync again. Your previous cloud records were not restored."
            icon="refresh-circle-outline"
          />
          <Button
            label="Recreate empty account"
            loading={cloud.busy}
            loadingLabel="Recreating account..."
            onPress={() => void cloud.recreateAccount()}
          />
          <Text style={[styles.body, { color: theme.secondaryText }]}>
            Local scans remain on this device and are not uploaded
            automatically.
          </Text>
        </Card>
      ) : cloud.configured && cloud.sessionStatus === "unavailable" ? (
        <Card accent="amber">
          <SectionTitle
            title="Cloud account paused on this device"
            subtitle="The prior deletion could not be tracked safely, so this app removed its session and will not reconnect automatically. Local features remain available."
            icon="shield-outline"
          />
        </Card>
      ) : !cloud.configured ? (
        <Card accent="amber">
          <SectionTitle
            title="Account services unavailable"
            icon="cloud-offline-outline"
          />
          <Text style={[styles.body, { color: theme.text }]}>
            {cloud.configurationMessage}
          </Text>
          <Text style={[styles.body, { color: theme.secondaryText }]}>
            Capture, analysis, comparison, the observation map, and local
            reports still work on this device.
          </Text>
        </Card>
      ) : cloud.sessionStatus !== "signed_in" ? (
        <Card>
          <SectionTitle
            title="Use Stoma3D on more than one device"
            subtitle="Signing in is optional. Your local workspace remains available without an account."
            icon="person-circle-outline"
          />
          <Button
            label="Sign in or create account"
            icon="log-in-outline"
            loading={
              cloud.busy ||
              cloud.sessionStatus === "checking" ||
              cloud.sessionStatus === "signing_in"
            }
            loadingLabel="Opening secure sign-in..."
            onPress={() => void cloud.signIn()}
          />
        </Card>
      ) : (
        <>
          <Card accent="teal">
            <SectionTitle title="Signed in" icon="checkmark-circle-outline" />
            <View style={styles.detailRow}>
              <Text style={[styles.label, { color: theme.secondaryText }]}>
                Access
              </Text>
              <Text style={[styles.value, { color: theme.text }]}>
                {readableRole(cloud.account?.role ?? "patient")}
              </Text>
            </View>
            <View style={styles.detailRow}>
              <Text style={[styles.label, { color: theme.secondaryText }]}>
                Account status
              </Text>
              <Text style={[styles.value, { color: theme.text }]}>
                {cloud.account?.deletionPending ? "Deletion pending" : "Active"}
              </Text>
            </View>
          </Card>

          {cloud.account?.deletionPending ? (
            <Card accent="amber">
              <SectionTitle
                title="Cloud deletion in progress"
                subtitle="New sync, sharing, processing, and analytics are paused. Local features remain available."
                icon="time-outline"
              />
            </Card>
          ) : cloud.productConsent ? (
            <Card>
              <SectionTitle
                title="Cloud consent active"
                subtitle={`Version ${cloud.productConsent.documentVersion} · accepted ${new Date(cloud.productConsent.acceptedAt).toLocaleString()}`}
                icon="shield-checkmark-outline"
              />
              <Text style={[styles.body, { color: theme.secondaryText }]}>
                You can stop new cloud work at any time. Withdrawing consent
                does not delete records already stored.
              </Text>
              <Button
                label="Withdraw cloud consent"
                variant="danger"
                onPress={confirmConsentWithdrawal}
              />
            </Card>
          ) : cloud.consentDocument ? (
            <Card accent="amber">
              <SectionTitle
                title={cloud.consentDocument.title}
                subtitle={`Version ${cloud.consentDocument.documentVersion}`}
                icon="document-text-outline"
              />
              <Text style={[styles.consentBody, { color: theme.text }]}>
                {cloud.consentDocument.body}
              </Text>
              <Button
                label="Accept and enable cloud features"
                icon="checkmark-circle-outline"
                loading={cloud.busy}
                onPress={() =>
                  void cloud.acceptProductConsent().catch(() => undefined)
                }
              />
              <Text style={[styles.body, { color: theme.secondaryText }]}>
                Product analytics is a separate choice and remains off unless
                you enable it in Settings.
              </Text>
            </Card>
          ) : (
            <Card accent="amber">
              <Text style={[styles.body, { color: theme.text }]}>
                The current cloud consent document could not be loaded. Local
                features remain available.
              </Text>
              <Button
                label="Retry"
                variant="ghost"
                onPress={() => void cloud.refreshAccountData()}
              />
            </Card>
          )}

          {cloud.productConsent ? (
            <Card>
              <SectionTitle title="Account tools" icon="grid-outline" />
              <Button
                label="Sync and backup"
                variant="secondary"
                icon="sync-outline"
                onPress={() => router.push("/cloud-sync" as Href)}
              />
              <Button
                label="Secure QR sharing"
                variant="secondary"
                icon="qr-code-outline"
                onPress={() => router.push("/shares" as Href)}
              />
              <Button
                label="Access history"
                variant="secondary"
                icon="eye-outline"
                onPress={() => router.push("/access-history" as Href)}
              />
              <Button
                label="Processing jobs"
                variant="secondary"
                icon="hourglass-outline"
                onPress={() => router.push("/jobs" as Href)}
              />
            </Card>
          ) : null}

          {cloud.productConsent ? (
            <Card>
              <SectionTitle
                title="Sync recovery key"
                subtitle="This key unlocks end-to-end encrypted sync data on another device. Stoma3D cannot recover it for you."
                icon="key-outline"
              />
              {showRecovery && cloud.recoveryCode ? (
                <Text
                  selectable
                  style={[
                    styles.recovery,
                    { color: theme.text, borderColor: theme.border },
                  ]}
                >
                  {cloud.recoveryCode}
                </Text>
              ) : null}
              <Button
                label={showRecovery ? "Hide recovery key" : "Show recovery key"}
                variant="ghost"
                icon={showRecovery ? "eye-off-outline" : "eye-outline"}
                disabled={!cloud.recoveryCode}
                onPress={() => setShowRecovery((value) => !value)}
              />
              <Button
                label="Save recovery key"
                variant="ghost"
                icon="share-outline"
                disabled={!cloud.recoveryCode}
                onPress={() => {
                  if (cloud.recoveryCode) {
                    void Share.share({
                      title: "Stoma3D sync recovery key",
                      message: cloud.recoveryCode,
                    });
                  }
                }}
              />
              <TextInput
                accessibilityLabel="Existing sync recovery key"
                autoCapitalize="characters"
                autoCorrect={false}
                placeholder="Paste a recovery key from another device"
                placeholderTextColor={theme.secondaryText}
                value={recoveryInput}
                onChangeText={setRecoveryInput}
                style={[
                  styles.input,
                  {
                    color: theme.text,
                    borderColor: theme.border,
                    backgroundColor: theme.background,
                  },
                ]}
              />
              <Button
                label="Restore this key"
                variant="secondary"
                disabled={!recoveryInput.trim() || cloud.busy}
                onPress={() =>
                  void cloud
                    .importRecoveryCode(recoveryInput)
                    .then(() => setRecoveryInput(""))
                }
              />
            </Card>
          ) : null}

          {cloud.deletion ? (
            <Card accent="amber">
              <SectionTitle
                title="Cloud deletion request"
                icon="time-outline"
              />
              <Text style={[styles.body, { color: theme.text }]}>
                Status: {cloud.deletion.status.replaceAll("_", " ")}
              </Text>
              <Button
                label="Refresh deletion status"
                variant="ghost"
                onPress={() => void cloud.refreshDeletion()}
              />
            </Card>
          ) : null}

          <Card>
            <Button
              label="Sign out"
              variant="ghost"
              icon="log-out-outline"
              onPress={() => void cloud.signOut()}
            />
          </Card>
          <Card accent="coral">
            <SectionTitle
              title="Delete Stoma3D data"
              subtitle="Choose cloud only, or remove both cloud data and everything stored by this app on this device."
              icon="cloud-offline-outline"
            />
            <Button
              label="Delete cloud data"
              variant="danger"
              disabled={cloud.account?.deletionPending}
              onPress={confirmCloudDeletion}
            />
            <Button
              label="Delete cloud and local data"
              variant="danger"
              loading={deletingEverywhere}
              loadingLabel="Starting deletion..."
              disabled={cloud.account?.deletionPending}
              onPress={confirmEverywhereDeletion}
            />
          </Card>
        </>
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
  body: { fontSize: 14, lineHeight: 21 },
  detailRow: { flexDirection: "row", justifyContent: "space-between", gap: 16 },
  label: { fontSize: 13 },
  value: { flexShrink: 1, fontSize: 13, fontWeight: "800", textAlign: "right" },
  recovery: {
    borderWidth: 1,
    borderRadius: 12,
    padding: 12,
    fontSize: 12,
    lineHeight: 18,
    fontFamily: "monospace",
  },
  consentBody: { fontSize: 14, lineHeight: 22 },
  input: {
    minHeight: 52,
    borderWidth: 1,
    borderRadius: 12,
    paddingHorizontal: 14,
    fontSize: 14,
  },
  error: { fontSize: 13, lineHeight: 20, fontWeight: "700" },
});
