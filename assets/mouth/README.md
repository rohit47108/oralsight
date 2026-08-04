# Oral observation map asset

The audited v1 asset is `procedural-v1`: Codex-assisted geometry created for OralSight
and rendered from React Three Fiber primitives in
`apps/mobile/src/components/OralObservationMap.tsx`. There is no GLB, imported patient
anatomy, or commercial mesh in this version. `manifest.json` binds the implementation
path and SHA-256 to the canonical eight `regionId`/`meshId` mappings.

The procedural asset definition is released as CC0-1.0, as recorded in the manifest.
Runtime libraries retain their own licenses and must remain in the open-source
disclosure.

Persisted pins store `regionId`, `meshId`, UV coordinates, and the exact
`assetVersion: "procedural-v1"`; world coordinates are derived when rendered. Any later
binary mesh is a new asset version and remains ineligible until its source, license,
checksum, region mapping, and platform behavior pass the asset audit.
