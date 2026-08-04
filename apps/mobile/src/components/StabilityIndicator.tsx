import { useEffect } from "react";
import { StyleSheet, Text, View } from "react-native";
import Animated, {
  Easing,
  useAnimatedStyle,
  useSharedValue,
  withTiming,
} from "react-native-reanimated";

import { useAppTheme, useShouldReduceMotion } from "@/theme";

interface StabilityIndicatorProps {
  progress: number;
}

export function StabilityIndicator({ progress }: StabilityIndicatorProps) {
  const theme = useAppTheme();
  const reducedMotion = useShouldReduceMotion();
  const animatedProgress = useSharedValue(0);
  useEffect(() => {
    animatedProgress.value = withTiming(Math.max(0, Math.min(1, progress)), {
      duration: reducedMotion ? 0 : 160,
      easing: Easing.bezier(0.23, 1, 0.32, 1),
    });
  }, [animatedProgress, progress, reducedMotion]);
  const animatedStyle = useAnimatedStyle(() => ({
    transform: [{ scaleX: animatedProgress.value }],
  }));
  const stable = progress >= 0.9;
  const percent = Math.round(progress * 100);
  return (
    <View
      accessible
      accessibilityRole="progressbar"
      accessibilityLabel="Camera stability"
      accessibilityValue={{
        min: 0,
        max: 100,
        now: percent,
        text: stable ? "Stable. Ready to capture." : `${percent} percent`,
      }}
      style={styles.container}
    >
      <View style={[styles.track, { borderColor: theme.onCamera }]}>
        <Animated.View
          style={[
            styles.fill,
            {
              backgroundColor: stable ? theme.aqua : theme.warningOnCamera,
            },
            animatedStyle,
          ]}
        />
      </View>
      <Text style={styles.label}>
        {stable ? "Steady and ready" : "Hold still"}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { gap: 6, alignItems: "center" },
  track: {
    width: 154,
    height: 12,
    position: "relative",
    borderWidth: 2,
    borderRadius: 999,
    overflow: "hidden",
    backgroundColor: "rgba(0,0,0,0.28)",
  },
  fill: {
    position: "absolute",
    top: 0,
    right: 0,
    bottom: 0,
    left: 0,
    transformOrigin: "left center",
  },
  label: {
    color: "#FFFFFF",
    fontWeight: "800",
    fontSize: 13,
    textShadowColor: "#000000",
    textShadowRadius: 4,
  },
});
