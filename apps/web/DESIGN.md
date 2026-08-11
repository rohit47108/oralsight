# OralSight public site design

## Direction

The public site is a guided-scan editorial field. The fixed four-step flow and
eight-region mouth guide are the composition, not content placed inside a standard
software landing-page template. The first view uses an asymmetric rail, direct
promise, capture screen, and anatomical guide.

## Palette

- Porcelain ground: `#f7faf8`
- White paper: `#ffffff`
- Graphite: `#142d31`
- Mineral teal: `#096d67`
- Amber attention: `#b96814`
- Rules: `#cddbd7`

Teal is the only action color. Amber marks meaningful caution or focus. There are
no gradients, glass effects, or decorative medical color coding.

## Type and shape

The site uses the local system sans stack. Headlines are compact, heavy, and
slightly tightened. Body copy stays below 65 characters where practical. Controls
use a 10px radius; substantial panels use 14px; the report preview remains nearly
square like paper.

## Layout and motion

Wide screens present four distinct hero columns. Narrow screens become a reading
sequence: promise, capture, four-step rail, then region guide. Lines and whitespace
separate information; cards are used only for real artifacts such as the phone,
share controls, and report sheet.

The phone enters once with a short ease-out. Hover movement is restricted to fine
pointers, and reduced-motion settings remove positional animation.

## Content

Copy is direct and non-diagnostic. Examples never contain fabricated patient data
or model results. The shared footer places `This result is not a diagnosis.` on
every page.

## Authenticated product

The patient and clinician workspaces are quiet operating surfaces, not smaller
landing pages. A mineral paper sidebar, plain data ledgers, and precise status
language carry the same identity at higher density. Teal marks navigation and
primary actions; amber is reserved for pending review or a required decision.

Desktop uses a stable left rail. Compact screens use a platform-familiar bottom
navigation with a small top bar. Patient records are opened only after the
platform verifies ownership. Clinician screens remain empty until a patient has
created a valid share; no sample cases or invented findings fill the workspace.

Loading uses restrained skeleton lines. Empty and error states state what is
missing, what was protected, and the next available action. All private routes
send `Cache-Control: private, no-store`.
