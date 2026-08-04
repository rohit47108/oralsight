import { useState } from "react";
import { router } from "expo-router";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { Screen } from "@/components/Screen";
import { Button, Card, SectionTitle } from "@/components/Ui";
import { KNOWLEDGE_QUESTIONS } from "@/lib/education";
import { useAppTheme } from "@/theme";

export default function QuestionsRoute() {
  const theme = useAppTheme();
  const [index, setIndex] = useState(0);
  const [answer, setAnswer] = useState<number | null>(null);
  const [score, setScore] = useState(0);
  const [finished, setFinished] = useState(false);
  const question = KNOWLEDGE_QUESTIONS[index] ?? KNOWLEDGE_QUESTIONS[0]!;
  const correct = answer === question.correctIndex;

  const continueQuiz = () => {
    if (index === KNOWLEDGE_QUESTIONS.length - 1) {
      setFinished(true);
      return;
    }
    setIndex((value) => value + 1);
    setAnswer(null);
  };

  const restart = () => {
    setIndex(0);
    setAnswer(null);
    setScore(0);
    setFinished(false);
  };

  return (
    <Screen
      title="Quick knowledge check"
      eyebrow={
        finished ? "Complete" : `${index + 1} of ${KNOWLEDGE_QUESTIONS.length}`
      }
      action={
        <Button label="Back" variant="ghost" onPress={() => router.back()} />
      }
    >
      {finished ? (
        <Card accent="teal">
          <View style={[styles.resultIcon, { backgroundColor: theme.mint }]}>
            <Ionicons name="checkmark" size={34} color={theme.primary} />
          </View>
          <Text
            accessibilityRole="header"
            style={[styles.resultTitle, { color: theme.text }]}
          >
            {score} of {KNOWLEDGE_QUESTIONS.length} correct
          </Text>
          <Text style={[styles.resultBody, { color: theme.secondaryText }]}>
            You can repeat this check at any time. It teaches product limits and
            capture habits; it is not a health assessment.
          </Text>
          <Button label="Repeat questions" onPress={restart} />
          <Button
            label="Return to Learn"
            variant="ghost"
            onPress={() => router.back()}
          />
        </Card>
      ) : (
        <>
          <View style={[styles.progressTrack, { backgroundColor: theme.line }]}>
            <View
              style={[
                styles.progressFill,
                {
                  backgroundColor: theme.primary,
                  width: `${((index + 1) / KNOWLEDGE_QUESTIONS.length) * 100}%`,
                },
              ]}
            />
          </View>
          <Card>
            <SectionTitle title={question.prompt} icon="help-circle-outline" />
            <View accessibilityRole="radiogroup" style={styles.choices}>
              {question.choices.map((choice, choiceIndex) => {
                const selected = answer === choiceIndex;
                return (
                  <Pressable
                    key={choice}
                    accessibilityRole="radio"
                    accessibilityState={{
                      checked: selected,
                      disabled: answer !== null,
                    }}
                    disabled={answer !== null}
                    onPress={() => {
                      setAnswer(choiceIndex);
                      if (choiceIndex === question.correctIndex) {
                        setScore((value) => value + 1);
                      }
                    }}
                    style={({ pressed }) => [
                      styles.choice,
                      {
                        borderColor: selected ? theme.primary : theme.border,
                        backgroundColor: selected ? theme.mint : theme.surface,
                      },
                      pressed && styles.pressed,
                    ]}
                  >
                    <Text
                      style={[styles.choiceLetter, { color: theme.primary }]}
                    >
                      {String.fromCharCode(65 + choiceIndex)}
                    </Text>
                    <Text style={[styles.choiceText, { color: theme.text }]}>
                      {choice}
                    </Text>
                  </Pressable>
                );
              })}
            </View>
          </Card>
          {answer !== null ? (
            <Card accent={correct ? "teal" : "amber"}>
              <Text style={[styles.feedbackTitle, { color: theme.text }]}>
                {correct ? "Correct" : "The best answer is shown below"}
              </Text>
              {!correct ? (
                <Text style={[styles.correctAnswer, { color: theme.primary }]}>
                  {question.choices[question.correctIndex]}
                </Text>
              ) : null}
              <Text
                style={[styles.feedbackBody, { color: theme.secondaryText }]}
              >
                {question.explanation}
              </Text>
              <Button
                label={
                  index === KNOWLEDGE_QUESTIONS.length - 1
                    ? "See result"
                    : "Next question"
                }
                onPress={continueQuiz}
              />
            </Card>
          ) : null}
        </>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  progressTrack: { height: 6, overflow: "hidden" },
  progressFill: { height: "100%" },
  choices: { gap: 9 },
  choice: {
    minHeight: 58,
    borderWidth: 1,
    borderRadius: 14,
    padding: 12,
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  choiceLetter: { width: 26, fontSize: 13, fontWeight: "900" },
  choiceText: { flex: 1, fontSize: 14, lineHeight: 20, fontWeight: "700" },
  pressed: { opacity: 0.82, transform: [{ scale: 0.99 }] },
  feedbackTitle: { fontSize: 17, fontWeight: "800" },
  correctAnswer: { fontSize: 14, lineHeight: 20, fontWeight: "800" },
  feedbackBody: { fontSize: 14, lineHeight: 21 },
  resultIcon: {
    width: 64,
    height: 64,
    borderRadius: 22,
    alignItems: "center",
    justifyContent: "center",
    alignSelf: "center",
  },
  resultTitle: { fontSize: 26, fontWeight: "900", textAlign: "center" },
  resultBody: { fontSize: 14, lineHeight: 21, textAlign: "center" },
});
