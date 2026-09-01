# AI and open-source disclosure

This file records the current greenfield build provenance. It must be reconciled with the
locked release commit and the competition portal wording before submission.

## Current AI-assistance record

This initial monorepo was produced with substantial OpenAI Codex assistance in response
to the team's detailed product and engineering blueprint. It must not be represented as
entirely hand-written student code.

| Tool/model                                                                                           | How it was used                                                                                                                                                          | Current verification                                                                                                                                                       | Included output                                                                                 |
| ---------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| OpenAI Codex desktop agent (GPT-5-based; exact deployment identifier was not exposed in the session) | Interpreted the supplied blueprint; generated and revised the greenfield mobile, API, ML, contract, test, CI, and documentation working tree; and ran local verification | The dated, last-known verification snapshot is recorded in `IMPLEMENTATION_STATUS.md`. Student-by-student review, modification, and architecture rehearsal remain required | Yes - substantial source, tests, documentation, procedural geometry, and synthetic fixture work |
| Codex browser/web research workflow                                                                  | Checked the linked primary FDA, FTC, CAC, NJ-06, SMART-OM, and Expo sources while shaping safety and build decisions                                                     | Source links are retained near the relevant claims; rules and guidance must be refreshed before release                                                                    | Research summaries and linked documentation only                                                |

No patient image, restricted dataset, secret, or clinician-confidential material was
provided to the AI workflow. The repository-only backend test image is synthetic
procedural pixel art and is not compiled into the mobile app; the 3D map is generic
procedural geometry and contains no patient anatomy.

## Required student ownership before submission

Each student must review the actual code, make and document meaningful contributions,
run the relevant checks, and be able to explain the full architecture and safety
boundaries. The release evidence should record commits/reviews by owner. If the official
rules or district office require a different level of authorship, the team must obtain a
written answer or change the submission rather than minimizing this disclosure.

## Open-source runtime snapshot

The lockfiles are authoritative for exact resolved versions and transitive packages.
Direct runtime families in this build are:

| Area                 | Direct software used                                                                                                                                                                                                                    | License review status                                                                                                                                       |
| -------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Mobile               | Expo SDK 57 and Expo Router/Camera/Sensors/GL/SecureStore/SQLite/Print/Sharing modules; React 19.2.3; React Native 0.86; Reanimated 4.5; Skia 2.6.2; React Three Fiber 9.4; Three.js 0.181; Zustand 5; Noble crypto packages; base64-js | Locked direct/transitive inventory and installed legal texts are generated in `licenses-model-cards/THIRD_PARTY_NOTICES.md` and `THIRD_PARTY_SBOM.cdx.json` |
| Inference            | FastAPI, Uvicorn, Pydantic, Cryptography, NumPy, OpenCV headless, Pillow, and python-multipart at the exact versions in `uv.lock`                                                                                                       | Locked direct/transitive inventory and installed legal texts are generated in the same notice and SBOM artifacts                                            |
| Research-only extras | PyTorch/Torchvision, DVC, and MLflow are optional `research` extras and are not part of the default inference container                                                                                                                 | Include only if installed or used for the locked evaluation, then disclose exact versions and artifacts                                                     |
| Test/build           | Vitest, TypeScript, Prettier, tsx/esbuild, pytest, httpx, uv, pnpm, Expo CLI/Doctor, and GitHub Actions                                                                                                                                 | Development-only; still include where the competition asks for all open-source assistance                                                                   |

Assets and their exact checksums, provenance, and declared CC0 status are recorded in
`docs/licenses-model-cards/ASSET_DATA_INVENTORY.csv`. Dataset permission requires a
separate evidence review; a paper or download link is not a redistribution license.
No public license has been selected for the Stoma3D source tree itself; asset and
dependency licenses do not grant a source-repository license.

## Final attestation checklist

- [ ] Every student contribution/review is tied to the locked commit.
- [ ] The portal and video disclose substantial Codex assistance in plain language.
- [ ] Every student can explain and defend the complete code path.
- [x] A generated direct/transitive dependency and license inventory matches both lockfiles; optional packages absent from this release environment are explicitly identified for review before use.
- [x] Exact license and notice texts present in the installed release environment ship with the source release.
- [ ] Demo inputs and cached outputs identify input and analysis provenance.
- [ ] No restricted image, patient metadata, secret, or unlicensed model is present in
      the release commit or its history.
- [ ] The video does not claim diagnosis, clinical validation, HIPAA compliance, or FDA
      status.
