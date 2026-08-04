import { useEffect, useState } from "react";
import { FaceDetectionProvider } from "@infinitered/react-native-mlkit-face-detection";
import { router, Stack, useSegments } from "expo-router";
import { StatusBar } from "expo-status-bar";
import {
  ActivityIndicator,
  Alert,
  AppState,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { DISCLAIMER } from "@/constants";
import { routeRequiresConsent } from "@/lib/navigationPolicy";
import {
  purgeOralSightBackgroundTemporaryFiles,
  purgeOralSightTemporaryFiles,
} from "@/lib/tempFiles";
import { useOralSightStore } from "@/store/useOralSightStore";
import { useAppTheme, useShouldReduceMotion } from "@/theme";

function RootLayoutContent() {
  const theme = useAppTheme();
  const hydrate = useOralSightStore((state) => state.hydrate);
  const deleteEverything = useOralSightStore((state) => state.deleteEverything);
  const reducedMotion = useShouldReduceMotion();
  const hydrated = useOralSightStore((state) => state.hydrated);
  const storageError = useOralSightStore((state) => state.storageError);
  const consentedAt = useOralSightStore((state) => state.consentedAt);
  const [resetBusy, setResetBusy] = useState(false);
  const [resetError, setResetError] = useState<string | null>(null);
  const segments = useSegments();
  const consentBlocked =
    hydrated && !storageError && !consentedAt && routeRequiresConsent(segments);
  useEffect(() => {
    let active = true;
    void purgeOralSightTemporaryFiles()
      .catch(() => {
        console.warn("[ORALSIGHT_TEMP_PURGE_FAILED]");
      })
      .finally(() => {
        if (active) void hydrate();
      });
    return () => {
      active = false;
    };
  }, [hydrate]);

  useEffect(() => {
    const subscription = AppState.addEventListener("change", (nextState) => {
      if (nextState === "active") return;
      void purgeOralSightBackgroundTemporaryFiles().catch(() => {
        console.warn("[ORALSIGHT_BACKGROUND_TEMP_PURGE_FAILED]");
      });
    });
    return () => subscription.remove();
  }, []);

  useEffect(() => {
    if (consentBlocked) router.replace("/onboarding");
  }, [consentBlocked]);

  if (hydrated && storageError) {
    return (
      <SafeAreaView
        style={[styles.recovery, { backgroundColor: theme.background }]}
      >
        <StatusBar style={theme.statusBarStyle} />
        <ScrollView
          contentContainerStyle={styles.recoveryContent}
          keyboardShouldPersistTaps="handled"
        >
          <Text
            style={[styles.recoveryDisclaimer, { color: theme.secondaryText }]}
          >
            {DISCLAIMER}
          </Text>
          <Text style={[styles.recoveryTitle, { color: theme.text }]}>
            Protected workspace unavailable
          </Text>
          <Text style={[styles.recoveryBody, { color: theme.secondaryText }]}>
            {storageError}
          </Text>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Retry protected workspace"
            disabled={resetBusy}
            onPress={() => {
              setResetError(null);
              void hydrate();
            }}
            style={({ pressed }) => [
              styles.recoveryButton,
              { backgroundColor: theme.primary },
              pressed && styles.recoveryButtonPressed,
            ]}
          >
            <Text style={styles.recoveryButtonText}>
              Retry protected workspace
            </Text>
          </Pressable>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Delete local data and reset"
            accessibilityHint="Permanently removes all local OralSight observations and reports"
            disabled={resetBusy}
            onPress={() =>
              Alert.alert(
                "Reset all local OralSight data?",
                "This permanently deletes the protected database, images, reports, and encryption keys on this device. This cannot be undone.",
                [
                  { text: "Cancel", style: "cancel" },
                  {
                    text: "Delete and reset",
                    style: "destructive",
                    onPress: () => {
                      setResetBusy(true);
                      setResetError(null);
                      void deleteEverything()
                        .catch((error: unknown) =>
                          setResetError(
                            error instanceof Error
                              ? error.message
                              : "The local reset did not finish.",
                          ),
                        )
                        .finally(() => setResetBusy(false));
                    },
                  },
                ],
              )
            }
            style={({ pressed }) => [
              styles.recoveryButton,
              styles.recoverySecondaryButton,
              { borderColor: theme.danger },
              pressed && styles.recoveryButtonPressed,
            ]}
          >
            <Text
              style={[styles.recoverySecondaryText, { color: theme.danger }]}
            >
              {resetBusy
                ? "Resetting local data..."
                : "Delete local data and reset"}
            </Text>
          </Pressable>
          {resetError ? (
            <Text
              accessibilityRole="alert"
              style={[styles.recoveryError, { color: theme.danger }]}
            >
              {resetError}
            </Text>
          ) : null}
        </ScrollView>
      </SafeAreaView>
    );
  }

  if (!hydrated || consentBlocked) {
    return (
      <View style={styles.guard}>
        <StatusBar style="light" />
        <Text style={styles.guardDisclaimer}>{DISCLAIMER}</Text>
        <ActivityIndicator color="#FFFFFF" size="small" />
        <Text style={styles.guardText}>
          {hydrated ? "Opening consent..." : "Opening protected workspace..."}
        </Text>
      </View>
    );
  }

  return (
    <>
      <StatusBar style={theme.statusBarStyle} />
      <Stack
        screenOptions={{
          headerShown: false,
          animation: reducedMotion ? "none" : "slide_from_right",
          contentStyle: { backgroundColor: theme.background },
        }}
      >
        <Stack.Screen name="index" />
        <Stack.Screen name="onboarding" />
        <Stack.Screen name="(tabs)" />
        <Stack.Screen name="capture/[region]" />
        <Stack.Screen name="result/[captureId]" />
        <Stack.Screen name="compare" />
        <Stack.Screen name="report" />
        <Stack.Screen name="learn/atlas" />
        <Stack.Screen name="learn/scan-practice" />
        <Stack.Screen name="learn/questions" />
        <Stack.Screen name="roadmap" />
        <Stack.Screen name="model-card" />
      </Stack>
    </>
  );
}

export default function RootLayout() {
  return (
    <FaceDetectionProvider
      options={{
        performanceMode: "accurate",
        landmarkMode: false,
        contourMode: false,
        classificationMode: false,
        minFaceSize: 0.1,
        isTrackingEnabled: false,
      }}
    >
      <RootLayoutContent />
    </FaceDetectionProvider>
  );
}

const styles = StyleSheet.create({
  guard: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: 12,
    backgroundColor: "#102A43",
  },
  guardText: { color: "#FFFFFF", fontSize: 13, fontWeight: "700" },
  guardDisclaimer: {
    color: "#FFFFFF",
    fontSize: 12,
    fontWeight: "700",
    textAlign: "center",
  },
  recovery: {
    flex: 1,
  },
  recoveryContent: {
    flexGrow: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: 16,
    padding: 28,
  },
  recoveryTitle: {
    fontSize: 26,
    lineHeight: 32,
    fontWeight: "800",
    textAlign: "center",
  },
  recoveryDisclaimer: {
    fontSize: 12,
    fontWeight: "700",
    textAlign: "center",
  },
  recoveryBody: {
    maxWidth: 520,
    fontSize: 15,
    lineHeight: 23,
    textAlign: "center",
  },
  recoveryButton: {
    minHeight: 48,
    minWidth: 240,
    borderRadius: 14,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 18,
    paddingVertical: 12,
  },
  recoverySecondaryButton: {
    backgroundColor: "transparent",
    borderWidth: 1,
  },
  recoveryButtonPressed: { opacity: 0.82 },
  recoveryButtonText: { color: "#FFFFFF", fontWeight: "800" },
  recoverySecondaryText: { fontWeight: "800", textAlign: "center" },
  recoveryError: {
    maxWidth: 520,
    fontSize: 13,
    lineHeight: 19,
    fontWeight: "700",
    textAlign: "center",
  },
});
