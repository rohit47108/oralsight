import { useMemo, useState } from "react";
import { router } from "expo-router";
import { StyleSheet, Text, TextInput, View } from "react-native";
import type { CaptureProtocol } from "@oralsight/contracts";

import { APP_TAGLINE, NEUTRAL_SEEK_CARE_COPY } from "@/constants";
import { OralObservationMapIntroduction } from "@/components/OralObservationMap";
import { Screen } from "@/components/Screen";
import { SymptomBodyMap } from "@/components/SymptomBodyMap";
import { Button, Card, ChoiceChip, SectionTitle } from "@/components/Ui";
import { useOralSightStore } from "@/store/useOralSightStore";
import { useAppTheme } from "@/theme";
import type { AgeRange, IntakeProfile } from "@/types";

const ageOptions: Array<{ value: AgeRange; label: string }> = [
  { value: "under_18", label: "Under 18" },
  { value: "18_39", label: "18–39" },
  { value: "40_64", label: "40–64" },
  { value: "65_plus", label: "65+" },
  { value: "prefer_not_to_say", label: "Prefer not to say" },
];

const symptoms = [
  "pain",
  "bleeding",
  "numbness",
  "difficulty swallowing",
  "jaw pain",
  "neck lump",
  "ear pain",
];

export default function OnboardingRoute() {
  const theme = useAppTheme();
  const finishConsentAndStartSession = useOralSightStore(
    (state) => state.finishConsentAndStartSession,
  );
  const [ageRange, setAgeRange] = useState<AgeRange>("prefer_not_to_say");
  const [assisted, setAssisted] = useState(false);
  const [firstNoticed, setFirstNoticed] = useState("");
  const [durationDays, setDurationDays] = useState("");
  const [selectedSymptoms, setSelectedSymptoms] = useState<string[]>([]);
  const [change, setChange] = useState<IntakeProfile["change"]>("not_sure");
  const [tobaccoExposure, setTobaccoExposure] =
    useState<IntakeProfile["tobaccoExposure"]>("prefer_not_to_say");
  const [alcoholExposure, setAlcoholExposure] =
    useState<IntakeProfile["alcoholExposure"]>("prefer_not_to_say");
  const [bleedingFrequency, setBleedingFrequency] =
    useState<IntakeProfile["bleedingFrequency"]>();
  const [bleedingDuration, setBleedingDuration] = useState("");
  const [previousConditions, setPreviousConditions] = useState("");
  const [professionallyExamined, setProfessionallyExamined] = useState(false);
  const [protocol, setProtocol] = useState<CaptureProtocol>(
    "standard_eight_region",
  );
  const [understood, setUnderstood] = useState(false);
  const [localConsent, setLocalConsent] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const canContinue = useMemo(
    () => understood && localConsent && firstNoticed.trim().length > 0,
    [firstNoticed, localConsent, understood],
  );

  const toggleSymptom = (symptom: string) =>
    setSelectedSymptoms((current) =>
      current.includes(symptom)
        ? current.filter((value) => value !== symptom)
        : [...current, symptom],
    );

  const finish = async () => {
    if (!canContinue || saving) return;
    setSaving(true);
    setSaveError(null);
    const profile: IntakeProfile = {
      ageRange,
      assisted,
      firstNoticed: firstNoticed.trim(),
      ...(durationDays ? { durationDays: Number(durationDays) } : {}),
      symptoms: selectedSymptoms,
      ...(selectedSymptoms.includes("bleeding")
        ? { bleedingFrequency, bleedingDuration }
        : {}),
      change,
      tobaccoExposure,
      alcoholExposure,
      previousConditions: previousConditions.trim(),
      professionallyExamined,
    };
    try {
      await finishConsentAndStartSession(profile, protocol);
      router.replace("/(tabs)/scan");
    } catch (error) {
      setSaveError(
        error instanceof Error
          ? error.message
          : "The protected intake could not be saved.",
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <Screen title="A clearer self-check" eyebrow="Welcome to OralSight">
      <Text style={[styles.tagline, { color: theme.primary }]}>
        {APP_TAGLINE}
      </Text>
      <OralObservationMapIntroduction />
      <Card accent="amber">
        <SectionTitle title="What this prototype does" icon="eye-outline" />
        <Text style={[styles.body, { color: theme.text }]}>
          OralSight helps you capture consistent images, describe visible
          patterns, and track visual changes for professional discussion.
        </Text>
        <Text style={[styles.strong, { color: theme.text }]}>
          It cannot diagnose cancer or confirm that an area is harmless.
        </Text>
      </Card>

      <Card>
        <SectionTitle
          title="Choose a capture method"
          subtitle="You can start with the shorter scan or collect more views for follow-up alignment."
          icon="camera-outline"
        />
        <View accessibilityRole="radiogroup" style={styles.chips}>
          <ChoiceChip
            label="Standard · 8 photos"
            selected={protocol === "standard_eight_region"}
            accessibilityRole="radio"
            fullWidth
            onPress={() => setProtocol("standard_eight_region")}
          />
          <Text style={[styles.optionHelp, { color: theme.secondaryText }]}>
            One accepted image for each region.
          </Text>
          <ChoiceChip
            label="Detailed · 24 photos"
            selected={protocol === "detailed_multi_angle"}
            accessibilityRole="radio"
            fullWidth
            onPress={() => setProtocol("detailed_multi_angle")}
          />
          <Text style={[styles.optionHelp, { color: theme.secondaryText }]}>
            Straight, left, and right views for every region.
          </Text>
          <ChoiceChip
            label="Guided sweep · 8 short videos"
            selected={protocol === "guided_video_sweep"}
            accessibilityRole="radio"
            fullWidth
            onPress={() => setProtocol("guided_video_sweep")}
          />
          <Text style={[styles.optionHelp, { color: theme.secondaryText }]}>
            A six-second camera sweep selects three quality-checked frames. The
            raw video is deleted after frame selection.
          </Text>
        </View>
      </Card>

      <Card>
        <SectionTitle
          title="About this observation"
          subtitle="These answers provide report context. They do not create a diagnosis."
          icon="clipboard-outline"
        />
        <Text style={[styles.label, { color: theme.text }]}>Age range</Text>
        <View accessibilityRole="radiogroup" style={styles.chips}>
          {ageOptions.map((option) => (
            <ChoiceChip
              key={option.value}
              label={option.label}
              selected={ageRange === option.value}
              accessibilityRole="radio"
              fullWidth
              onPress={() => setAgeRange(option.value)}
            />
          ))}
        </View>
        <Text style={[styles.label, { color: theme.text }]}>
          Who is being assisted?
        </Text>
        <View accessibilityRole="radiogroup" style={styles.chips}>
          <ChoiceChip
            label="Myself"
            selected={!assisted}
            accessibilityRole="radio"
            fullWidth
            onPress={() => setAssisted(false)}
          />
          <ChoiceChip
            label="Someone I’m helping"
            selected={assisted}
            accessibilityRole="radio"
            fullWidth
            onPress={() => setAssisted(true)}
          />
        </View>
        <Text style={[styles.label, { color: theme.text }]}>
          When was the area first noticed? (required)
        </Text>
        <TextInput
          accessibilityLabel="Date or approximate time first noticed"
          accessibilityHint="Required before the intake can be saved"
          placeholder="Example: 3 days ago or July 18"
          placeholderTextColor={theme.secondaryText}
          value={firstNoticed}
          onChangeText={setFirstNoticed}
          style={[
            styles.input,
            {
              borderColor: theme.border,
              color: theme.text,
              backgroundColor: theme.background,
            },
          ]}
        />
        <Text style={[styles.label, { color: theme.text }]}>
          About how many days ago? (optional)
        </Text>
        <TextInput
          accessibilityLabel="Approximate number of days since first noticed"
          placeholder="Example: 3"
          placeholderTextColor={theme.secondaryText}
          value={durationDays}
          onChangeText={(value) =>
            setDurationDays(value.replaceAll(/\D/g, "").slice(0, 5))
          }
          keyboardType="number-pad"
          inputMode="numeric"
          maxLength={5}
          style={[
            styles.input,
            {
              borderColor: theme.border,
              color: theme.text,
              backgroundColor: theme.background,
            },
          ]}
        />
        <Text style={[styles.label, { color: theme.text }]}>
          Reported symptoms and locations (optional)
        </Text>
        <SymptomBodyMap selected={selectedSymptoms} onToggle={toggleSymptom} />
        <View style={styles.chips}>
          {symptoms.map((symptom) => (
            <ChoiceChip
              key={symptom}
              label={symptom}
              selected={selectedSymptoms.includes(symptom)}
              onPress={() => toggleSymptom(symptom)}
              accessibilityRole="checkbox"
              fullWidth
            />
          ))}
        </View>
        {selectedSymptoms.includes("bleeding") ? (
          <View style={[styles.adaptive, { backgroundColor: theme.mint }]}>
            <Text style={[styles.label, { color: theme.text }]}>
              Bleeding details
            </Text>
            <View accessibilityRole="radiogroup" style={styles.chips}>
              {(["once", "occasionally", "often"] as const).map((value) => (
                <ChoiceChip
                  key={value}
                  label={value}
                  selected={bleedingFrequency === value}
                  accessibilityRole="radio"
                  fullWidth
                  onPress={() => setBleedingFrequency(value)}
                />
              ))}
            </View>
            <TextInput
              accessibilityLabel="Bleeding duration"
              placeholder="How long has this occurred?"
              placeholderTextColor={theme.secondaryText}
              value={bleedingDuration}
              onChangeText={setBleedingDuration}
              style={[
                styles.input,
                {
                  borderColor: theme.border,
                  color: theme.text,
                  backgroundColor: theme.surface,
                },
              ]}
            />
          </View>
        ) : null}
        <Text style={[styles.label, { color: theme.text }]}>
          Has it changed?
        </Text>
        <View accessibilityRole="radiogroup" style={styles.chips}>
          {(
            [
              ["not_sure", "Not sure"],
              ["no_change", "No change"],
              ["slow_change", "Slow change"],
              ["rapid_change", "Rapid change"],
            ] as const
          ).map(([value, label]) => (
            <ChoiceChip
              key={value}
              label={label}
              selected={change === value}
              accessibilityRole="radio"
              fullWidth
              onPress={() => setChange(value)}
            />
          ))}
        </View>
        <Text style={[styles.label, { color: theme.text }]}>
          Tobacco exposure (optional)
        </Text>
        <View accessibilityRole="radiogroup" style={styles.chips}>
          {(
            [
              ["none", "None"],
              ["past", "Past"],
              ["current", "Current"],
              ["prefer_not_to_say", "Prefer not to say"],
            ] as const
          ).map(([value, label]) => (
            <ChoiceChip
              key={value}
              label={label}
              selected={tobaccoExposure === value}
              accessibilityRole="radio"
              fullWidth
              onPress={() => setTobaccoExposure(value)}
            />
          ))}
        </View>
        <Text style={[styles.label, { color: theme.text }]}>
          Alcohol exposure (optional)
        </Text>
        <View accessibilityRole="radiogroup" style={styles.chips}>
          {(
            [
              ["none", "None"],
              ["some", "Some"],
              ["frequent", "Frequent"],
              ["prefer_not_to_say", "Prefer not to say"],
            ] as const
          ).map(([value, label]) => (
            <ChoiceChip
              key={value}
              label={label}
              selected={alcoholExposure === value}
              accessibilityRole="radio"
              fullWidth
              onPress={() => setAlcoholExposure(value)}
            />
          ))}
        </View>
        <TextInput
          accessibilityLabel="Previous oral conditions"
          placeholder="Previous oral conditions (optional)"
          placeholderTextColor={theme.secondaryText}
          value={previousConditions}
          onChangeText={setPreviousConditions}
          multiline
          style={[
            styles.input,
            styles.multiline,
            {
              borderColor: theme.border,
              color: theme.text,
              backgroundColor: theme.background,
            },
          ]}
        />
        <ChoiceChip
          label="Already examined by a professional"
          selected={professionallyExamined}
          onPress={() => setProfessionallyExamined((value) => !value)}
          accessibilityRole="checkbox"
          fullWidth
        />
      </Card>

      <Card>
        <SectionTitle
          title="Consent and privacy"
          icon="shield-checkmark-outline"
        />
        <ChoiceChip
          label="I understand this is non-diagnostic"
          selected={understood}
          onPress={() => setUnderstood((value) => !value)}
          accessibilityRole="checkbox"
          fullWidth
        />
        <ChoiceChip
          label="I consent to encrypted local storage and chosen analysis requests"
          selected={localConsent}
          onPress={() => setLocalConsent((value) => !value)}
          accessibilityRole="checkbox"
          fullWidth
        />
        <Text style={[styles.small, { color: theme.secondaryText }]}>
          Images rejected by the on-device checks are not saved or uploaded.
          Confirmed images are re-encoded to remove metadata before a transient
          service check. A service rejection removes the protected local copy.
          You can delete all local data and rotate encryption keys at any time.
        </Text>
      </Card>
      <Text style={[styles.seekCare, { color: theme.secondaryText }]}>
        {NEUTRAL_SEEK_CARE_COPY}
      </Text>
      <Button
        label="Save intake and start scan"
        icon="arrow-forward"
        loading={saving}
        loadingLabel="Saving protected intake..."
        onPress={() => {
          void finish();
        }}
        disabled={!canContinue || saving}
      />
      {saveError ? (
        <Text
          accessibilityRole="alert"
          style={[styles.saveError, { color: theme.danger }]}
        >
          {saveError}
        </Text>
      ) : null}
    </Screen>
  );
}

const styles = StyleSheet.create({
  tagline: { fontSize: 16, fontWeight: "800", marginTop: -9 },
  body: { fontSize: 15, lineHeight: 22 },
  strong: { fontSize: 15, fontWeight: "800", lineHeight: 22 },
  label: { fontSize: 14, fontWeight: "800", marginTop: 5 },
  chips: {
    width: "100%",
    gap: 8,
  },
  input: {
    minHeight: 48,
    borderRadius: 14,
    borderWidth: 1,
    paddingHorizontal: 14,
    fontSize: 15,
  },
  multiline: { minHeight: 82, paddingTop: 12, textAlignVertical: "top" },
  adaptive: { padding: 13, borderRadius: 16, gap: 10 },
  small: { fontSize: 12, lineHeight: 18 },
  optionHelp: {
    fontSize: 12,
    lineHeight: 17,
    marginTop: -3,
    paddingHorizontal: 4,
  },
  seekCare: {
    textAlign: "center",
    fontSize: 12,
    lineHeight: 18,
    paddingHorizontal: 12,
  },
  saveError: {
    textAlign: "center",
    fontSize: 13,
    lineHeight: 19,
    fontWeight: "700",
  },
});
