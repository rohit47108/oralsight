# OralSight design system

This file is the shared visual and interaction source of truth for the public
site, patient workspace, clinician workspace, and native app. Page-specific
files under `pages/` may narrow these rules but may not change product claims,
safety language, or the meaning of status colors.

## Design read

OralSight is a trust-first oral observation product for patients and clinicians.
It should feel calm, precise, private, and usable under imperfect real-world
conditions. It is not a generic wellness brand or a hospital dashboard.

- Design variance: 4/10. Clear structure with a few asymmetric editorial moments.
- Motion: 3/10. Immediate press feedback and short state transitions only.
- Density: 5/10. Patient screens stay calm; clinician screens carry more detail.

The automatically suggested wellness palette, serif typography, reviews, and
ratings were rejected. They conflict with the existing OralSight identity and
would imply evidence or social proof the product does not have.

## Product language

- Write in plain, active sentences.
- Name what a person can do: `Start scan`, `Retake photo`, `Create share`.
- Use `observation`, `candidate area`, and `professional review`; do not present
  model output as a diagnosis.
- Every screen and generated artifact includes: `This result is not a diagnosis.`
- Empty, loading, offline, unsupported, and failed states must say what happened
  and the next available action.
- Never invent ratings, patient stories, accuracy claims, measurements, or
  clinician endorsements.

## Color

Teal is the single action color. Amber communicates a decision or caution, not
disease risk. Coral/red is reserved for errors and destructive actions. Status
always includes text or an icon so color is never the only signal.

### Web light tokens

| Role             | Value     |
| ---------------- | --------- |
| Porcelain canvas | `#f7faf8` |
| Paper surface    | `#ffffff` |
| Soft surface     | `#eef5f2` |
| Primary text     | `#142d31` |
| Secondary text   | `#50666a` |
| Action           | `#096d67` |
| Action hover     | `#075650` |
| Action soft      | `#dceee9` |
| Border           | `#cddbd7` |
| Strong border    | `#a8bfba` |
| Caution          | `#a55710` |
| Caution surface  | `#fff0d9` |
| Destructive      | `#a42e3a` |

### Native themes

Native UI uses the semantic roles in `apps/mobile/src/theme.ts`. It supports
light, dark, and increased-contrast variants. Components consume semantic roles
instead of adding per-screen colors.

## Type

- Use the platform system sans family. It gives iOS Dynamic Type, Android font
  scaling, and web rendering without another network request.
- Headlines are compact, weight 700-760, with slightly tighter tracking.
- Body copy is at least 16px on web and follows platform body styles on native.
- Long text stays near 65 characters per line.
- Data values use tabular figures when alignment matters.

## Shape and spacing

- Controls: 10px radius on web; native platform shape roles on iOS and Android.
- Substantial panels: 14px radius.
- Paper/report previews: 2-6px radius so they still read as documents.
- Pills are reserved for filters or compact statuses, never used as decoration.
- Spacing follows a 4/8 unit rhythm: 4, 8, 12, 16, 24, 32, 48, 64.
- Use borders and whitespace before adding another card or shadow.

## Navigation

- Web workspaces use a stable left rail on desktop and compact bottom navigation
  on small screens.
- Native uses no more than five labeled top-level tabs and preserves system back
  gestures.
- Every deep screen has a predictable back or close route.
- Destructive account actions remain separate from ordinary navigation.
- All key private routes use ownership checks and `private, no-store` responses.

## Controls and feedback

- Minimum target: 44x44pt on iOS, 48x48dp on Android, 44x44px on web.
- Press feedback begins immediately and does not move surrounding layout.
- Disable repeat submission while work is pending; show the current state in the
  control or adjacent status region.
- Form labels remain visible. Field errors sit next to the affected field and
  include a recovery step.
- Focus rings are always visible for keyboard users.
- Destructive operations require a clear confirmation and report completion.

## Motion

- Default UI feedback: 120-200ms ease-out.
- Drawers and sheets: native spring or 220-300ms platform transition.
- Comparison dragging follows the pointer or finger 1:1 and can be interrupted.
- Never animate a repeated keyboard action or block interaction during motion.
- Animate transform and opacity only where practical.
- Reduced motion replaces movement with a short crossfade or an instant update.
- No looping decorative animation, parallax, glow, bounce, or scroll hijacking.

## Responsive and adaptive behavior

- Verify web at 375, 768, 1024, and 1440px.
- Verify native on small and large phones, tablet, portrait, and landscape.
- Respect safe areas, the software keyboard, display cutouts, and system bars.
- Multi-column layouts collapse explicitly below 768px.
- Reserve space for images, 3D viewers, and async content to prevent jumping.
- Heavy 3D/media viewers load only when needed and always have an accessible
  text fallback.

## Required states

Every networked or data-driven surface implements:

- loading with a layout-shaped skeleton or clear progress;
- empty with one useful next action;
- offline with queued/local behavior explained;
- permission denied with a route to settings or another input path;
- unsupported or abstained without substituted fixture data;
- timeout/malformed response with retry;
- success confirmation;
- deletion/revocation completion.

## Accessibility release gate

- Text contrast at least 4.5:1; large text and meaningful graphics at least 3:1.
- Logical heading and screen-reader order.
- Descriptive labels and hints for icons, maps, camera controls, and charts.
- Keyboard operation for the clinician workspace and comparison controls.
- Non-color labels for quality, coverage, confidence, and job status.
- Dynamic text cannot hide controls or truncate safety wording.
- Reduced motion and increased contrast preserve full function.
- Charts and 3D surfaces include a readable text/table alternative.

## Pre-release visual check

- One icon family and consistent icon sizes per platform.
- One action color and one radius system.
- No emojis as structural icons.
- No generic sample patient cases in authenticated screens.
- No fake product screenshots, ratings, statistics, or endorsements.
- No unlabelled icon-only actions.
- No content behind fixed bars or safe areas.
- No horizontal overflow at supported widths.
- Light, dark, increased contrast, large text, and reduced motion checked.
- Loading, empty, error, offline, and destructive flows checked.
