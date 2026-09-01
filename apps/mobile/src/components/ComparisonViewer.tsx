import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Image,
  PanResponder,
  Pressable,
  StyleSheet,
  Text,
  View,
  type ImageStyle,
  type LayoutChangeEvent,
  type NativeSyntheticEvent,
  type StyleProp,
} from "react-native";
import Svg, { Polygon } from "react-native-svg";
import type { CandidateMask } from "@stoma3d/contracts";

import {
  clampComparisonBlend,
  comparisonBlendAfterDrag,
  comparisonBlendFromTrackPosition,
} from "@/lib/comparisonSlider";
import {
  buildDisplayRegistrationMatrix,
  buildMaskTimelineGeometry,
  containedImageRect,
  projectRegisteredPoint,
  type ContainedImageRect,
  type ImageSize,
  type NormalizedPoint,
} from "@/lib/comparisonPresentation";
import { animationDurationMs } from "@/lib/motionPreferences";
import { useStoma3DStore } from "@/store/useStoma3DStore";
import { useAppTheme, useShouldReduceMotion } from "@/theme";
import type { RegistrationAlignment } from "@stoma3d/contracts";

interface ComparisonViewerProps {
  baselineUri: string;
  currentUri: string;
  baselineMask?: CandidateMask | null;
  currentMask?: CandidateMask | null;
  registrationAlignment?: RegistrationAlignment | null;
}

interface KeyboardEventData {
  key: string;
}

type PresentationMode = "reveal" | "timeline";

const FRAME_HEIGHT = 255;

function imageSizeFromUri(uri: string, onSize: (size: ImageSize) => void) {
  let active = true;
  Image.getSize(
    uri,
    (widthPx, heightPx) => {
      if (active) onSize({ widthPx, heightPx });
    },
    () => undefined,
  );
  return () => {
    active = false;
  };
}

function pointsForSvg(
  points: readonly NormalizedPoint[],
  rect: ContainedImageRect | null,
): string | null {
  if (!rect || points.length < 3) return null;
  return points
    .map(
      ([x, y]) => `${rect.left + x * rect.width},${rect.top + y * rect.height}`,
    )
    .join(" ");
}

