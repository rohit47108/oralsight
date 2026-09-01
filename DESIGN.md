# Stoma3D design system

## Product character

Stoma3D is a safety-first native health tool for everyday users. It should feel
calm, clear, private, and dependable. It should not look like a game, a diagnostic
device, or a marketing dashboard.

The interface favors:

- direct language;
- native interaction patterns;
- visible system state;
- one main action at a time;
- restrained color and motion; and
- honest unavailable and error states.

## Color

All UI code must use semantic values from `apps/mobile/src/theme.ts`.

Light foundation:

- background: `#F5FAF9`
- surface: `#FFFFFF`
- main text: `#17324D`
- secondary text: `#536A7C`
- border: `#C9D8E0`
- primary teal: `#0B716C`
- danger: `#A42E3A`
- warning: `#7A4D00`

Dark foundation:

- background: `#06171D`
- surface: `#0D222A`
- main text: `#F2FAF8`
- secondary text: `#B9CCCC`
- border: `#36535C`
- primary teal: `#2D9D91`
- danger: `#F27983`
- warning: `#F2C66D`

High-contrast mode increases text, border, and control contrast in both appearance
modes. Status must never rely on color alone.

## Type

Use the platform system font. Shared components apply the app's larger-text
preference. Route-level text must reflow without clipping and should not cap
important instructions to a fixed line count.

- Screen title: 30 on phones, 34 on tablet widths, weight 800
- Section heading: weight 800
- Body: 13 to 15 with at least 1.4 line height
- Supporting text: 11 to 13, never below accessible contrast
- Numeric result: tabular figures when values need comparison

## Layout

- Phone horizontal padding: 20
- Tablet horizontal padding: 32
- Large-screen horizontal padding: 40
- Maximum content width: 840 on tablets and 960 on large screens
- Standard vertical gap: 16
- Minimum interactive target: 48 by 48
- Standard control radius: 14
- Standard panel radius: 16
- Always include top, bottom, left, and right safe areas
- Long forms use automatic keyboard insets and interactive keyboard dismissal

Cards group related information. Do not put every sentence in a separate card.
Debug identifiers, hashes, mesh coordinates, and model details belong in secondary
details, reports, or the model-card screen.

## Components

Buttons:

- one clear primary action per decision;
- secondary for a safe alternative;
- ghost for navigation or low-emphasis actions;
- preserve the action label while loading;
- disable duplicate submissions.

Choice chips:

- checkboxes for independent confirmation;
- radio semantics for mutually exclusive choices;
- selected, checked, and disabled states exposed to assistive technology.

Status panels:

- always include a plain-language title;
- state what happened and what the user can do next;
- unavailable means unavailable, never zero confidence;
- every result surface repeats the non-diagnostic statement through the shared
  screen frame.

Observation map:

- the 3D view is a generic oral observation map, not a personalized digital twin;
- a generated private GLB may project selected capture colors and confirmed pins onto
  the generic surface, but must never be described as reconstructed patient anatomy;
- every region must also be selectable through the synchronized native list;
- pin data stays bound to region ID, named mesh, UV coordinates, and asset version;
- map controls use 48-point targets and visible press feedback.

## Motion

Motion exists only for feedback or state explanation.

- Button and map press feedback: subtle scale or opacity, 100 to 160 ms
- Stability progress: transform-based scale, 160 ms strong ease-out
- Navigation: native stack transition
- OS Reduce Motion and the app preference both disable positional motion
- Never animate layout width, height, margin, padding, top, or left
- No decorative loops, bouncing health results, confetti, or delayed controls

Final bounded motion review verdict: **Approve**. The stability indicator uses a
composited transform, all custom control feedback is short and interruptible, and
the operating-system Reduce Motion setting is honored.

| Before                                 | After                                             | Why                                            |
| -------------------------------------- | ------------------------------------------------- | ---------------------------------------------- |
| Stability animated layout width        | Stability animates `scaleX` for 160 ms            | Avoids repeated layout and paint work          |
| App preference controlled motion alone | OS and app Reduce Motion are combined             | Honors the user's device accessibility setting |
| Map controls were 40 points and static | Controls are 48 points with short press feedback  | Improves reach, confirmation, and target size  |
| Comparison track only accepted taps    | Track supports drag, tap, and screen-reader steps | Makes close image review precise and inclusive |
| 3D renderer failure was a dead end     | Named-region fallback includes a retry action     | Keeps the workflow usable and recoverable      |
| Tablet used the phone bottom tab bar   | Tablet switches to a compact side rail            | Uses wide screens without stretching phone UI  |

## Accessibility

- Every interactive element has a descriptive label and role.
- Use a native list as the accessibility equivalent of the 3D view.
- Text, icons, and shape must reinforce status; color alone is insufficient.
- Loading and error changes use live-region or alert semantics only when new
  information needs announcement.
- The persistent disclaimer is static and is not re-announced as an alert on every
  screen.
- Screen readers, large text, high contrast, rotation, tablets, and reduced motion
  are release-test requirements.

## Content rules

Always say:

- "This result is not a diagnosis."
- "approximate" for image-normalized measurements
- "approximate calibrated estimate" for a millimeter value that passed the physical
  marker and same-plane checks
- "oral observation map"
- "analysis unavailable" when the service cannot produce a validated output

Never claim:

- cancer or harmlessness;
- clinical accuracy;
- uncalibrated or clinically precise millimeter measurement;
- HIPAA compliance;
- a personalized digital twin; or
- that an unavailable model produced a result.
