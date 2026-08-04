import { Component, useEffect, useState, type ReactNode } from "react";
import {
  Pressable,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
} from "react-native";
import { Canvas, useThree } from "@react-three/fiber/native";
import { Ionicons } from "@expo/vector-icons";
import { MOUTH_REGION_DETAILS, type MouthRegion } from "@oralsight/contracts";

import { ORAL_MAP_ASSET_VERSION } from "@/constants";
import { useAppTheme } from "@/theme";
import type { ObservationPin } from "@/types";

interface OralObservationMapProps {
  completedRegions: MouthRegion[];
  selectedRegion: MouthRegion | null;
  onSelectRegion: (region: MouthRegion) => void;
  pins?: ObservationPin[];
  showRegionList?: boolean;
}

interface RegionMeshProps {
  id: MouthRegion;
  meshId: string;
  position: [number, number, number];
  scale: [number, number, number];
  color: string;
  opacity: number;
  onSelect: (region: MouthRegion) => void;
}

interface MapRenderBoundaryProps {
  children: ReactNode;
  fallback: ReactNode;
  onError: () => void;
}

class MapRenderBoundary extends Component<
  MapRenderBoundaryProps,
  { failed: boolean }
> {
  override state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  override componentDidCatch() {
    this.props.onError();
  }

  override render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}

function RegionMesh({
  id,
  meshId,
  position,
  scale,
  color,
  opacity,
  onSelect,
}: RegionMeshProps) {
  return (
    <mesh
      name={meshId}
      position={position}
      scale={scale}
      onClick={() => onSelect(id)}
    >
      <sphereGeometry args={[0.55, 32, 20]} />
      <meshStandardMaterial
        color={color}
        roughness={0.62}
        metalness={0.02}
        transparent
        opacity={opacity}
      />
    </mesh>
  );
}

const positions: Record<MouthRegion, [number, number, number]> = {
  dorsal_tongue: [0, -0.36, 0.28],
  ventral_tongue: [0, -0.72, -0.02],
  left_buccal_mucosa: [-1.02, 0, 0],
  right_buccal_mucosa: [1.02, 0, 0],
  upper_lip: [0, 0.82, 0.34],
  lower_lip: [0, -1.03, 0.32],
  upper_dental_arch: [0, 0.45, -0.02],
  lower_dental_arch: [0, -0.52, -0.2],
};

const scales: Record<MouthRegion, [number, number, number]> = {
  dorsal_tongue: [1.15, 0.72, 0.42],
  ventral_tongue: [0.72, 0.26, 0.3],
  left_buccal_mucosa: [0.42, 1.26, 0.6],
  right_buccal_mucosa: [0.42, 1.26, 0.6],
  upper_lip: [1.48, 0.26, 0.35],
  lower_lip: [1.35, 0.26, 0.35],
  upper_dental_arch: [1.1, 0.26, 0.25],
  lower_dental_arch: [1.08, 0.24, 0.25],
};

function renderedRegionPosition(
  region: MouthRegion,
  exploded: boolean,
): [number, number, number] {
  const base = positions[region];
  if (!exploded) return base;
  return [
    base[0] + Math.sign(base[0]) * 0.38,
    base[1] + Math.sign(base[1]) * 0.16,
    base[2],
  ];
}

function CameraDistance({ zoom }: { zoom: number }) {
  const camera = useThree((state) => state.camera);

  useEffect(() => {
    camera.position.z = zoom;
    camera.updateProjectionMatrix();
  }, [camera, zoom]);

  return null;
}

