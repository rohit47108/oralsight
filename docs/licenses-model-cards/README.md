# Licenses, provenance, and model cards

Nothing enters a build, training run, evaluation, or demonstration until its row in
`ASSET_DATA_INVENTORY.csv` is complete and `eligible_for_use` is `yes`. That field is a
narrow repository-policy decision for the row's stated purpose; it is not proof of final
human license review, mobile compatibility, clinical suitability, or release approval.

Rules:

- Record the original source, exact license terms, permitted purpose, checksum, review
  owner, and review evidence. “Publicly available” is not a license.
- Keep restricted medical data outside Git and outside public/cloud CI.
- Treat patient-level identifiers as pseudonymous and source-scoped; never use names,
  contact details, medical-record numbers, or capture GPS metadata.
- Record train/validation/test assignment at patient level, not image level.
- Demo assets must be synthetic, team-created, or expressly licensed for public display.
- AI-generated and open-source assets still require provenance and disclosure.
- A trained artifact receives a model card only after its artifact hash, dataset versions,
  code version, aggregate evaluation, subgroup report, limitations, and gate decision are
  locked.

The deployed service response from `GET /v1/model-card` is authoritative for runtime
model versions, hashes, enabled heads, and gates. The public source release enables
anatomy matching and receives the competition segmentation model from a private,
hash-verified deployment bundle. Appearance, disease-category research, and automated
re-identification remain disabled.

The current eligible asset rows are deliberately narrow: the `procedural-v1`
renderer and manifest, plus an exact CC0 synthetic fixture used only by isolated
backend and contract tests. That fixture is not imported by the mobile app. Its
inventory hash is the JSON file hash; its notes separately pin the decoded PNG
hash. Editing any audited file requires recalculating its SHA-256, updating the
inventory/manifest, and rerunning the repository audit workflow.

`SEGMENTATION_SMART_OM_ONLY_ATTEMPT.json` records the failed 2026-08-10 attempt
to replace the Autooral-assisted segmentation artifact with a SMART-OM-only
CC BY 4.0 model. The failed model weights are not bundled. The existing competition
weight stays outside public Git history and is used only through the private
deployment bundle.

The OralSight source repository uses the MIT License. The CC0 declarations for the
procedural map and synthetic fixture and the licenses of third-party dependencies and
model assets still apply to those items separately.

The locked dependency inventory is generated from `pnpm-lock.yaml` and `uv.lock`:

- `THIRD_PARTY_NOTICES.md` contains the resolved package list and exact legal texts
  present in the installed release environment.
- `THIRD_PARTY_SBOM.cdx.json` is the corresponding CycloneDX 1.5 inventory.
- `scripts/generate_third_party_notices.py --check` fails when those checked
  artifacts no longer match the lockfiles.

Packages locked only for another operating system or optional research environment are
listed as not installed and require their own license-text review before they are used.
