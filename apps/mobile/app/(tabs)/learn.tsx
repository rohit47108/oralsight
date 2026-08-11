import { type Href, router } from "expo-router";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { Screen } from "@/components/Screen";
import { Button, Card, SectionTitle } from "@/components/Ui";
import { APPOINTMENT_QUESTIONS } from "@/lib/education";
import { useAppTheme } from "@/theme";

const lessons = [
  {
    title: "Oral anatomy atlas",
    body: "Learn the exact eight scan regions and how to frame each one.",
    icon: "map-outline" as const,
    route: "/learn/atlas" as const,
  },
  {
    title: "Variation gallery",
    body: "See how anatomy, lighting, texture, and symmetry can change a photograph.",
    icon: "images-outline" as const,
    route: "/learn/normal-variations" as const,
  },
  {
    title: "Capture practice",
    body: "Practice recognizing blur, glare, obstruction, and useful framing.",
    icon: "camera-outline" as const,
    route: "/learn/scan-practice" as const,
  },
  {
    title: "Four quick questions",
    body: "Check what makes a follow-up image and report useful.",
    icon: "help-circle-outline" as const,
    route: "/learn/questions" as const,
  },
];

export default function LearnRoute() {
  const theme = useAppTheme();
  return (
    <Screen
      title="Learn the scan"
      eyebrow="Practice before capture"
      action={
        <Button
          label="Settings"
          icon="options-outline"
          variant="ghost"
          onPress={() => router.push("/(tabs)/settings")}
        />
      }
    >
      <Card accent="teal">
        <SectionTitle
          title="Know what the camera needs"
          subtitle="These tools teach capture and reporting. They do not analyze you or provide a medical conclusion."
          icon="school-outline"
        />
      </Card>

      <View style={styles.lessonList}>
        {lessons.map((lesson, index) => (
          <Pressable
            key={lesson.title}
            accessibilityRole="button"
            accessibilityLabel={`${lesson.title}. ${lesson.body}`}
            onPress={() => router.push(lesson.route as Href)}
            style={({ pressed }) => [
              styles.lesson,
              {
                backgroundColor: theme.surface,
                borderColor: theme.border,
              },
              pressed && styles.pressed,
            ]}
          >
            <Text style={[styles.number, { color: theme.primary }]}>
              {String(index + 1).padStart(2, "0")}
            </Text>
            <View style={[styles.lessonIcon, { backgroundColor: theme.mint }]}>
              <Ionicons name={lesson.icon} size={23} color={theme.primary} />
            </View>
            <View style={styles.lessonCopy}>
              <Text style={[styles.lessonTitle, { color: theme.text }]}>
                {lesson.title}
              </Text>
              <Text style={[styles.lessonBody, { color: theme.secondaryText }]}>
                {lesson.body}
              </Text>
            </View>
            <Ionicons
              name="chevron-forward"
              color={theme.secondaryText}
              size={20}
            />
          </Pressable>
        ))}
      </View>

      <Card>
        <SectionTitle
          title="Prepare for a professional visit"
          subtitle="Use the report as a record, then ask direct questions."
          icon="chatbubbles-outline"
        />
        {APPOINTMENT_QUESTIONS.map((question, index) => (
          <View key={question} style={styles.questionRow}>
            <Text style={[styles.questionNumber, { color: theme.primary }]}>
              {index + 1}
            </Text>
            <Text style={[styles.question, { color: theme.text }]}>
              {question}
            </Text>
          </View>
        ))}
      </Card>
    </Screen>
  );
}

const styles = StyleSheet.create({
  lessonList: { gap: 10 },
  lesson: {
    minHeight: 92,
    borderWidth: 1,
    borderRadius: 17,
    padding: 14,
    flexDirection: "row",
    alignItems: "center",
    gap: 11,
  },
  number: { alignSelf: "flex-start", fontSize: 11, fontWeight: "900" },
  lessonIcon: {
    width: 46,
    height: 46,
    borderRadius: 15,
    alignItems: "center",
    justifyContent: "center",
  },
  lessonCopy: { flex: 1, gap: 4 },
  lessonTitle: { fontSize: 16, fontWeight: "800" },
  lessonBody: { fontSize: 12, lineHeight: 17 },
  pressed: { opacity: 0.82, transform: [{ scale: 0.99 }] },
  questionRow: {
    minHeight: 44,
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 10,
  },
  questionNumber: {
    width: 25,
    height: 25,
    textAlign: "center",
    textAlignVertical: "center",
    fontSize: 12,
    fontWeight: "900",
  },
  question: { flex: 1, fontSize: 14, lineHeight: 20, fontWeight: "600" },
});
