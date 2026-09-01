# Stoma3D competition demonstration script

Target duration: **2:50**. Keep the public video between one and three minutes,
add captions, and use only synthetic or expressly licensed mouth images. Images
used during recording are supplied through the real camera or photo picker; none
are preinstalled in Stoma3D.

## 0:00-0:18 - Team, audience, and problem

**Screen:** Title card with the names of students who actually contributed,
school, district, and "Research application - not a diagnosis." Open consent.

**Narration:** Introduce the actual team and explain that Stoma3D gives people
a structured way to photograph visible mouth concerns and discuss changes with a
professional. State that a phone photograph cannot diagnose cancer or prove an
area is harmless.

## 0:18-0:38 - Consent and symptom intake

**Screen:** Complete consent and one adaptive symptom follow-up using fictional
answers.

**Narration:** Explain that care priority stays disabled until a clinician has
approved the deterministic rule file. The current app gives neutral seek-care
information only.

## 0:38-1:15 - Real eight-region capture

**Screen:** Open a scan containing seven previously captured, expressly licensed
images. Select the last region, then capture or choose its real source image.
Show motion and quality feedback, image review, the mouth-only privacy
confirmation, and region confirmation. Finish at 8/8.

**Narration:** Explain the eight fixed regions, pre-upload metadata removal and
basic quality checks, manual privacy confirmation, encrypted local storage, and
sanitized upload. Say that green means captured, not healthy. Call the 3D view an
oral observation map, not a personalized digital twin.

## 1:15-1:45 - Honest analysis state

**Screen:** Open the result returned for the submitted image. Show the real
anatomy-region confirmation followed by the segmentation abstention, then open
the model card.

**Narration:** Explain that the released anatomy model checks only whether the
photo matches the selected mouth region. The locked lesion-segmentation and
disease experiments failed their required gates, so Stoma3D shows no candidate
mask, disease class, or diagnosis.

## 1:45-2:12 - History and longitudinal boundary

**Screen:** Show saved real observations and the timeline. If released models do
not make two observations eligible, show the comparison empty state rather than a
fixture result. If models later pass, show the two-stage suggestion, full-image
review, mandatory confirmation, and confidence-gated result from that locked
build.

**Narration:** Explain that Stoma3D never links two observations automatically.
Change stays hidden unless the user confirms the pair and every model,
registration, and repeated-capture gate passes.

## 2:12-2:35 - Local report and deletion

**Screen:** Generate the local PDF after 8/8, open the operating-system share
sheet, cancel it, and show delete-all.

**Narration:** Explain that the report is for professional discussion, is not
treatment advice, is encrypted at rest, and is decrypted temporarily only for
the share sheet. State that physical-device deletion and backup behavior still
need the documented device-matrix verification.

## 2:35-2:50 - Architecture, disclosure, and close

**Screen:** Show the architecture: installed Expo app, versioned contracts,
stateless FastAPI service, and release-gated model runtime. End on limitations.

**Narration:** Name each student's work truthfully, disclose substantial AI and
open-source assistance, and close by saying Stoma3D organizes observations
without pretending a phone can diagnose.

## Recording gate

- [ ] Runtime is 2:45-2:55 and the public upload is no more than three minutes.
- [ ] Every shown input enters through the real camera or picker.
- [ ] No preinstalled image, fixture response, fake score, or unavailable feature
      is presented as real.
- [ ] Captions, readable text, non-color status labels, and reduced motion are
      verified in the recorded build.
- [ ] No participant data, notification, secret, local path, API key, or
      restricted image appears.
- [ ] Every shown feature exists at the locked commit.
- [ ] Every contribution and review claim is backed by evidence and approved by
      the named student.
