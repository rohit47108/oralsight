import { useEffect, useRef, useState } from "react";
import { useFaceDetection } from "@infinitered/react-native-mlkit-face-detection";
import { router, useLocalSearchParams } from "expo-router";
import { CameraView, useCameraPermissions } from "expo-camera";
import { useVideoPlayer } from "expo-video";
import { ImageManipulator, SaveFormat } from "expo-image-manipulator";
import { Accelerometer } from "expo-sensors";
import * as Crypto from "expo-crypto";
import * as Haptics from "expo-haptics";
import * as ImagePicker from "expo-image-picker";
import * as Speech from "expo-speech";
import { Image, Linking, StyleSheet, Text, View } from "react-native";
import {
  MOUTH_REGION_DETAILS,
  captureAngleSchema,
  mouthRegionSchema,
  type CaptureAngle,
  type QualityResult,
} from "@oralsight/contracts";

import { CaptureGuideOverlay } from "@/components/CaptureGuideOverlay";
import { CaptureGuidanceMetrics } from "@/components/CaptureGuidanceMetrics";
import { Screen } from "@/components/Screen";
import { StabilityIndicator } from "@/components/StabilityIndicator";
import {
  createCaptureGuidanceSnapshot,
  type CaptureGuidanceSnapshot,
  type CaptureGuidanceSource,
  type MotionSample,
} from "@/components/captureGuidance";
import {
  Button,
  Card,
  ChoiceChip,
  MetricBar,
  SectionTitle,
} from "@/components/Ui";
import { captureStorageRejectionReasons } from "@/lib/analysisPolicy";
import { analyzeCapture } from "@/lib/api";
import { captureGuideSpec } from "@/lib/captureGuide";
import {
  qualityForSanitizedCapture,
  sanitizeCameraCapture,
  sanitizeSelectedImage,
  sanitizeVideoFrame,
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
import {
  selectBestSweepFrames,
  sweepFrameRequests,
  sweepInstruction,
  type SweepAngle,
} from "@/lib/videoSweep";
import { useOralSightStore } from "@/store/useOralSightStore";
import { useAppTheme } from "@/theme";
import type { CaptureRecord } from "@/types";
import { CALIBRATION_CARD_VERSION, PUBLIC_WEB_URL } from "@/constants";

interface CandidateState {
  capture: SanitizedCapture;
  quality: QualityResult;
  angle: CaptureAngle;
  mediaKind: "image" | "video_frame";
  sourceVideoDurationMs?: number;
  frameTimeMs?: number;
  guidance: CaptureGuidanceSnapshot;
}

interface SweepCandidateState extends CandidateState {
  angle: SweepAngle;
  mediaKind: "video_frame";
  sourceVideoDurationMs: number;
  frameTimeMs: number;
}

export default function CaptureRoute() {
  const theme = useAppTheme();
  const params = useLocalSearchParams<{ region?: string; angle?: string }>();
  const parsedRegion = mouthRegionSchema.safeParse(params.region);
  const region = parsedRegion.success ? parsedRegion.data : null;
  const detail = MOUTH_REGION_DETAILS.find((item) => item.id === region);
  const activeSessionId = useOralSightStore((state) => state.activeSessionId);
  const sessions = useOralSightStore((state) => state.sessions);
  const settings = useOralSightStore((state) => state.settings);
  const captures = useOralSightStore((state) => state.captures);
  const addCaptures = useOralSightStore((state) => state.addCaptures);
  const faceDetector = useFaceDetection();
  const cameraRef = useRef<CameraView>(null);
  const videoPlayer = useVideoPlayer(null);
  const recordingStartedAt = useRef<number | null>(null);
  const previousMotion = useRef({ x: 0, y: 0, z: 1 });
  const latestMotion = useRef<MotionSample | null>(null);
  const stableSamples = useRef(0);
  const autoCaptureAction = useRef<() => void>(() => undefined);
  const autoCaptureTriggered = useRef(false);
  const [permission, requestPermission] = useCameraPermissions();
  const [stability, setStability] = useState(0);
  const [motionReading, setMotionReading] = useState<MotionSample | null>(null);
  const [sensorAvailable, setSensorAvailable] = useState<boolean | null>(null);
  const [candidate, setCandidate] = useState<CandidateState | null>(null);
  const [sweepCandidates, setSweepCandidates] = useState<SweepCandidateState[]>(
    [],
  );
  const [recording, setRecording] = useState(false);
  const [sweepElapsedMs, setSweepElapsedMs] = useState(0);
  const [rejectedQuality, setRejectedQuality] = useState<QualityResult | null>(
    null,
  );
  const [rejectedGuidance, setRejectedGuidance] =
    useState<CaptureGuidanceSnapshot | null>(null);
  const [mouthOnlyConfirmed, setMouthOnlyConfirmed] = useState(false);
  const [regionConfirmed, setRegionConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [busyLabel, setBusyLabel] = useState("Working...");
  const [photoPermissionBlocked, setPhotoPermissionBlocked] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ghostEnabled, setGhostEnabled] = useState(false);
  const [mirrorGuide, setMirrorGuide] = useState(false);
  const [autoCaptureEnabled, setAutoCaptureEnabled] = useState(false);
  const [calibrationEnabled, setCalibrationEnabled] = useState(false);
  const [calibrationPlaneConfirmed, setCalibrationPlaneConfirmed] =
    useState(false);
  const [ghostUri, setGhostUri] = useState<string | null>(null);
  const [ghostError, setGhostError] = useState<string | null>(null);
  const session = sessions.find((item) => item.id === activeSessionId) ?? null;
  const parsedAngle = captureAngleSchema.safeParse(params.angle);
  const requestedAngle = parsedAngle.success ? parsedAngle.data : null;
  const captureAngle: CaptureAngle | null =
    session?.protocol === "standard_eight_region"
      ? "primary"
      : session?.protocol === "guided_video_sweep"
        ? "straight"
        : requestedAngle && requestedAngle !== "primary"
          ? requestedAngle
          : null;
  const isSweep = session?.protocol === "guided_video_sweep";
  const preparedCandidates =
    sweepCandidates.length > 0 ? sweepCandidates : candidate ? [candidate] : [];
  const priorCapture =
    region === null
      ? null
      : latestPriorAcceptedCapture(
          captures.filter((capture) => capture.angle === captureAngle),
          activeSessionId,
          region,
        );

  useEffect(() => {
    let active = true;
    let subscription: { remove: () => void } | null = null;
    void Accelerometer.isAvailableAsync()
      .then((available) => {
        if (!active) return;
        setSensorAvailable(available);
        if (!available) {
          setStability(1);
          latestMotion.current = null;
          setMotionReading(null);
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
          latestMotion.current = motion;
          setMotionReading(motion);
          previousMotion.current = motion;
        });
      })
      .catch(() => {
        if (!active) return;
        setSensorAvailable(false);
        setStability(1);
        latestMotion.current = null;
        setMotionReading(null);
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

  useEffect(() => {
    const uris = new Set([
      ...(candidate ? [candidate.capture.uri] : []),
      ...sweepCandidates.map((item) => item.capture.uri),
    ]);
    return () => {
      for (const uri of uris) void removeTemporaryFile(uri);
    };
  }, [candidate, sweepCandidates]);

  useEffect(() => {
    if (!recording) return undefined;
    const interval = setInterval(() => {
      const startedAt = recordingStartedAt.current;
      setSweepElapsedMs(
        startedAt ? Math.min(6_000, Date.now() - startedAt) : 0,
      );
    }, 100);
    return () => clearInterval(interval);
  }, [recording]);

  useEffect(() => {
    if (stability < 0.75) autoCaptureTriggered.current = false;
    if (
      !autoCaptureEnabled ||
      isSweep ||
      !permission?.granted ||
      busy ||
      candidate ||
      sweepCandidates.length > 0 ||
      stability < 0.98 ||
      autoCaptureTriggered.current
    ) {
      return undefined;
    }
    autoCaptureTriggered.current = true;
    const timeout = setTimeout(() => autoCaptureAction.current(), 350);
    return () => clearTimeout(timeout);
  }, [
    autoCaptureEnabled,
    busy,
    candidate,
    isSweep,
    permission?.granted,
    stability,
    sweepCandidates.length,
  ]);

  useEffect(() => {
    setGhostUri(null);
    setGhostError(null);
    if (
      !ghostEnabled ||
      !priorCapture?.encryptedUri ||
      preparedCandidates.length > 0
    ) {
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
    preparedCandidates.length,
    ghostEnabled,
    priorCapture?.encryptedUri,
    priorCapture?.id,
    priorCapture?.mimeType,
  ]);

  if (!region || !detail || !session || !captureAngle) {
    return (
      <Screen title="Unsupported region">
        <Card accent="coral">
          <Text style={{ color: theme.text }}>
            The requested region, angle, or scan session is not available.
          </Text>
          <Button label="Return" onPress={() => router.back()} />
        </Card>
      </Screen>
    );
  }

  const guidanceSnapshot = (
    source: CaptureGuidanceSource,
  ): CaptureGuidanceSnapshot =>
    createCaptureGuidanceSnapshot({
      motion: source === "imported_photo" ? null : latestMotion.current,
      stability,
      sensorAvailable: source === "imported_photo" ? false : sensorAvailable,
      targetWidthPercent: captureGuideSpec(region).targetWidthPercent,
      source,
    });

  const inspectCapture = async (
    capture: SanitizedCapture,
  ): Promise<{ capture: SanitizedCapture; quality: QualityResult }> => {
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
    const checkedCapture = withFaceDetectionResult(
      capture,
      detection.faces.length > 0,
    );
    return {
      capture: checkedCapture,
      quality: qualityForSanitizedCapture(checkedCapture),
    };
  };

  const prepareCandidate = async (
    capture: SanitizedCapture,
    guidance: CaptureGuidanceSnapshot,
  ) => {
    setBusyLabel("Checking privacy and image quality...");
    let inspected: Awaited<ReturnType<typeof inspectCapture>>;
    try {
      inspected = await inspectCapture(capture);
    } catch (privacyError) {
      await removeTemporaryFile(capture.uri);
      setCandidate(null);
      setSweepCandidates([]);
      setRejectedQuality(null);
      setRejectedGuidance(null);
      setMouthOnlyConfirmed(false);
      setRegionConfirmed(false);
      setCalibrationPlaneConfirmed(false);
      throw new Error(
        privacyError instanceof Error
          ? `${privacyError.message} The image was deleted and was not saved or uploaded.`
          : "The on-device privacy check failed. The image was deleted and was not saved or uploaded.",
      );
    }
    const { capture: checkedCapture, quality } = inspected;
    if (settings.haptics) {
      await Haptics.notificationAsync(
        quality.accepted
          ? Haptics.NotificationFeedbackType.Success
          : Haptics.NotificationFeedbackType.Warning,
      ).catch(() => undefined);
    }
    if (!quality.accepted) {
      await removeTemporaryFile(checkedCapture.uri);
      setCandidate(null);
      setSweepCandidates([]);
      setRejectedQuality(quality);
      setRejectedGuidance(guidance);
      setMouthOnlyConfirmed(false);
      setRegionConfirmed(false);
      setCalibrationPlaneConfirmed(false);
      return;
    }
    setRejectedQuality(null);
    setRejectedGuidance(null);
    setSweepCandidates([]);
    setCandidate({
      capture: checkedCapture,
      quality,
      angle: captureAngle,
      mediaKind: "image",
      guidance,
    });
    setMouthOnlyConfirmed(false);
    setRegionConfirmed(false);
    setCalibrationPlaneConfirmed(false);
  };

  const takePhoto = async () => {
    setError(null);
    setBusy(true);
    setBusyLabel("Capturing image...");
    let rawPhotoUri: string | null = null;
    const guidance = guidanceSnapshot("live_camera");
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
        guidance,
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
  autoCaptureAction.current = () => {
    void takePhoto();
  };

  const recordSweep = async () => {
    setError(null);
    setRejectedQuality(null);
    setRejectedGuidance(null);
    setBusy(true);
    setBusyLabel("Recording guided sweep...");
    setRecording(true);
    setSweepElapsedMs(0);
    recordingStartedAt.current = Date.now();
    let rawVideoUri: string | null = null;
    const renderedFrameUris: string[] = [];
    const inspectedFrames: SweepCandidateState[] = [];
    const sweepGuidance = guidanceSnapshot("sweep_start");
    let selectedUris = new Set<string>();
    try {
      const video = await cameraRef.current?.recordAsync({
        maxDuration: 6,
        maxFileSize: 20_000_000,
      });
      const durationMs = Math.min(
        60_000,
        Date.now() - (recordingStartedAt.current ?? Date.now()),
      );
      if (!video?.uri) throw new Error("The camera did not return a sweep.");
      rawVideoUri = video.uri;
      const requests = sweepFrameRequests(durationMs);
      setBusyLabel("Selecting the clearest frames...");
      await videoPlayer.replaceAsync({ uri: video.uri });
      const thumbnails = await videoPlayer.generateThumbnailsAsync(
        requests.map((request) => request.timeMs / 1_000),
        { maxWidth: 2_048, maxHeight: 2_048 },
      );
      if (thumbnails.length !== requests.length) {
        throw new Error(
          "The recorded sweep did not produce every needed frame.",
        );
      }
      for (const [index, thumbnail] of thumbnails.entries()) {
        const request = requests[index];
        if (!request) continue;
        const context = ImageManipulator.manipulate(thumbnail);
        const rendered = await context.renderAsync();
        const saved = await rendered.saveAsync({
          compress: 0.92,
          format: SaveFormat.JPEG,
        });
        renderedFrameUris.push(saved.uri);
        const sanitized = await sanitizeVideoFrame(saved.uri);
        try {
          const inspected = await inspectCapture(sanitized);
          inspectedFrames.push({
            ...inspected,
            angle: request.angle,
            mediaKind: "video_frame",
            sourceVideoDurationMs: durationMs,
            frameTimeMs: request.timeMs,
            guidance: sweepGuidance,
          });
        } catch (privacyError) {
          await removeTemporaryFile(sanitized.uri);
          throw new Error(
            privacyError instanceof Error
              ? `${privacyError.message} The sweep was deleted and was not saved or uploaded.`
              : "The on-device privacy check could not inspect the sweep.",
          );
        }
      }
      const best = selectBestSweepFrames(inspectedFrames);
      if (best.length !== 3) {
        const firstRejected = inspectedFrames.find(
          (frame) => !frame.quality.accepted,
        );
        setRejectedQuality(firstRejected?.quality ?? null);
        setRejectedGuidance(firstRejected?.guidance ?? sweepGuidance);
        throw new Error(
          "The sweep did not contain a clear straight, left, and right frame. Record it again more slowly.",
        );
      }
      selectedUris = new Set(best.map((frame) => frame.capture.uri));
      await Promise.all(
        inspectedFrames
          .filter((frame) => !selectedUris.has(frame.capture.uri))
          .map((frame) => removeTemporaryFile(frame.capture.uri)),
      );
      setCandidate(best[0] ?? null);
      setSweepCandidates(best);
      setMouthOnlyConfirmed(false);
      setRegionConfirmed(false);
      setCalibrationPlaneConfirmed(false);
      if (settings.haptics) {
        await Haptics.notificationAsync(
          Haptics.NotificationFeedbackType.Success,
        ).catch(() => undefined);
      }
    } catch (sweepError) {
      setCandidate(null);
      setSweepCandidates([]);
      setMouthOnlyConfirmed(false);
      setRegionConfirmed(false);
      setCalibrationPlaneConfirmed(false);
      setError(
        sweepError instanceof Error
          ? sweepError.message
          : "The guided sweep could not be prepared.",
      );
    } finally {
      await videoPlayer.replaceAsync(null).catch(() => undefined);
      await Promise.all([
        removeTemporaryFile(rawVideoUri),
        ...renderedFrameUris.map((uri) => removeTemporaryFile(uri)),
        ...inspectedFrames
          .filter((frame) => !selectedUris.has(frame.capture.uri))
          .map((frame) => removeTemporaryFile(frame.capture.uri)),
      ]);
      recordingStartedAt.current = null;
      setRecording(false);
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
      await prepareCandidate(
        await sanitizeSelectedImage(asset.uri),
        guidanceSnapshot("imported_photo"),
      );
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
    await Promise.all(
      preparedCandidates.map((item) => removeTemporaryFile(item.capture.uri)),
    );
    setCandidate(null);
    setSweepCandidates([]);
    setRejectedQuality(null);
    setRejectedGuidance(null);
    setMouthOnlyConfirmed(false);
    setRegionConfirmed(false);
    setCalibrationPlaneConfirmed(false);
  };

  const acceptAndAnalyze = async () => {
    if (
      preparedCandidates.length === 0 ||
      !activeSessionId ||
      preparedCandidates.some((item) => !item.quality.accepted) ||
      !mouthOnlyConfirmed ||
      !regionConfirmed
    )
      return;
    setBusy(true);
    setBusyLabel("Protecting and uploading...");
    setError(null);
    const protectedUris: string[] = [];
    let captureCommitted = false;
    try {
      const entries: Array<{
        capture: CaptureRecord;
        analysis: Awaited<ReturnType<typeof analyzeCapture>>;
      }> = [];
      for (const [index, prepared] of preparedCandidates.entries()) {
        setBusyLabel(
          preparedCandidates.length === 1
            ? "Protecting and analyzing..."
            : `Protecting and analyzing view ${index + 1} of ${preparedCandidates.length}...`,
        );
        const captureId = Crypto.randomUUID();
        const encryptedUri = await encryptFile(
          prepared.capture.uri,
          `capture:${captureId}`,
        );
        protectedUris.push(encryptedUri);
        const analysis = await analyzeCapture({
          captureId,
          selectedRegion: region,
          imageUri: prepared.capture.uri,
          mimeType: prepared.capture.mimeType,
          inputOrigin: "live_capture",
          localQuality: prepared.quality,
          ...(calibrationEnabled
            ? {
                calibration: {
                  cardVersion: CALIBRATION_CARD_VERSION,
                  markerId: 17,
                  markerSideMm: 20,
                  planeConfirmed: calibrationPlaneConfirmed,
                } as const,
              }
            : {}),
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
          setRejectedGuidance(prepared.guidance);
          await Promise.all(
            preparedCandidates.map((item) =>
              removeTemporaryFile(item.capture.uri),
            ),
          );
          setCandidate(null);
          setSweepCandidates([]);
          setMouthOnlyConfirmed(false);
          setRegionConfirmed(false);
          setCalibrationPlaneConfirmed(false);
          throw new Error(
            "One view did not pass the service anatomy and quality checks. The entire set was discarded.",
          );
        }
        entries.push({
          capture: {
            id: captureId,
            sessionId: activeSessionId,
            region,
            angle: prepared.angle,
            mediaKind: prepared.mediaKind,
            capturedAt: new Date().toISOString(),
            encryptedUri,
            mimeType: prepared.capture.mimeType,
            inputOrigin: "live_capture",
            captureSource: prepared.capture.source,
            ...(prepared.sourceVideoDurationMs === undefined
              ? {}
              : { sourceVideoDurationMs: prepared.sourceVideoDurationMs }),
            ...(prepared.frameTimeMs === undefined
              ? {}
              : { frameTimeMs: prepared.frameTimeMs }),
            ...(calibrationEnabled
              ? {
                  calibrationRequested: true,
                  calibrationPlaneConfirmed: true,
                  calibrationCardVersion: CALIBRATION_CARD_VERSION,
                }
              : {}),
            privacyConfirmedByUser: mouthOnlyConfirmed,
            regionConfirmedByUser: regionConfirmed,
            captureGuidance: prepared.guidance,
            quality: analysis.quality,
          },
          analysis,
        });
      }
      await addCaptures(entries);
      captureCommitted = true;
      await Promise.all(
        preparedCandidates.map((item) => removeTemporaryFile(item.capture.uri)),
      );
      const primary =
        entries.find(
          ({ capture }) =>
            capture.angle === "primary" || capture.angle === "straight",
        ) ?? entries[0];
      if (!primary) throw new Error("The accepted capture set is empty.");
      router.replace({
        pathname: "/result/[captureId]",
        params: { captureId: primary.capture.id },
      });
    } catch (captureError) {
      setError(
        captureError instanceof Error
          ? captureError.message
          : "Could not protect and analyze this capture.",
      );
    } finally {
      if (!captureCommitted) {
        await Promise.all(protectedUris.map((uri) => removeProtectedFile(uri)));
      }
      setBusy(false);
    }
  };

  return (
    <Screen
      title={detail.shortLabel}
      eyebrow={
        isSweep
          ? "Six-second guided sweep"
          : `${captureAngle.replaceAll("_", " ")} view`
      }
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
                mode={isSweep ? "video" : "picture"}
                mute
                videoQuality="720p"
              />
            ) : (
              <View style={styles.permission}>
                <Text style={styles.permissionText}>
                  {permission?.canAskAgain === false
                    ? `Camera access is disabled in device settings.${isSweep ? " A guided sweep requires the live camera." : " You can still choose a saved photo."}`
                    : `Allow camera access to ${isSweep ? "record a short guided sweep" : "capture a new image"}${isSweep ? "." : ", or choose a saved photo below."}`}
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
                <View style={mirrorGuide ? styles.mirroredOverlay : undefined}>
                  <CaptureGuideOverlay region={region} />
                </View>
                {ghostUri ? (
                  <Text style={styles.ghostLabel}>
                    Earlier scan alignment guide
                  </Text>
                ) : null}
                <Text style={styles.instruction}>
                  {recording
                    ? sweepInstruction(sweepElapsedMs / 6_000)
                    : isSweep
                      ? `${detail.captureInstruction} Then move slowly from straight to left to right.`
                      : detail.captureInstruction}
                </Text>
                {recording ? (
                  <Text style={styles.recordingLabel}>
                    Recording · {(sweepElapsedMs / 1_000).toFixed(1)} of 6.0
                    seconds
                  </Text>
                ) : null}
                <StabilityIndicator
                  progress={stability}
                  available={sensorAvailable}
                />
                <CaptureGuidanceMetrics
                  snapshot={createCaptureGuidanceSnapshot({
                    motion: motionReading,
                    stability,
                    sensorAvailable,
                    targetWidthPercent:
                      captureGuideSpec(region).targetWidthPercent,
                    source: "live_camera",
                  })}
                  {...(priorCapture
                    ? {
                        baselineSnapshot: priorCapture.captureGuidance ?? null,
                        baselineExposureScore:
                          priorCapture.quality.exposureScore,
                        baselineMillimetersPerPixel:
                          calibratedScale(priorCapture),
                      }
                    : {})}
                  tone="camera"
                />
              </View>
            ) : null}
          </View>
          {isSweep ? (
            recording ? (
              <Button
                label="Stop and check frames"
                icon="stop-circle-outline"
                variant="secondary"
                onPress={() => cameraRef.current?.stopRecording()}
              />
            ) : (
              <Button
                label="Record guided sweep"
                icon="videocam-outline"
                loading={busy}
                loadingLabel={busyLabel}
                disabled={
                  !permission?.granted ||
                  (sensorAvailable !== false && stability < 0.9)
                }
                onPress={() => {
                  void recordSweep();
                }}
              />
            )
          ) : (
            <>
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
            </>
          )}
          <View style={styles.captureOptions}>
            {!isSweep ? (
              <ChoiceChip
                label="Auto-capture when the stability ring fills"
                selected={autoCaptureEnabled}
                onPress={() => setAutoCaptureEnabled((value) => !value)}
                accessibilityRole="checkbox"
              />
            ) : null}
            <ChoiceChip
              label="Mirror the anatomical guide"
              selected={mirrorGuide}
              onPress={() => setMirrorGuide((value) => !value)}
              accessibilityRole="checkbox"
            />
          </View>
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
            {isSweep
              ? "The raw sweep stays in temporary device storage while OralSight selects quality-checked frames, then is deleted. Only the three confirmed frames can be protected or uploaded."
              : "Camera and library images are re-encoded to remove metadata and checked on this device for image quality and visible faces before protected storage or upload. You must also confirm the privacy framing before anything is sent."}
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
          <Card accent={calibrationEnabled ? "teal" : undefined}>
            <SectionTitle
              title="Optional physical scale card"
              subtitle="Use the printed 20 mm OralSight marker only when someone can hold it beside the target without touching tissue. The marker and target must stay in the same plane."
              icon="resize-outline"
            />
            <ChoiceChip
              label="Include the versioned scale card in this capture"
              selected={calibrationEnabled}
              onPress={() => {
                setCalibrationEnabled((value) => {
                  if (value) setCalibrationPlaneConfirmed(false);
                  return !value;
                });
              }}
              accessibilityRole="checkbox"
            />
            {PUBLIC_WEB_URL ? (
              <Button
                label="Open printable calibration card"
                icon="print-outline"
                variant="ghost"
                onPress={() => {
                  void Linking.openURL(`${PUBLIC_WEB_URL}/calibration`);
                }}
              />
            ) : null}
            <Text style={[styles.sensorNote, { color: theme.secondaryText }]}>
              A millimeter estimate is shown only if the exact marker is
              detected and every calibration gate passes. Otherwise the app
              keeps image-normalized approximate measurements.
            </Text>
          </Card>
          {rejectedQuality ? (
            <Card accent="coral">
              <SectionTitle
                title="Capture discarded · retake needed"
                subtitle="Rejected temporary images and raw video have already been deleted."
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
              {rejectedGuidance ? (
                <CaptureGuidanceMetrics
                  snapshot={rejectedGuidance}
                  exposureScore={rejectedQuality.exposureScore}
                  {...(priorCapture
                    ? {
                        baselineSnapshot: priorCapture.captureGuidance ?? null,
                        baselineExposureScore:
                          priorCapture.quality.exposureScore,
                        baselineMillimetersPerPixel:
                          calibratedScale(priorCapture),
                      }
                    : {})}
                />
              ) : null}
            </Card>
          ) : null}
        </>
      ) : (
        <>
          {sweepCandidates.length > 0 ? (
            <View style={styles.sweepPreviewList}>
              {sweepCandidates.map((item) => (
                <View key={item.angle} style={styles.sweepPreviewItem}>
                  <Image
                    accessible
                    accessibilityLabel={`${item.angle.replaceAll("_", " ")} preview of ${detail.label}`}
                    source={{ uri: item.capture.uri }}
                    resizeMode="cover"
                    style={[
                      styles.sweepPreview,
                      { backgroundColor: theme.navy },
                    ]}
                  />
                  <Text
                    style={[styles.sweepPreviewLabel, { color: theme.text }]}
                  >
                    {item.angle.replaceAll("_", " ")}
                  </Text>
                </View>
              ))}
            </View>
          ) : (
            <Image
              accessible
              accessibilityLabel={`Preview of ${detail.label} before protected storage`}
              source={{ uri: candidate.capture.uri }}
              resizeMode="contain"
              style={[styles.preview, { backgroundColor: theme.navy }]}
            />
          )}
          <Card accent={candidate.quality.accepted ? "teal" : "coral"}>
            <SectionTitle
              title={
                candidate.quality.accepted
                  ? "Image quality accepted"
                  : "Retake needed"
              }
              subtitle={`${candidate.capture.source === "camera" ? "Camera image" : candidate.capture.source === "video_sweep" ? "Three sweep frames" : "Selected photo"}, metadata removed, ${candidate.capture.width} by ${candidate.capture.height} pixels`}
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
            <CaptureGuidanceMetrics
              snapshot={candidate.guidance}
              exposureScore={candidate.quality.exposureScore}
              {...(priorCapture
                ? {
                    baselineSnapshot: priorCapture.captureGuidance ?? null,
                    baselineExposureScore: priorCapture.quality.exposureScore,
                    baselineMillimetersPerPixel: calibratedScale(priorCapture),
                  }
                : {})}
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
                label={`I confirm ${sweepCandidates.length > 0 ? "these frames show" : "this frame shows"} mouth tissue only: no full face, eyes, name, or identifying surroundings are visible, and I have permission to capture it`}
                selected={mouthOnlyConfirmed}
                onPress={() => setMouthOnlyConfirmed((value) => !value)}
                accessibilityRole="checkbox"
              />
              <ChoiceChip
                label={`I confirm ${sweepCandidates.length > 0 ? "these frames show" : "this image shows"} ${detail.label}`}
                selected={regionConfirmed}
                onPress={() => setRegionConfirmed((value) => !value)}
                accessibilityRole="checkbox"
              />
              {calibrationEnabled ? (
                <ChoiceChip
                  label={`I confirm the printed 20 mm marker ${sweepCandidates.length > 0 ? "stayed" : "is"} beside the target, in the same plane, and did not touch tissue`}
                  selected={calibrationPlaneConfirmed}
                  onPress={() =>
                    setCalibrationPlaneConfirmed((value) => !value)
                  }
                  accessibilityRole="checkbox"
                />
              ) : null}
            </Card>
          ) : null}
          {candidate.quality.accepted ? (
            <Button
              label={
                sweepCandidates.length > 0
                  ? "Protect 3 frames & analyze"
                  : "Protect image & analyze"
              }
              icon="shield-checkmark-outline"
              loading={busy}
              loadingLabel={busyLabel}
              disabled={
                !mouthOnlyConfirmed ||
                !regionConfirmed ||
                (calibrationEnabled && !calibrationPlaneConfirmed) ||
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

function calibratedScale(capture: CaptureRecord): number | null {
  return capture.calibration?.status === "valid"
    ? capture.calibration.millimetersPerPixel
    : null;
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
  recordingLabel: {
    color: "#FFFFFF",
    fontSize: 12,
    lineHeight: 17,
    fontWeight: "800",
    backgroundColor: "rgba(166,52,42,0.88)",
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 999,
  },
  privacy: { fontSize: 11, lineHeight: 16, textAlign: "center" },
  sensorNote: { fontSize: 12, lineHeight: 18, textAlign: "center" },
  preview: { width: "100%", height: 290, borderRadius: 16 },
  sweepPreviewList: { flexDirection: "row", gap: 8 },
  sweepPreviewItem: { flex: 1, gap: 6 },
  sweepPreview: { width: "100%", height: 150, borderRadius: 13 },
  sweepPreviewLabel: {
    fontSize: 11,
    lineHeight: 15,
    fontWeight: "800",
    textAlign: "center",
    textTransform: "capitalize",
  },
  captureOptions: { gap: 8 },
  mirroredOverlay: { transform: [{ scaleX: -1 }] },
  reason: { fontSize: 13, lineHeight: 19, fontWeight: "700" },
  error: { textAlign: "center", fontSize: 13, fontWeight: "700" },
  errorGroup: { gap: 8 },
});