export function OralObservationMap({
  completedRegions,
  selectedRegion,
  onSelectRegion,
  pins = [],
  showRegionList = false,
}: OralObservationMapProps) {
  const theme = useAppTheme();
  const { height, width } = useWindowDimensions();
  const [rotation, setRotation] = useState(0);
  const [zoom, setZoom] = useState(4.5);
  const [exploded, setExploded] = useState(false);
  const [archesFaded, setArchesFaded] = useState(false);
  const [renderUnavailable, setRenderUnavailable] = useState(false);
  const [renderAttempt, setRenderAttempt] = useState(0);
  const isWide = width >= 700;
  const compactLandscape = width > height && height < 560;
  const mapHeight = compactLandscape ? 280 : isWide ? 420 : 350;

  const colorFor = (region: MouthRegion) =>
    selectedRegion === region
      ? theme.pin
      : completedRegions.includes(region)
        ? theme.aqua
        : theme.mapPending;

  return (
    <View style={styles.container}>
      <View
        accessible={false}
        style={[
          styles.shell,
          {
            height: mapHeight,
            backgroundColor: theme.navy,
            borderColor: theme.border,
          },
        ]}
      >
        <MapRenderBoundary
          key={renderAttempt}
          onError={() => setRenderUnavailable(true)}
          fallback={
            <View accessible={false} style={styles.renderFallback}>
              <View
                accessible
                accessibilityRole="alert"
                accessibilityLabel="3D map unavailable. Use the named region list below or retry the 3D view."
                style={styles.renderFallbackCopy}
              >
                <Ionicons
                  accessible={false}
                  name="cube-outline"
                  size={32}
                  color={theme.onCamera}
                />
                <Text
                  style={[
                    styles.renderFallbackTitle,
                    { color: theme.onCamera },
                  ]}
                >
                  3D view unavailable
                </Text>
                <Text
                  style={[styles.renderFallbackBody, { color: theme.onCamera }]}
                >
                  Use the named region list below. All selection and capture
                  actions remain available.
                </Text>
              </View>
              <Pressable
                accessibilityRole="button"
                accessibilityLabel="Retry 3D view"
                onPress={() => {
                  setRenderUnavailable(false);
                  setRenderAttempt((value) => value + 1);
                }}
                style={({ pressed }) => [
                  styles.renderRetry,
                  { borderColor: theme.onCamera },
                  pressed && styles.renderRetryPressed,
                ]}
              >
                <Ionicons
                  accessible={false}
                  name="refresh"
                  size={18}
                  color={theme.onCamera}
                />
                <Text
                  style={[styles.renderRetryText, { color: theme.onCamera }]}
                >
                  Retry 3D view
                </Text>
              </Pressable>
            </View>
          }
        >
          <View
            accessible={false}
            importantForAccessibility="no-hide-descendants"
            style={styles.canvas}
          >
            <Canvas camera={{ position: [0, 0, zoom], fov: 46 }}>
              <CameraDistance zoom={zoom} />
              <ambientLight intensity={1.6} />
              <directionalLight position={[2, 3, 4]} intensity={2.2} />
              <group rotation={[0.06, rotation, 0]}>
                {(Object.keys(positions) as MouthRegion[]).map((region) => {
                  const regionDetail = MOUTH_REGION_DETAILS.find(
                    (detail) => detail.id === region,
                  );
                  if (!regionDetail) return null;
                  return (
                    <RegionMesh
                      key={region}
                      id={region}
                      meshId={regionDetail.meshId}
                      position={renderedRegionPosition(region, exploded)}
                      scale={scales[region]}
                      color={colorFor(region)}
                      opacity={
                        archesFaded &&
                        (region === "upper_dental_arch" ||
                          region === "lower_dental_arch")
                          ? 0.16
                          : 0.92
                      }
                      onSelect={onSelectRegion}
                    />
                  );
                })}
                {pins.map((pin) => {
                  const regionDetail = MOUTH_REGION_DETAILS.find(
                    (detail) => detail.id === pin.region,
                  );
                  if (
                    !pin.userConfirmed ||
                    pin.assetVersion !== ORAL_MAP_ASSET_VERSION ||
                    pin.meshId !== regionDetail?.meshId
                  ) {
                    return null;
                  }
                  const base = renderedRegionPosition(pin.region, exploded);
                  const regionScale = scales[pin.region];
                  const position: [number, number, number] = [
                    base[0] + (pin.uvX - 0.5) * regionScale[0] * 0.65,
                    base[1] + (0.5 - pin.uvY) * regionScale[1] * 0.65,
                    base[2] + 0.35 + regionScale[2] * 0.25,
                  ];
                  return (
                    <mesh
                      key={pin.id}
                      name={`pin-${pin.id}`}
                      position={position}
                    >
                      <sphereGeometry args={[0.1, 18, 18]} />
                      <meshStandardMaterial
                        color={theme.pin}
                        emissive={theme.amber}
                        emissiveIntensity={0.3}
                      />
                    </mesh>
                  );
                })}
              </group>
            </Canvas>
          </View>
        </MapRenderBoundary>
        {!renderUnavailable ? (
          <>
            <View pointerEvents="box-none" style={styles.legend}>
              <View style={styles.legendRow}>
                <View style={[styles.dot, { backgroundColor: theme.aqua }]} />
                <Text style={[styles.legendText, { color: theme.onCamera }]}>
                  Accepted
                </Text>
              </View>
              <View style={styles.legendRow}>
                <View
                  style={[styles.dot, { backgroundColor: theme.mapPending }]}
                />
                <Text style={[styles.legendText, { color: theme.onCamera }]}>
                  Not captured
                </Text>
              </View>
              <View style={styles.legendRow}>
                <View style={[styles.dot, { backgroundColor: theme.pin }]} />
                <Text style={[styles.legendText, { color: theme.onCamera }]}>
                  Selected / pin
                </Text>
              </View>
            </View>
            <View style={styles.controls}>
              <MapControl
                label="Rotate left"
                icon="arrow-back"
                onPress={() => setRotation((value) => value - 0.35)}
              />
              <MapControl
                label="Rotate right"
                icon="arrow-forward"
                onPress={() => setRotation((value) => value + 0.35)}
              />
              <MapControl
                label="Zoom in"
                icon="add"
                onPress={() => setZoom((value) => Math.max(3.4, value - 0.4))}
              />
              <MapControl
                label="Zoom out"
                icon="remove"
                onPress={() => setZoom((value) => Math.min(6, value + 0.4))}
              />
              <MapControl
                label={exploded ? "Join layers" : "Explode layers"}
                icon={exploded ? "contract" : "expand"}
                onPress={() => setExploded((value) => !value)}
              />
            </View>
            <View style={styles.archControl}>
              <MapControl
                label={
                  archesFaded ? "Show dental arches" : "Fade dental arches"
                }
                icon={archesFaded ? "eye" : "eye-off"}
                onPress={() => setArchesFaded((value) => !value)}
              />
            </View>
          </>
        ) : null}
      </View>
      {showRegionList ? (
        <View
          style={[
            styles.regionSection,
            { backgroundColor: theme.surface, borderColor: theme.border },
          ]}
        >
          <Text
            accessibilityRole="header"
            style={[styles.regionSectionTitle, { color: theme.text }]}
          >
            Select a named region
          </Text>
          <Text
            style={[styles.regionSectionHint, { color: theme.secondaryText }]}
          >
            This list mirrors the visual map and remains available with a screen
            reader or when 3D rendering is unavailable.
          </Text>
          <View style={styles.regionGrid}>
            {MOUTH_REGION_DETAILS.map((detail) => {
              const selected = selectedRegion === detail.id;
              const accepted = completedRegions.includes(detail.id);
              const pinCount = pins.filter(
                (pin) =>
                  pin.userConfirmed &&
                  pin.region === detail.id &&
                  pin.assetVersion === ORAL_MAP_ASSET_VERSION &&
                  pin.meshId === detail.meshId,
              ).length;
              const stateCopy = [
                accepted ? "Accepted" : "Not captured",
                `${pinCount} observation pin${pinCount === 1 ? "" : "s"}`,
              ].join(", ");
              return (
                <Pressable
                  key={detail.id}
                  accessibilityRole="button"
                  accessibilityLabel={`${detail.label}. ${stateCopy}`}
                  accessibilityState={{ selected }}
                  onPress={() => onSelectRegion(detail.id)}
                  style={({ pressed }) => [
                    styles.regionOption,
                    isWide && styles.regionOptionWide,
                    {
                      backgroundColor: selected ? theme.mint : theme.background,
                      borderColor: selected ? theme.primary : theme.border,
                    },
                    pressed && styles.regionOptionPressed,
                  ]}
                >
                  <Ionicons
                    accessible={false}
                    name={
                      selected
                        ? "location"
                        : accepted
                          ? "checkmark-circle"
                          : "ellipse-outline"
                    }
                    color={
                      selected || accepted ? theme.primary : theme.secondaryText
                    }
                    size={21}
                  />
                  <View style={styles.regionOptionCopy}>
                    <Text
                      style={[styles.regionOptionTitle, { color: theme.text }]}
                    >
                      {detail.label}
                    </Text>
                    <Text
                      style={[
                        styles.regionOptionMeta,
                        { color: theme.secondaryText },
                      ]}
                    >
                      {stateCopy}
                    </Text>
                  </View>
                </Pressable>
              );
            })}
          </View>
        </View>
      ) : null}
    </View>
  );
}

