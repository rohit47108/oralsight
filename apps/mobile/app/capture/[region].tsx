import { useEffect, useRef, useState } from "react";
import { useFaceDetection } from "@infinitered/react-native-mlkit-face-detection";
import { router, useLocalSearchParams } from "expo-router";
import { CameraView, useCameraPermissions } from "expo-camera";
import { Accelerometer } from "expo-sensors";
import * as Crypto from "expo-crypto";
import * as Haptics from "expo-haptics";
import * as ImagePicker from "expo-image-picker";
import * as Speech from "expo-speech";
import { Image, Linking, StyleSheet, Text, View } from "react-native";
import {
  MOUTH_REGION_DETAILS,
  mouthRegionSchema,
  type QualityResult,
} from "@oralsight/contracts";

import { CaptureGuideOverlay } from "@/components/CaptureGuideOverlay";
import { Screen } from "@/components/Screen";
import { StabilityIndicator } from "@/components/StabilityIndicator";
import {
  Button,
  Card,
  ChoiceChip,
  MetricBar,
  SectionTitle,
} from "@/components/Ui";
import { captureStorageRejectionReasons } from "@/lib/analysisPolicy";
import { analyzeCapture } from "@/lib/api";
import {
  qualityForSanitizedCapture,
  sanitizeCameraCapture,
  sanitizeSelectedImage,
  type SanitizedCapture,
} from "@/lib/imagePipeline";
import { withFaceDetectionResult } from "@/lib/privacyPolicy";
import { latestPriorAcceptedCapture } from "@/lib/longitudinalPolicy";
import { humanizeResultReason } from "@/lib/resultCopy";
import {
  decryptToTemporaryFile,
  encryptFile,
  removeProtectedFile,
  removeTemporaryFile,
} from "@/lib/secureFiles";
import { removePickerTemporaryCopy } from "@/lib/tempFiles";
import { useOralSightStore } from "@/store/useOralSightStore";
import { useAppTheme } from "@/theme";
import type { CaptureRecord } from "@/types";

interface CandidateState {
  capture: SanitizedCapture;
  quality: QualityResult;
}