export function ComparisonViewer({
  baselineUri,
  currentUri,
  baselineMask = null,
  currentMask = null,
  registrationAlignment = null,
}: ComparisonViewerProps) {
  const theme = useAppTheme();
  const reduceMotion = useShouldReduceMotion();
  const animationSpeed = useStoma3DStore(
    (state) => state.settings.animationSpeed,
  );
  const [mode, setMode] = useState<PresentationMode>("reveal");
  const [position, setPosition] = useState(0.5);
  const [playing, setPlaying] = useState(false);
  const [frameWidth, setFrameWidth] = useState(1);
  const [baselineSize, setBaselineSize] = useState<ImageSize | null>(
    registrationAlignment?.targetImageSize ?? null,
  );
  const [currentSize, setCurrentSize] = useState<ImageSize | null>(
    registrationAlignment?.sourceImageSize ?? null,
  );
  const positionRef = useRef(0.5);
  const dragStartPosition = useRef(0.5);
  const trackWidthRef = useRef(1);

  const setPositionValue = useCallback((next: number) => {
    const bounded = clampComparisonBlend(next);
    positionRef.current = bounded;
    setPosition(bounded);
  }, []);

  useEffect(() => {
    if (registrationAlignment?.targetImageSize) {
      setBaselineSize(registrationAlignment.targetImageSize);
      return undefined;
    }
    return imageSizeFromUri(baselineUri, setBaselineSize);
  }, [baselineUri, registrationAlignment?.targetImageSize]);

  useEffect(() => {
    if (registrationAlignment?.sourceImageSize) {
      setCurrentSize(registrationAlignment.sourceImageSize);
      return undefined;
    }
    return imageSizeFromUri(currentUri, setCurrentSize);
  }, [currentUri, registrationAlignment?.sourceImageSize]);

  const frame = useMemo(
    () => ({ width: frameWidth, height: FRAME_HEIGHT }),
    [frameWidth],
  );
  const displayRegistration = useMemo(
    () => buildDisplayRegistrationMatrix(frame, registrationAlignment),
    [frame, registrationAlignment],
  );
  const baselineRect = useMemo(
    () =>
      displayRegistration?.targetRect ??
      (baselineSize ? containedImageRect(frame, baselineSize) : null),
    [baselineSize, displayRegistration?.targetRect, frame],
  );
  const currentRect = useMemo(
    () =>
      displayRegistration?.sourceRect ??
      (currentSize ? containedImageRect(frame, currentSize) : null),
    [currentSize, displayRegistration?.sourceRect, frame],
  );
  const timelineGeometry = useMemo(
    () =>
      buildMaskTimelineGeometry(
        baselineMask,
        currentMask,
        position,
        displayRegistration ? registrationAlignment : null,
      ),
    [
      baselineMask,
      currentMask,
      displayRegistration,
      position,
      registrationAlignment,
    ],
  );

  const baselineMaskPoints = useMemo(
    () =>
      baselineMask ? pointsForSvg(baselineMask.polygon, baselineRect) : null,
    [baselineMask, baselineRect],
  );
  const currentMaskPoints = useMemo(() => {
    if (!currentMask) return null;
    if (!displayRegistration) {
      return pointsForSvg(currentMask.polygon, currentRect);
    }
    const projected = currentMask.polygon.map((point) =>
      projectRegisteredPoint(point, registrationAlignment),
    );
    return projected.some((point) => point === null)
      ? null
      : pointsForSvg(projected as NormalizedPoint[], baselineRect);
  }, [
    baselineRect,
    currentMask,
    currentRect,
    displayRegistration,
    registrationAlignment,
  ]);
  const timelineBaselinePoints = useMemo(
    () => pointsForSvg(timelineGeometry.baseline, baselineRect),
    [baselineRect, timelineGeometry.baseline],
  );
  const timelineCurrentPoints = useMemo(
    () =>
      pointsForSvg(
        timelineGeometry.current,
        timelineGeometry.kind === "morph" ? baselineRect : currentRect,
      ),
    [baselineRect, currentRect, timelineGeometry],
  );
  const morphedMaskPoints = useMemo(
    () =>
      timelineGeometry.morphed
        ? pointsForSvg(timelineGeometry.morphed, baselineRect)
        : null,
    [baselineRect, timelineGeometry.morphed],
  );

  const onTrackLayout = (event: LayoutChangeEvent) => {
    trackWidthRef.current = Math.max(event.nativeEvent.layout.width, 1);
  };
  const onFrameLayout = (event: LayoutChangeEvent) => {
    setFrameWidth(Math.max(event.nativeEvent.layout.width, 1));
  };
  const adjust = useCallback(
    (direction: "increment" | "decrement") =>
      setPositionValue(
        positionRef.current + (direction === "increment" ? 0.1 : -0.1),
      ),
    [setPositionValue],
  );
  const panResponder = useMemo(
    () =>
      PanResponder.create({
        onMoveShouldSetPanResponderCapture: (_event, gesture) =>
          Math.abs(gesture.dx) > 4 &&
          Math.abs(gesture.dx) > Math.abs(gesture.dy),
        onMoveShouldSetPanResponder: (_event, gesture) =>
          Math.abs(gesture.dx) > 4 &&
          Math.abs(gesture.dx) > Math.abs(gesture.dy),
        onPanResponderGrant: () => {
          dragStartPosition.current = positionRef.current;
        },
        onPanResponderMove: (_event, gesture) => {
          setPositionValue(
            comparisonBlendAfterDrag(
              dragStartPosition.current,
              gesture.dx,
              trackWidthRef.current,
            ),
          );
        },
        onPanResponderTerminationRequest: () => true,
      }),
    [setPositionValue],
  );
  const onAccessibilityAction = (
    event: NativeSyntheticEvent<{ actionName: string }>,
  ) => {
    if (
      event.nativeEvent.actionName === "increment" ||
      event.nativeEvent.actionName === "decrement"
    ) {
      adjust(event.nativeEvent.actionName);
    }
  };
  const onKeyDown = (event: NativeSyntheticEvent<KeyboardEventData>) => {
    switch (event.nativeEvent.key) {
      case "ArrowRight":
      case "ArrowUp":
        event.preventDefault();
        adjust("increment");
        break;
      case "ArrowLeft":
      case "ArrowDown":
        event.preventDefault();
        adjust("decrement");
        break;
      case "Home":
        event.preventDefault();
        setPositionValue(0);
        break;
      case "End":
        event.preventDefault();
        setPositionValue(1);
        break;
      default:
        break;
    }
  };
  // React Native implements keyboard events on View/Pressable in the new
  // architecture, while the stable Pressable TypeScript declaration lags the
  // native prop. The spread keeps the runtime capability without weakening
  // the rest of this component's props.
  const keyboardHandlers = {
    onKeyDown,
  } as unknown as Record<string, unknown>;

  useEffect(() => {
    if (!playing || reduceMotion || mode !== "timeline") return undefined;
    const startedAt = Date.now();
    const startedAtPosition =
      positionRef.current >= 0.995 ? 0 : positionRef.current;
    if (startedAtPosition === 0) setPositionValue(0);
    const fullDuration = animationDurationMs(4_000, animationSpeed);
    const remainingDuration = Math.max(
      fullDuration * (1 - startedAtPosition),
      1,
    );
    let frameHandle = 0;
    const animate = () => {
      const fraction = Math.min(
        (Date.now() - startedAt) / remainingDuration,
        1,
      );
      const eased = fraction * fraction * (3 - 2 * fraction);
      setPositionValue(startedAtPosition + (1 - startedAtPosition) * eased);
      if (fraction >= 1) {
        setPlaying(false);
        return;
      }
      frameHandle = requestAnimationFrame(animate);
    };
    frameHandle = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frameHandle);
  }, [animationSpeed, mode, playing, reduceMotion, setPositionValue]);

  useEffect(() => {
    if (reduceMotion || mode !== "timeline") setPlaying(false);
  }, [mode, reduceMotion]);

  const imageStyle = (kind: "baseline" | "current"): StyleProp<ImageStyle> => {
    if (kind === "current" && displayRegistration) {
      return {
        position: "absolute",
        left: 0,
        top: 0,
        width: displayRegistration.sourceRect.width,
        height: displayRegistration.sourceRect.height,
        transformOrigin: [0, 0, 0],
        transform: [{ matrix: [...displayRegistration.matrix] }],
      };
    }
    const rect = kind === "baseline" ? baselineRect : currentRect;
    return rect
      ? {
          position: "absolute",
          left: rect.left,
          top: rect.top,
          width: rect.width,
          height: rect.height,
        }
      : StyleSheet.absoluteFill;
  };

  const renderImage = (kind: "baseline" | "current", opacity = 1) => (
    <Image
      accessible={false}
      source={{ uri: kind === "baseline" ? baselineUri : currentUri }}
      style={[imageStyle(kind), { opacity }]}
      resizeMode={
        (kind === "current" && displayRegistration) ||
        (kind === "baseline" ? baselineRect : currentRect)
          ? "stretch"
          : "contain"
      }
    />
  );

  const renderPolygon = (points: string | null, color: string, opacity = 1) =>
    points ? (
      <Polygon
        points={points}
        fill={color}
        fillOpacity={0.16 * opacity}
        stroke={color}
        strokeOpacity={opacity}
        strokeWidth={2.5}
        strokeLinejoin="round"
      />
    ) : null;

  const modeHint =
    mode === "reveal"
      ? displayRegistration
        ? "Drag or tap to reveal the registered current capture over the baseline. The untouched originals remain above."
        : "Drag or tap to reveal the current capture in its original framing. No registration transform is available; the app does not claim these pixels are aligned."
      : timelineGeometry.kind === "morph"
        ? "The two registered candidate-mask outlines interpolate from baseline to current. This is a visual timeline, not a physical measurement."
        : timelineGeometry.kind === "crossfade"
          ? "The captures and candidate-mask outlines crossfade chronologically. Without registration, the outlines do not spatially morph."
          : "The captures crossfade chronologically. Both candidate masks are required for a mask-aware timeline.";

  return (
    <View style={styles.container}>
      <View style={styles.originalPair}>
        <View style={styles.originalColumn}>
          <Image
            accessible
            accessibilityLabel="Untouched baseline observation"
            source={{ uri: baselineUri }}
            style={styles.originalImage}
            resizeMode="contain"
          />
          <Text style={[styles.originalLabel, { color: theme.text }]}>
            BASELINE ORIGINAL
          </Text>
        </View>
        <View style={styles.originalColumn}>
          <Image
            accessible
            accessibilityLabel="Untouched current observation"
            source={{ uri: currentUri }}
            style={styles.originalImage}
            resizeMode="contain"
          />
          <Text style={[styles.originalLabel, { color: theme.text }]}>
            CURRENT ORIGINAL
          </Text>
        </View>
      </View>

      <View accessibilityRole="tablist" style={styles.modeTabs}>
        {(
          [
            ["reveal", "Reveal slider"],
            ["timeline", "Change timeline"],
          ] as const
        ).map(([value, label]) => {
          const selected = mode === value;
          return (
            <Pressable
              key={value}
              accessibilityRole="tab"
              accessibilityState={{ selected }}
              onPress={() => {
                setPlaying(false);
                setMode(value);
              }}
              style={({ pressed }) => [
                styles.modeTab,
                {
                  borderColor: selected ? theme.primary : theme.border,
                  backgroundColor: selected ? theme.mint : theme.surface,
                  opacity: pressed ? 0.82 : 1,
                },
              ]}
            >
              <Text
                style={[
                  styles.modeTabText,
                  { color: selected ? theme.primary : theme.secondaryText },
                ]}
              >
                {label}
              </Text>
            </Pressable>
          );
        })}
      </View>

      <View
        onLayout={onFrameLayout}
        style={[
          styles.imageShell,
          { borderColor: displayRegistration ? theme.primary : theme.border },
        ]}
      >
        {renderImage("baseline", mode === "timeline" ? 1 - position : 1)}
        {mode === "reveal" ? (
          <>
            <Svg
              pointerEvents="none"
              width={frameWidth}
              height={FRAME_HEIGHT}
              style={StyleSheet.absoluteFill}
            >
              {renderPolygon(baselineMaskPoints, theme.amber)}
            </Svg>
            <View
              pointerEvents="none"
              style={[styles.revealClip, { width: `${position * 100}%` }]}
            >
              <View style={{ width: frameWidth, height: FRAME_HEIGHT }}>
                {renderImage("current")}
                <Svg
                  width={frameWidth}
                  height={FRAME_HEIGHT}
                  style={StyleSheet.absoluteFill}
                >
                  {renderPolygon(currentMaskPoints, theme.primary)}
                </Svg>
              </View>
            </View>
            <View
              pointerEvents="none"
              style={[
                styles.divider,
                {
                  left: `${position * 100}%`,
                  backgroundColor: theme.amber,
                },
              ]}
            >
              <View
                style={[
                  styles.dividerHandle,
                  { backgroundColor: theme.surface, borderColor: theme.amber },
                ]}
              />
            </View>
          </>
        ) : (
          <>
            {renderImage("current", position)}
            <Svg
              pointerEvents="none"
              width={frameWidth}
              height={FRAME_HEIGHT}
              style={StyleSheet.absoluteFill}
            >
              {timelineGeometry.kind === "morph" ? (
                renderPolygon(morphedMaskPoints, theme.primary)
              ) : (
                <>
                  {renderPolygon(
                    timelineBaselinePoints,
                    theme.amber,
                    timelineGeometry.baselineOpacity,
                  )}
                  {renderPolygon(
                    timelineCurrentPoints,
                    theme.primary,
                    timelineGeometry.currentOpacity,
                  )}
                </>
              )}
            </Svg>
          </>
        )}
        <View style={styles.labels} pointerEvents="none">
          <Text style={styles.label}>BASELINE</Text>
          <Text style={styles.label}>CURRENT</Text>
        </View>
        <View
          pointerEvents="none"
          style={[
            styles.alignmentBadge,
            {
              backgroundColor: displayRegistration
                ? "rgba(10, 93, 84, 0.88)"
                : "rgba(15, 23, 42, 0.82)",
            },
          ]}
        >
          <Text style={styles.alignmentBadgeText}>
            {displayRegistration ? "REGISTERED VIEW" : "ORIGINAL FRAMING"}
          </Text>
        </View>
      </View>

      <View {...panResponder.panHandlers}>
        <Pressable
          {...keyboardHandlers}
          focusable
          tabIndex={0}
          accessibilityRole="adjustable"
          accessibilityLabel={
            mode === "reveal"
              ? "Before and after reveal divider"
              : "Chronological comparison position"
          }
          accessibilityHint="Drag horizontally, tap a position, press an arrow key, or use accessibility increment and decrement actions"
          accessibilityValue={{
            min: 0,
            max: 100,
            now: Math.round(position * 100),
            text:
              mode === "reveal"
                ? `${Math.round(position * 100)} percent current capture revealed from the left`
                : `${Math.round(position * 100)} percent from baseline toward current capture`,
          }}
          accessibilityActions={[
            {
              name: "increment",
              label:
                mode === "reveal"
                  ? "Reveal more current capture"
                  : "Move toward current capture",
            },
            {
              name: "decrement",
              label:
                mode === "reveal"
                  ? "Reveal more baseline capture"
                  : "Move toward baseline capture",
            },
          ]}
          onAccessibilityAction={onAccessibilityAction}
          onLayout={onTrackLayout}
          onPress={(event) =>
            setPositionValue(
              comparisonBlendFromTrackPosition(
                event.nativeEvent.locationX,
                trackWidthRef.current,
              ),
            )
          }
          style={({ pressed }) => [
            styles.sliderTouch,
            pressed && styles.sliderPressed,
          ]}
        >
          <View
            pointerEvents="none"
            style={[styles.track, { backgroundColor: theme.line }]}
          >
            <View
              style={[
                styles.trackFill,
                {
                  backgroundColor: theme.primary,
                  width: `${position * 100}%`,
                },
              ]}
            />
            <View
              style={[
                styles.thumb,
                {
                  left: `${position * 100}%`,
                  backgroundColor: theme.surface,
                  borderColor: theme.primary,
                },
              ]}
            />
          </View>
        </Pressable>
      </View>
      <Text style={[styles.hint, { color: theme.secondaryText }]}>
        {modeHint}
      </Text>
      {mode === "timeline" ? (
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={
            playing
              ? "Pause baseline-to-current timeline"
              : "Play baseline-to-current timeline"
          }
          accessibilityHint="Animates from the earlier capture to the newer capture once"
          accessibilityState={{ disabled: reduceMotion }}
          disabled={reduceMotion}
          onPress={() => setPlaying((value) => !value)}
          style={({ pressed }) => [
            styles.playButton,
            {
              borderColor: theme.border,
              backgroundColor: theme.surface,
              opacity: reduceMotion ? 0.55 : pressed ? 0.82 : 1,
            },
          ]}
        >
          <Text style={[styles.playButtonText, { color: theme.primary }]}>
            {reduceMotion
              ? "Automatic motion off; use the slider"
              : playing
                ? "Pause timeline"
                : position >= 0.995
                  ? "Replay baseline to current"
                  : "Play baseline to current"}
          </Text>
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { gap: 12 },
  originalPair: { flexDirection: "row", gap: 10 },
  originalColumn: { flex: 1, gap: 5 },
  originalImage: {
    width: "100%",
    height: 145,
    borderRadius: 14,
    backgroundColor: "#102A43",
  },
  originalLabel: { fontSize: 10, fontWeight: "900", textAlign: "center" },
  modeTabs: { flexDirection: "row", gap: 8 },
  modeTab: {
    flex: 1,
    minHeight: 44,
    borderWidth: 1,
    borderRadius: 13,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 10,
  },
  modeTabText: { fontSize: 12, fontWeight: "800", textAlign: "center" },
  imageShell: {
    height: FRAME_HEIGHT,
    borderWidth: 1,
    borderRadius: 20,
    overflow: "hidden",
    backgroundColor: "#102A43",
  },
  revealClip: {
    position: "absolute",
    top: 0,
    bottom: 0,
    left: 0,
    overflow: "hidden",
  },
  divider: {
    position: "absolute",
    top: 0,
    bottom: 0,
    width: 3,
    marginLeft: -1.5,
    alignItems: "center",
    justifyContent: "center",
  },
  dividerHandle: {
    width: 30,
    height: 42,
    borderRadius: 15,
    borderWidth: 3,
  },
  labels: {
    position: "absolute",
    top: 10,
    left: 10,
    right: 10,
    flexDirection: "row",
    justifyContent: "space-between",
  },
  label: {
    color: "#FFFFFF",
    fontSize: 11,
    fontWeight: "900",
    backgroundColor: "rgba(0,0,0,0.55)",
    borderRadius: 7,
    paddingHorizontal: 8,
    paddingVertical: 5,
  },
  alignmentBadge: {
    position: "absolute",
    bottom: 10,
    alignSelf: "center",
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  alignmentBadgeText: {
    color: "#FFFFFF",
    fontSize: 9,
    fontWeight: "900",
    letterSpacing: 0.7,
  },
  sliderTouch: { minHeight: 48, justifyContent: "center" },
  sliderPressed: { opacity: 0.86 },
  track: { height: 12, borderRadius: 999 },
  trackFill: { height: "100%", borderRadius: 999 },
  thumb: {
    position: "absolute",
    top: -7,
    width: 26,
    height: 26,
    borderRadius: 13,
    borderWidth: 3,
    marginLeft: -13,
  },
  hint: { fontSize: 11, lineHeight: 16, textAlign: "center" },
  playButton: {
    minHeight: 46,
    borderWidth: 1,
    borderRadius: 14,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 16,
  },
  playButtonText: { fontSize: 13, fontWeight: "800", textAlign: "center" },
});