interface MapControlProps {
  label: string;
  icon: keyof typeof Ionicons.glyphMap;
  onPress: () => void;
}

function MapControl({ label, icon, onPress }: MapControlProps) {
  const theme = useAppTheme();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityHint="Adjusts the visual oral observation map"
      hitSlop={4}
      style={({ pressed }) => [
        styles.control,
        {
          borderColor: "rgba(255,255,255,0.42)",
          backgroundColor: theme.isDark
            ? "rgba(255,255,255,0.18)"
            : "rgba(255,255,255,0.2)",
        },
        pressed && styles.controlPressed,
      ]}
      onPress={onPress}
    >
      <Ionicons
        accessible={false}
        name={icon}
        size={20}
        color={theme.onCamera}
      />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  container: { gap: 12 },
  shell: { borderRadius: 24, overflow: "hidden", borderWidth: 1 },
  canvas: { flex: 1 },
  renderFallback: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    padding: 28,
    gap: 18,
  },
  renderFallbackCopy: { alignItems: "center", gap: 8 },
  renderFallbackTitle: { fontSize: 18, fontWeight: "800", textAlign: "center" },
  renderFallbackBody: {
    maxWidth: 340,
    fontSize: 13,
    lineHeight: 19,
    textAlign: "center",
    opacity: 0.86,
  },
  renderRetry: {
    minHeight: 48,
    borderWidth: 1,
    borderRadius: 14,
    paddingHorizontal: 18,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
  },
  renderRetryPressed: { opacity: 0.76, transform: [{ scale: 0.98 }] },
  renderRetryText: { fontSize: 14, fontWeight: "800" },
  legend: {
    position: "absolute",
    top: 14,
    left: 14,
    gap: 5,
    backgroundColor: "rgba(7,26,43,0.75)",
    padding: 9,
    borderRadius: 12,
  },
  legendRow: { flexDirection: "row", gap: 6, alignItems: "center" },
  legendText: { fontSize: 11, fontWeight: "700" },
  dot: { width: 9, height: 9, borderRadius: 5 },
  controls: {
    position: "absolute",
    bottom: 12,
    left: 12,
    right: 12,
    flexDirection: "row",
    justifyContent: "center",
    gap: 8,
  },
  archControl: {
    position: "absolute",
    top: 12,
    right: 12,
  },
  control: {
    width: 48,
    height: 48,
    borderRadius: 24,
    borderWidth: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  controlPressed: { opacity: 0.76, transform: [{ scale: 0.96 }] },
  regionSection: {
    borderWidth: 1,
    borderRadius: 20,
    padding: 16,
    gap: 8,
  },
  regionSectionTitle: { fontSize: 17, fontWeight: "800" },
  regionSectionHint: { fontSize: 13, lineHeight: 19 },
  regionGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
    marginTop: 4,
  },
  regionOption: {
    width: "100%",
    minHeight: 56,
    borderWidth: 1,
    borderRadius: 14,
    paddingHorizontal: 12,
    paddingVertical: 9,
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  regionOptionWide: { width: "48.5%", flexGrow: 1 },
  regionOptionPressed: { opacity: 0.78, transform: [{ scale: 0.99 }] },
  regionOptionCopy: { flex: 1, gap: 2 },
  regionOptionTitle: { fontSize: 14, fontWeight: "800" },
  regionOptionMeta: { fontSize: 12, lineHeight: 17 },
});
