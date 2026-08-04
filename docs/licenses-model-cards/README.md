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
model versions, hashes, enabled heads, and gates. `CURRENT_MODEL_CARD.md` records the
checked-in release: anatomy enabled for region matching and segmentation enabled for
non-diagnostic candidate masks. Appearance, disease-category research, and automated
re-identification remain disabled.

The current eligible asset rows are deliberately narrow: the `procedural-v1`
renderer and manifest, plus an exact CC0 synthetic fixture used only by isolated
backend and contract tests. That fixture is not imported by the mobile app. Its
inventory hash is the JSON file hash; its notes separately pin the decoded PNG
hash. Editing any audited file requires recalculating its SHA-256, updating the
inventory/manifest, and rerunning the repository audit workflow.

No public license has been selected for the OralSight source repository as a whole.
The CC0 declarations for the procedural map and synthetic fixture apply only to those
listed assets. Third-party dependency licenses apply to their respective packages. Do
not infer a repository-wide source license from either category or from package metadata;
the owners must select and add an explicit source license before public distribution.
