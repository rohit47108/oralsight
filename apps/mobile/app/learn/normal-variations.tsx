import { router } from "expo-router";
import { StyleSheet, Text, View } from "react-native";

import { Screen } from "@/components/Screen";
import { Button, Card, SectionTitle } from "@/components/Ui";
import { useAppTheme } from "@/theme";

const VARIATIONS = [
  {
    id: "symmetry",
    title: "Natural asymmetry",
    body: "The two sides of the mouth do not have to look pixel-for-pixel identical. Save clear surrounding landmarks so a professional can understand the location.",
  },
  {
    id: "texture",
    title: "Fine surface texture",
    body: "Tongue, lip, cheek, and gum surfaces have different textures. A close photograph can exaggerate normal ridges and folds.",
  },
  {
    id: "vessels",
    title: "Visible vessels",
    body: "Thin surface vessels may be easier to see in some regions and lighting. Match the angle and exposure before judging whether a later image looks different.",
  },
  {
    id: "lighting",
    title: "Color under different light",
    body: "Flash, room light, shadows, and phone processing can shift apparent color. Stoma3D records color descriptors only when image quality is usable and still labels them approximate.",
  },
] as const;

export default function NormalVariationsRoute() {
  const theme = useAppTheme();
  return (
    <Screen
      title="Variation gallery"
      eyebrow="Illustrated, not diagnostic"
      action={
        <Button label="Back" variant="ghost" onPress={() => router.back()} />
      }
    >
      <Card accent="amber">
        <SectionTitle
          title="Learn the effect of anatomy and photography"
          subtitle="These are abstract teaching illustrations, not patient photographs or examples to match against your own image."
          icon="images-outline"
        />
      </Card>
      {VARIATIONS.map((variation, index) => (
        <Card key={variation.id}>
          <View style={styles.row}>
            <VariationIllustration kind={variation.id} />
            <View style={styles.copy}>
              <Text style={[styles.index, { color: theme.primary }]}>
                {String(index + 1).padStart(2, "0")}
              </Text>
              <Text style={[styles.title, { color: theme.text }]}>
                {variation.title}
              </Text>
              <Text style={[styles.body, { color: theme.secondaryText }]}>
                {variation.body}
              </Text>
            </View>
          </View>
        </Card>
      ))}
      <Card accent="teal">
        <SectionTitle
          title="Use change, not resemblance"
          subtitle="A gallery match cannot establish that an area is harmless. If an area persists, changes, or worries you, arrange a professional examination."
          icon="git-compare-outline"
        />
      </Card>
    </Screen>
  );
}

function VariationIllustration({
  kind,
}: {
  kind: (typeof VARIATIONS)[number]["id"];
}) {
  const theme = useAppTheme();
  return (
    <View
      accessible
      accessibilityLabel={`${kind} abstract illustration, not a medical image`}
      style={[
        styles.illustration,
        { backgroundColor: theme.warningSurface, borderColor: theme.border },
      ]}
    >
      <View style={[styles.tissue, { backgroundColor: theme.mapPending }]} />
      {kind === "symmetry" ? (
        <>
          <View
            style={[styles.centerLine, { backgroundColor: theme.surface }]}
          />
          <View
            style={[
              styles.dot,
              styles.dotLeft,
              { backgroundColor: theme.coral },
            ]}
          />
          <View
            style={[
              styles.dot,
              styles.dotRight,
              { backgroundColor: theme.coral },
            ]}
          />
        </>
      ) : null}
      {kind === "texture" ? (
        <View style={styles.textureRows}>
          {[0, 1, 2, 3].map((item) => (
            <View
              key={item}
              style={[styles.textureLine, { borderColor: theme.coral }]}
            />
          ))}
        </View>
      ) : null}
      {kind === "vessels" ? (
        <>
          <View style={[styles.vessel, { backgroundColor: theme.primary }]} />
          <View
            style={[styles.vesselBranch, { backgroundColor: theme.primary }]}
          />
        </>
      ) : null}
      {kind === "lighting" ? (
        <View style={styles.lightingSplit}>
          <View
            style={[styles.lightHalf, { backgroundColor: theme.surface }]}
          />
          <View
            style={[
              styles.lightHalf,
              { backgroundColor: theme.warningOnCamera },
            ]}
          />
        </View>
      ) : null}
      <Text style={[styles.illustrationLabel, { color: theme.text }]}>
        ILLUSTRATION
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "center", gap: 14 },
  copy: { flex: 1, gap: 4 },
  index: { fontSize: 10, fontWeight: "900", letterSpacing: 0.7 },
  title: { fontSize: 17, lineHeight: 22, fontWeight: "800" },
  body: { fontSize: 13, lineHeight: 19 },
  illustration: {
    width: 118,
    height: 112,
    borderWidth: 1,
    borderRadius: 19,
    overflow: "hidden",
    alignItems: "center",
    justifyContent: "center",
  },
  tissue: {
    position: "absolute",
    width: 82,
    height: 62,
    borderRadius: 34,
  },
  centerLine: { position: "absolute", width: 2, height: 50 },
  dot: { position: "absolute", width: 7, height: 7, borderRadius: 4 },
  dotLeft: { left: 39, top: 49 },
  dotRight: { right: 35, top: 56 },
  textureRows: { position: "absolute", width: 66, gap: 5 },
  textureLine: { height: 7, borderTopWidth: 1, borderRadius: 8 },
  vessel: {
    position: "absolute",
    width: 3,
    height: 48,
    transform: [{ rotate: "24deg" }],
  },
  vesselBranch: {
    position: "absolute",
    width: 2,
    height: 29,
    transform: [{ translateX: 12 }, { translateY: -8 }, { rotate: "-36deg" }],
  },
  lightingSplit: {
    position: "absolute",
    width: 80,
    height: 60,
    borderRadius: 30,
    overflow: "hidden",
    flexDirection: "row",
    opacity: 0.48,
  },
  lightHalf: { flex: 1 },
  illustrationLabel: {
    position: "absolute",
    bottom: 8,
    fontSize: 8,
    fontWeight: "900",
    letterSpacing: 0.8,
  },
});