export default function CaptureRoute() {
  const theme = useAppTheme();
  const params = useLocalSearchParams<{ region?: string }>();
  const parsedRegion = mouthRegionSchema.safeParse(params.region);
  const region = parsedRegion.success ? parsedRegion.data : null;
  const detail = MOUTH_REGION_DETAILS.find((item) => item.id === region);
  const activeSessionId = useOralSightStore((state) => state.activeSessionId);
  const settings = useOralSightStore((state) => state.settings);
  const captures = useOralSightStore((state) => state.captures);
  const addCapture = useOralSightStore((state) => state.addCapture);
  const faceDetector = useFaceDetection();
  const cameraRef = useRef<CameraView>(null);
  const previousMotion = useRef({ x: 0, y: 0, z: 1 });
  const stableSamples = useRef(0);
  const [permission, requestPermission] = useCameraPermissions();
  const [stability, setStability] = useState(0);
  const [sensorAvailable, setSensorAvailable] = useState<boolean | null>(null);
  const [candidate, setCandidate] = useState<CandidateState | null>(null);
  const [rejectedQuality, setRejectedQuality] = useState<QualityResult | null>(
    null,
  );
  const [mouthOnlyConfirmed, setMouthOnlyConfirmed] = useState(false);
  const [regionConfirmed, setRegionConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [busyLabel, setBusyLabel] = useState("Working...");
  const [photoPermissionBlocked, setPhotoPermissionBlocked] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ghostEnabled, setGhostEnabled] = useState(false);
  const [ghostUri, setGhostUri] = useState<string | null>(null);
  const [ghostError, setGhostError] = useState<string | null>(null);
  const priorCapture =
    region === null
      ? null
      : latestPriorAcceptedCapture(captures, activeSessionId, region);

  useEffect(() => {
    let active = true;
    let subscription: { remove: () => void } | null = null;
    void Accelerometer.isAvailableAsync()
      .then((available) => {
        if (!active) return;
        setSensorAvailable(available);
        if (!available) {
          setStability(1);
          return;
        }
        Accelerometer.setUpdateInterval(100);
        subscription = Accelerometer.addListener((motion) => {
          const prior = previousMotion.current;
          const delta =
            Math.abs(motion.x - prior.x) +
            Math.abs(motion.y - prior.y) +
            Math.abs(motion.z - prior.z);
          const gravityError = Math.abs(
            Math.sqrt(motion.x ** 2 + motion.y ** 2 + motion.z ** 2) - 1,
          );
          stableSamples.current =
            delta < 0.055 && gravityError < 0.12
              ? Math.min(12, stableSamples.current + 1)
              : Math.max(0, stableSamples.current - 3);
          setStability(stableSamples.current / 12);
          previousMotion.current = motion;
        });
      })
      .catch(() => {
        if (!active) return;
        setSensorAvailable(false);
        setStability(1);
      });
    return () => {
      active = false;
      subscription?.remove();
    };
  }, []);

  useEffect(() => {
    if (!settings.voiceInstructions || !detail) return;
    Speech.speak(detail.captureInstruction, { rate: 0.9 });
    return () => {
      void Speech.stop();
    };
  }, [detail, settings.voiceInstructions]);

  useEffect(
    () => () => {
      void removeTemporaryFile(candidate?.capture.uri);
    },
    [candidate],
  );

  useEffect(() => {
    setGhostUri(null);
    setGhostError(null);
    if (!ghostEnabled || !priorCapture?.encryptedUri || candidate !== null) {
      return undefined;
    }
    let active = true;
    let temporary: string | null = null;
    const extension = priorCapture.mimeType === "image/png" ? "png" : "jpg";
    void decryptToTemporaryFile(
      priorCapture.encryptedUri,
      extension,
      `capture:${priorCapture.id}`,
    )
      .then(async (uri) => {
        if (!active) {
          await removeTemporaryFile(uri);
          return;
        }
        temporary = uri;
        setGhostUri(uri);
      })
      .catch(() => {
        if (active) {
          setGhostError(
            "The earlier protected image could not be opened as an alignment guide.",
          );
          setGhostEnabled(false);
        }
      });
    return () => {
      active = false;
      void removeTemporaryFile(temporary);
    };
  }, [
    candidate,
    ghostEnabled,
    priorCapture?.encryptedUri,
    priorCapture?.id,
    priorCapture?.mimeType,
  ]);

  if (!region || !detail) {
    return (
      <Screen title="Unsupported region">
        <Card accent="coral">
          <Text style={{ color: theme.text }}>
            The requested region is not part of the fixed eight-region scan.
          </Text>
          <Button label="Return" onPress={() => router.back()} />
        </Card>
      </Screen>
    );
  }

  const prepareCandidate = async (capture: SanitizedCapture) => {
    setBusyLabel("Checking privacy and image quality...");
    try {
      if (
        faceDetector.status === "init" ||
        faceDetector.status === "modelLoading" ||
        faceDetector.status === "error"
      ) {
        await faceDetector.initialize({
          performanceMode: "accurate",
          landmarkMode: false,
          contourMode: false,
          classificationMode: false,
          minFaceSize: 0.1,
          isTrackingEnabled: false,
        });
      }
      if (faceDetector.status === "error") {
        throw new Error("The on-device privacy model could not start.");
      }
      const detection = await faceDetector.detectFaces(capture.uri);
      if (!detection || !Array.isArray(detection.faces)) {
        throw new Error("The on-device privacy check did not finish.");
      }
      capture = withFaceDetectionResult(capture, detection.faces.length > 0);
    } catch (privacyError) {
      await removeTemporaryFile(capture.uri);
      setCandidate(null);
      setRejectedQuality(null);
      setMouthOnlyConfirmed(false);
      setRegionConfirmed(false);
      throw new Error(
        privacyError instanceof Error
          ? `${privacyError.message} The image was deleted and was not saved or uploaded.`
          : "The on-device privacy check failed. The image was deleted and was not saved or uploaded.",
      );
    }
    const quality = qualityForSanitizedCapture(capture);
    if (settings.haptics) {
      await Haptics.notificationAsync(
        quality.accepted
          ? Haptics.NotificationFeedbackType.Success
          : Haptics.NotificationFeedbackType.Warning,
      ).catch(() => undefined);
    }
    if (!quality.accepted) {
      await removeTemporaryFile(capture.uri);
      setCandidate(null);
      setRejectedQuality(quality);
      setMouthOnlyConfirmed(false);
      setRegionConfirmed(false);
      return;
    }
    setRejectedQuality(null);
    setCandidate({ capture, quality });
    setMouthOnlyConfirmed(false);
    setRegionConfirmed(false);
  };

  const takePhoto = async () => {
    setError(null);
    setBusy(true);
    setBusyLabel("Capturing image...");
    let rawPhotoUri: string | null = null;
    try {
      const photo = await cameraRef.current?.takePictureAsync({
        quality: 0.9,
        skipProcessing: false,
      });
      if (!photo?.uri) throw new Error("The camera did not return an image.");
      rawPhotoUri = photo.uri;
      await prepareCandidate(
        await sanitizeCameraCapture(
          photo.uri,
          sensorAvailable === false || stability >= 0.9,
        ),
      );
    } catch (captureError) {
      setError(
        captureError instanceof Error
          ? captureError.message
          : "Capture failed.",
      );
    } finally {
      await removeTemporaryFile(rawPhotoUri);
      setBusy(false);
    }
  };

  const askForCamera = async () => {
    setError(null);
    try {
      await requestPermission();
    } catch {
      setError(
        "Camera permission could not be requested. Use a saved photo or open device settings.",
      );
    }
  };

  const choosePhoto = async () => {
    setBusy(true);
    setBusyLabel("Opening photo library...");
    setError(null);
    let pickerTemporaryUri: string | null = null;
    try {
      const permission =
        await ImagePicker.requestMediaLibraryPermissionsAsync();
      setPhotoPermissionBlocked(
        !permission.granted && permission.canAskAgain === false,
      );
      if (!permission.granted) {
        setError(
          permission.canAskAgain
            ? "Photo access was not granted. You can try again or use the camera."
            : "Photo access is disabled. Open device settings to allow selected-photo access.",
        );
        return;
      }
      const selection = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ["images"],
        allowsEditing: false,
        allowsMultipleSelection: false,
        exif: false,
        quality: 1,
        selectionLimit: 1,
      });
      if (selection.canceled) return;
      const asset = selection.assets[0];
      if (!asset?.uri) {
        throw new Error("The photo library did not return an image.");
      }
      pickerTemporaryUri = asset.uri;
      setBusyLabel("Checking selected image...");
      await prepareCandidate(await sanitizeSelectedImage(asset.uri));
    } catch (selectionError) {
      setError(
        selectionError instanceof Error
          ? selectionError.message
          : "The selected image could not be prepared.",
      );
    } finally {
      await removePickerTemporaryCopy(pickerTemporaryUri);
      setBusy(false);
    }
  };

  const retake = async () => {
    await removeTemporaryFile(candidate?.capture.uri);
    setCandidate(null);
    setRejectedQuality(null);
    setMouthOnlyConfirmed(false);
    setRegionConfirmed(false);
  };

  const acceptAndAnalyze = async () => {
    if (
      !candidate ||
      !activeSessionId ||
      !candidate.quality.accepted ||
      !mouthOnlyConfirmed ||
      !regionConfirmed
    )
      return;
    setBusy(true);
    setBusyLabel("Protecting and uploading...");
    setError(null);
    const captureId = Crypto.randomUUID();
    let encryptedUri: string | null = null;
    let captureCommitted = false;
    try {
      encryptedUri = await encryptFile(
        candidate.capture.uri,
        `capture:${captureId}`,
      );
      const analysis = await analyzeCapture({
        captureId,
        selectedRegion: region,
        imageUri: candidate.capture.uri,
        mimeType: candidate.capture.mimeType,
        inputOrigin: "live_capture",
        localQuality: candidate.quality,
      });
      const serverRejectionReasons = captureStorageRejectionReasons(
        analysis,
        region,
      );
      if (serverRejectionReasons.length > 0) {
        setRejectedQuality({
          ...analysis.quality,
          accepted: false,
          reasons: serverRejectionReasons,
        });
        await removeTemporaryFile(candidate.capture.uri);
        setCandidate(null);
        setMouthOnlyConfirmed(false);
        return;
      }
      const record: CaptureRecord = {
        id: captureId,
        sessionId: activeSessionId,
        region,
        capturedAt: new Date().toISOString(),
        encryptedUri,
        mimeType: candidate.capture.mimeType,
        inputOrigin: "live_capture",
        captureSource: candidate.capture.source,
        privacyConfirmedByUser: mouthOnlyConfirmed,
        regionConfirmedByUser: regionConfirmed,
        quality: analysis.quality,
      };
      await addCapture(record, analysis);
      captureCommitted = true;
      await removeTemporaryFile(candidate.capture.uri);
      router.replace({
        pathname: "/result/[captureId]",
        params: { captureId },
      });
    } catch (captureError) {
      setError(
        captureError instanceof Error
          ? captureError.message
          : "Could not protect and analyze this capture.",
      );
    } finally {
      if (!captureCommitted) {
        await removeProtectedFile(encryptedUri);
      }
      setBusy(false);
    }
  };

  return (
    <Screen
      title={detail.shortLabel}
      eyebrow="Guided capture"
      action={
        <Button
          label="Back"
          variant="ghost"
          disabled={busy}
          onPress={() => router.back()}
        />
      }
    >
      {!candidate ? (
        <>
          <View style={[styles.cameraShell, { backgroundColor: theme.navy }]}>
            {permission?.granted ? (
              <CameraView
                ref={cameraRef}
                style={StyleSheet.absoluteFill}
                facing="back"
              />
            ) : (
              <View style={styles.permission}>
                <Text style={styles.permissionText}>
                  {permission?.canAskAgain === false
                    ? "Camera access is disabled in device settings. You can still choose a saved photo."
                    : "Allow camera access to capture a new image, or choose a saved photo below."}
                </Text>
                <Button
                  label={
                    permission?.canAskAgain === false
                      ? "Open device settings"
                      : "Allow camera"
                  }
                  onPress={() => {
                    if (permission?.canAskAgain === false) {
                      void Linking.openSettings();
                    } else {
                      void askForCamera();
                    }
                  }}
                />
              </View>
            )}
            {permission?.granted && ghostUri ? (
              <View pointerEvents="none" style={styles.ghostLayer}>
                <Image
                  accessible={false}
                  source={{ uri: ghostUri }}
                  resizeMode="cover"
                  style={StyleSheet.absoluteFill}
                />
              </View>
            ) : null}
            {permission?.granted ? (
              <View pointerEvents="none" style={styles.guide}>
                <CaptureGuideOverlay region={region} />
                {ghostUri ? (
                  <Text style={styles.ghostLabel}>
                    Earlier scan alignment guide
                  </Text>
                ) : null}
                <Text style={styles.instruction}>
                  {detail.captureInstruction}
                </Text>
                <StabilityIndicator progress={stability} />
              </View>
            ) : null}
          </View>
          <Button
            label="Capture live image"
            icon="camera"
            loading={busy}
            loadingLabel={busyLabel}
            disabled={
              !permission?.granted ||
              (sensorAvailable !== false && stability < 0.9)
            }
            onPress={() => {
              void takePhoto();
            }}
          />
          <Button
            label="Choose a saved mouth image"
            icon="images-outline"
            variant="secondary"
            loading={busy}
            loadingLabel={busyLabel}
            onPress={() => {
              void choosePhoto();
            }}
          />
          {priorCapture && permission?.granted ? (
            <Button
              label={
                ghostEnabled
                  ? "Hide earlier alignment guide"
                  : "Show earlier alignment guide"
              }
              icon={ghostEnabled ? "eye-off-outline" : "layers-outline"}
              variant="secondary"
              disabled={busy}
              onPress={() => setGhostEnabled((value) => !value)}
            />
          ) : null}
          {ghostError ? (
            <Text style={[styles.error, { color: theme.danger }]}>
              {ghostError}
            </Text>
          ) : null}
          {priorCapture ? (
            <Text style={[styles.sensorNote, { color: theme.secondaryText }]}>
              The optional guide is a locally decrypted earlier image from a
              different scan session. It is never added to the new photograph
              and is removed from temporary storage when hidden or when you
              leave this screen.
            </Text>
          ) : null}
          {sensorAvailable === false ? (
            <Text style={[styles.sensorNote, { color: theme.secondaryText }]}>
              Motion sensing is unavailable on this device. OralSight will rely
              on the post-capture focus and exposure checks.
            </Text>
          ) : null}
          <Text style={[styles.privacy, { color: theme.secondaryText }]}>
            Camera and library images are re-encoded to remove metadata and
            checked on this device for image quality and visible faces before
            protected storage or upload. You must also confirm the privacy
            framing before anything is sent.
          </Text>
          {settings.caregiverMode ? (
            <Card accent="teal">
              <SectionTitle
                title="Caregiver-assisted capture"
                subtitle="Ask the person to stay seated, explain each step, and stop if they are uncomfortable. Confirm their permission before every image."
                icon="people-outline"
              />
            </Card>
          ) : null}
          {rejectedQuality ? (
            <Card accent="coral">
              <SectionTitle
                title="Image discarded - retake needed"
                subtitle="The rejected temporary image has already been deleted."
                icon="refresh-circle-outline"
              />
              <MetricBar label="Focus" value={rejectedQuality.blurScore} />
              <MetricBar
                label="Exposure"
                value={rejectedQuality.exposureScore}
              />
              <MetricBar
                label="Glare control"
                value={1 - rejectedQuality.glareScore}
              />
              <MetricBar
                label="Visibility"
                value={1 - rejectedQuality.obstructionScore}
              />
              {rejectedQuality.reasons.map((reason) => (
                <Text
                  key={reason}
                  style={[styles.reason, { color: theme.danger }]}
                >
                  • {humanizeResultReason(reason)}
                </Text>
              ))}
            </Card>
          ) : null}
        </>
      ) : (
        <>
          <Image
            accessible
            accessibilityLabel={`Preview of ${detail.label} before protected storage`}
            source={{ uri: candidate.capture.uri }}
            resizeMode="contain"
            style={[styles.preview, { backgroundColor: theme.navy }]}
          />
          <Card accent={candidate.quality.accepted ? "teal" : "coral"}>
            <SectionTitle
              title={
                candidate.quality.accepted
                  ? "Image quality accepted"
                  : "Retake needed"
              }
              subtitle={`${candidate.capture.source === "camera" ? "Camera image" : "Selected photo"}, metadata removed, ${candidate.capture.width} by ${candidate.capture.height} pixels`}
              icon={
                candidate.quality.accepted
                  ? "checkmark-circle-outline"
                  : "refresh-circle-outline"
              }
            />
            <MetricBar label="Focus" value={candidate.quality.blurScore} />
            <MetricBar
              label="Exposure"
              value={candidate.quality.exposureScore}
            />
            <MetricBar
              label="Glare control"
              value={1 - candidate.quality.glareScore}
            />
            <MetricBar
              label="Visibility"
              value={1 - candidate.quality.obstructionScore}
            />
            {candidate.quality.reasons.map((reason) => (
              <Text
                key={reason}
                style={[styles.reason, { color: theme.danger }]}
              >
                • {humanizeResultReason(reason)}
              </Text>
            ))}
          </Card>
          {candidate.quality.accepted ? (
            <Card accent="amber">
              <SectionTitle
                title="Confirm before upload"
                subtitle="The on-device face check passed. Your confirmation is still required because an automated check can miss identifying details. The selected mouth region is checked again by the server before the image is accepted."
                icon="shield-outline"
              />
              <ChoiceChip
                label="I confirm this frame shows mouth tissue only: no full face, eyes, name, or identifying surroundings are visible, and I have permission to capture it"
                selected={mouthOnlyConfirmed}
                onPress={() => setMouthOnlyConfirmed((value) => !value)}
                accessibilityRole="checkbox"
              />
              <ChoiceChip
                label={`I confirm this image shows ${detail.label}`}
                selected={regionConfirmed}
                onPress={() => setRegionConfirmed((value) => !value)}
                accessibilityRole="checkbox"
              />
            </Card>
          ) : null}
          {candidate.quality.accepted ? (
            <Button
              label="Protect image & analyze"
              icon="shield-checkmark-outline"
              loading={busy}
              loadingLabel={busyLabel}
              disabled={
                !mouthOnlyConfirmed ||
                !regionConfirmed ||
                !activeSessionId ||
                busy
              }
              onPress={() => {
                void acceptAndAnalyze();
              }}
            />
          ) : null}
          <Button
            label="Discard and retake"
            icon="refresh"
            variant="ghost"
            disabled={busy}
            onPress={() => {
              void retake();
            }}
          />
        </>
      )}
      {error ? (
        <View style={styles.errorGroup}>
          <Text
            accessibilityRole="alert"
            style={[styles.error, { color: theme.danger }]}
          >
            {error}
          </Text>
          {photoPermissionBlocked ? (
            <Button
              label="Open device settings"
              variant="ghost"
              onPress={() => {
                void Linking.openSettings();
              }}
            />
          ) : null}
        </View>
      ) : null}
    </Screen>
  );
}

