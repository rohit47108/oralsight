import { Fragment, useMemo, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { Canvas, Circle, Path, Skia } from "@shopify/react-native-skia";

import type { TrajectoryPoint } from "@/lib/trajectory";
import { useAppTheme } from "@/theme";

interface VisualTrajectoryChartProps {
  points: readonly TrajectoryPoint[];
}

interface PlotPoint {
  source: TrajectoryPoint;
  x: number;
  y: number;
}

type ChartPath = ReturnType<ReturnType<typeof Skia.PathBuilder.Make>["detach"]>;

const CHART_HEIGHT = 196;
const PADDING = 18;

export function VisualTrajectoryChart({ points }: VisualTrajectoryChartProps) {
  const theme = useAppTheme();
  const [chartWidth, setChartWidth] = useState(0);
  const plot = useMemo(() => {
    if (chartWidth <= PADDING * 2 || points.length === 0) {
      return { points: [] as PlotPoint[], paths: [] as ChartPath[] };
    }
    const firstPoint = points[0];
    const lastPoint = points.at(-1);
    if (!firstPoint || !lastPoint) {
      return { points: [] as PlotPoint[], paths: [] as ChartPath[] };
    }
    const areas = points.map((point) => point.normalizedArea);
    const observedMin = Math.min(...areas);
    const observedMax = Math.max(...areas);
    const padding = Math.max(0.01, (observedMax - observedMin) * 0.15);
    const minimum = Math.max(0, observedMin - padding);
    const maximum = Math.min(1, observedMax + padding);
    const range = Math.max(0.02, maximum - minimum);
    const drawableWidth = chartWidth - PADDING * 2;
    const drawableHeight = CHART_HEIGHT - PADDING * 2;
    const firstTime = Date.parse(firstPoint.capturedAt);
    const lastTime = Date.parse(lastPoint.capturedAt);
    const timeRange = Math.max(1, lastTime - firstTime);
    const plotted = points.map((point) => ({
      source: point,
      x:
        points.length === 1
          ? chartWidth / 2
          : PADDING +
            ((Date.parse(point.capturedAt) - firstTime) / timeRange) *
              drawableWidth,
      y:
        CHART_HEIGHT -
        PADDING -
        ((point.normalizedArea - minimum) / range) * drawableHeight,
    }));
    const paths = plotted.flatMap((point, index) => {
      const previous = plotted[index - 1];
      if (!previous || !point.source.comparableFromPrevious) return [];
      const builder = Skia.PathBuilder.Make();
      builder.moveTo(previous.x, previous.y);
      builder.lineTo(point.x, point.y);
      return [builder.detach()];
    });
    return { points: plotted, paths };
  }, [chartWidth, points]);

  const values = points.map((point) => point.normalizedArea);
  const topValue = values.length ? Math.max(...values) : 0;
  const bottomValue = values.length ? Math.min(...values) : 0;

  return (
    <View style={styles.container}>
      <View style={styles.axisRow}>
        <Text style={[styles.axis, { color: theme.secondaryText }]}>
          {(topValue * 100).toFixed(1)}%
        </Text>
        <View
          accessible={false}
          onLayout={(event) => setChartWidth(event.nativeEvent.layout.width)}
          style={[styles.chart, { backgroundColor: theme.background }]}
        >
          {chartWidth > 0 ? (
            <Canvas style={StyleSheet.absoluteFill}>
              {plot.paths.map((path, index) => (
                <Path
                  key={`segment-${index}`}
                  path={path}
                  color={theme.primary}
                  style="stroke"
                  strokeWidth={3}
                  strokeCap="round"
                />
              ))}
              {plot.points.map((point) => (
                <Fragment key={point.source.captureId}>
                  <Circle
                    cx={point.x}
                    cy={point.y}
                    r={8}
                    color={theme.primary}
                  />
                  <Circle cx={point.x} cy={point.y} r={5} color={theme.pin} />
                </Fragment>
              ))}
            </Canvas>
          ) : null}
        </View>
      </View>
      <Text style={[styles.axis, { color: theme.secondaryText }]}>
        {(bottomValue * 100).toFixed(1)}% approximate image area
      </Text>
      <View accessible style={styles.accessibleList}>
        {points.map((point, index) => (
          <Text
            key={point.captureId}
            style={[styles.pointSummary, { color: theme.secondaryText }]}
          >
            {new Date(point.capturedAt).toLocaleDateString()}: approximate area{" "}
            {(point.normalizedArea * 100).toFixed(1)}%, image quality{" "}
            {Math.round(point.qualityScore * 100)}%, model confidence{" "}
            {Math.round(point.confidence * 100)}%
            {index === 0
              ? "."
              : point.comparableFromPrevious
                ? "; connected because the comparison passed every gate."
                : "; not connected because comparable change was not established."}
          </Text>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { gap: 7 },
  axisRow: { flexDirection: "row", alignItems: "flex-start", gap: 8 },
  chart: {
    flex: 1,
    height: CHART_HEIGHT,
    borderRadius: 14,
    overflow: "hidden",
  },
  axis: { fontSize: 11, fontWeight: "700" },
  accessibleList: { gap: 5 },
  pointSummary: { fontSize: 12, lineHeight: 18 },
});
