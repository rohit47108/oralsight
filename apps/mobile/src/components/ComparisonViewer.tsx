import { useRef, useState } from "react";
import {
  Image,
  PanResponder,
  Pressable,
  StyleSheet,
  Text,
  View,
  type LayoutChangeEvent,
  type NativeSyntheticEvent,
} from "react-native";

import {
  clampComparisonBlend,
  comparisonBlendAfterDrag,
  comparisonBlendFromTrackPosition,
} from "@/lib/comparisonSlider";
import { useAppTheme } from "@/theme";

interface ComparisonViewerProps {
  baselineUri: string;
  currentUri: string;
}

export function ComparisonViewer({
  baselineUri,
  currentUri,
}: ComparisonViewerProps) {
  const theme = useAppTheme();
  const [blend, setBlend] = useState(0.5);
  const blendRef = useRef(0.5);
  const dragStartBlend = useRef(0.5);
  const trackWidthRef = useRef(1);
  const setBlendValue = (next: number) => {
    const bounded = clampComparisonBlend(next);
    blendRef.current = bounded;
    setBlend(bounded);
  };
  const onLayout = (event: LayoutChangeEvent) => {
    trackWidthRef.current = Math.max(event.nativeEvent.layout.width, 1);
  };
  const adjust = (direction: "increment" | "decrement") =>
    setBlendValue(blendRef.current + (direction === "increment" ? 0.1 : -0.1));
  const panResponder = useRef(
    PanResponder.create({
      onMoveShouldSetPanResponderCapture: (_event, gesture) =>
        Math.abs(gesture.dx) > 4 && Math.abs(gesture.dx) > Math.abs(gesture.dy),
      onMoveShouldSetPanResponder: (_event, gesture) =>
        Math.abs(gesture.dx) > 4 && Math.abs(gesture.dx) > Math.abs(gesture.dy),
      onPanResponderGrant: () => {
        dragStartBlend.current = blendRef.current;
      },
      onPanResponderMove: (_event, gesture) => {
        setBlendValue(
          comparisonBlendAfterDrag(
            dragStartBlend.current,
            gesture.dx,
            trackWidthRef.current,
          ),
        );
      },
      onPanResponderTerminationRequest: () => true,
    }),
  ).current;
  const onAccessibilityAction = (
    event: NativeSyntheticEvent<{ actionName: string }>,
  ) => {
    if (
      event.nativeEvent.actionName === "increment" ||
      event.nativeEvent.actionName === "decrement"
    )
      adjust(event.nativeEvent.actionName);
  };

  return (
    <View style={styles.container}>
      <View style={styles.originalPair}>
        <View style={styles.originalColumn}>
          <Image
            accessible
            accessibilityLabel="Original baseline observation"
            source={{ uri: baselineUri }}
            style={styles.originalImage}
            resizeMode="contain"
          />
          <Text style={[styles.originalLabel, { color: theme.text }]}>
            BASELINE
          </Text>
        </View>
        <View style={styles.originalColumn}>
          <Image
            accessible
            accessibilityLabel="Original current observation"
            source={{ uri: currentUri }}
            style={styles.originalImage}
            resizeMode="contain"
          />
          <Text style={[styles.originalLabel, { color: theme.text }]}>
            CURRENT
          </Text>
        </View>
      </View>
      <View style={styles.imageShell}>
        <Image
          accessible={false}
          source={{ uri: baselineUri }}
          style={StyleSheet.absoluteFill}
          resizeMode="contain"
        />
        <Image
          accessible={false}
          source={{ uri: currentUri }}
          style={[StyleSheet.absoluteFill, { opacity: blend }]}
          resizeMode="contain"
        />
        <View
          pointerEvents="none"
          style={[
            styles.divider,
            { left: `${blend * 100}%`, backgroundColor: theme.amber },
          ]}
        />
        <View style={styles.labels}>
          <Text style={styles.label}>BASELINE</Text>
          <Text style={styles.label}>CURRENT</Text>
        </View>
      </View>
      <View {...panResponder.panHandlers}>
        <Pressable
          accessibilityRole="adjustable"
          accessibilityLabel="Original baseline and current image blend"
          accessibilityHint="Drag horizontally, tap a position, or use accessibility increment and decrement actions"
          accessibilityValue={{
            min: 0,
            max: 100,
            now: Math.round(blend * 100),
            text: `${Math.round(blend * 100)} percent current image`,
          }}
          accessibilityActions={[
            { name: "increment", label: "Show more current image" },
            { name: "decrement", label: "Show more baseline image" },
          ]}
          onAccessibilityAction={onAccessibilityAction}
          onLayout={onLayout}
          onPress={(event) =>
            setBlendValue(
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
                { backgroundColor: theme.primary, width: `${blend * 100}%` },
              ]}
            />
            <View
              style={[
                styles.thumb,
                {
                  left: `${blend * 100}%`,
                  backgroundColor: theme.surface,
                  borderColor: theme.primary,
                },
              ]}
            />
          </View>
        </Pressable>
      </View>
      <Text style={[styles.hint, { color: theme.secondaryText }]}>
        Drag or tap to blend the original captures. Confirm only if they show
        the same observation. This preview does not apply server alignment or
        image warping.
      </Text>
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
  originalLabel: { fontSize: 11, fontWeight: "900", textAlign: "center" },
  imageShell: {
    height: 255,
    borderRadius: 20,
    overflow: "hidden",
    backgroundColor: "#102A43",
  },
  divider: {
    position: "absolute",
    top: 0,
    bottom: 0,
    width: 3,
    marginLeft: -1.5,
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
});