const styles = StyleSheet.create({
  cameraShell: {
    flex: 1,
    minHeight: 390,
    borderRadius: 16,
    overflow: "hidden",
  },
  permission: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    padding: 30,
    gap: 16,
  },
  permissionText: { color: "#FFFFFF", textAlign: "center", lineHeight: 20 },
  guide: {
    position: "absolute",
    top: 0,
    right: 0,
    bottom: 0,
    left: 0,
    alignItems: "center",
    justifyContent: "center",
    padding: 18,
    gap: 18,
  },
  ghostLayer: {
    position: "absolute",
    top: 0,
    right: 0,
    bottom: 0,
    left: 0,
    opacity: 0.32,
  },
  ghostLabel: {
    color: "#FFFFFF",
    fontSize: 12,
    lineHeight: 17,
    fontWeight: "900",
    textAlign: "center",
    backgroundColor: "rgba(11,122,117,0.82)",
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 999,
  },
  instruction: {
    color: "#FFFFFF",
    fontSize: 13,
    lineHeight: 18,
    fontWeight: "700",
    textAlign: "center",
    backgroundColor: "rgba(0,0,0,0.52)",
    padding: 9,
    borderRadius: 10,
  },
  privacy: { fontSize: 11, lineHeight: 16, textAlign: "center" },
  sensorNote: { fontSize: 12, lineHeight: 18, textAlign: "center" },
  preview: { width: "100%", height: 290, borderRadius: 16 },
  reason: { fontSize: 13, lineHeight: 19, fontWeight: "700" },
  error: { textAlign: "center", fontSize: 13, fontWeight: "700" },
  errorGroup: { gap: 8 },
});
