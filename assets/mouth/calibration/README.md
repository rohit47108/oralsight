# OralSight calibration card

The A4 and Letter cards are generated at 300 DPI by
`scripts/generate_calibration_cards.py`.

- Print at **100%** or **Actual size**. Never use “Fit to page.”
- Confirm that the printed reference line measures exactly 50 mm.
- Keep the card outside the mouth. It must not touch tissue or an observation.
- Millimeter estimates remain unavailable unless the app detects marker 17 from
  `DICT_4X4_50`, confirms the card version and scale, and passes its pose,
  proximity, repeatability, and device-release checks.
- The four neutral patches may normalize only the approximate mean-redness and
  mean-brightness descriptors. OralSight applies that optional correction only
  when marker 17, same-plane confirmation, all four unobstructed patches, and
  bounded fit checks pass. It never changes the stored image, candidate mask,
  anatomy or quality checks, texture descriptor, or care guidance.
- A printed card does not make OralSight a clinical measuring instrument.

The QR contains only the public card schema, version, marker dictionary, marker
ID, marker size, and reference-bar size. It contains no user or health data.
