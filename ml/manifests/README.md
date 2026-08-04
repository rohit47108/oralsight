# Dataset manifests

`dataset.example.csv` is a header-only template and contains no participant data.
Create `dataset.csv` only in an approved local workspace; it is intentionally ignored by
Git. Use pseudonymous patient IDs scoped to each source dataset, relative paths beneath
an explicit data root, and one of these splits: `train`, `validation`, `test`, or
`external_test`.

`license_status=approved`, `audit_status=approved`, and an allowed consent scope are
required before any baseline training code runs. The validator rejects patient overlap
across splits, duplicate samples, absolute paths, parent traversal, invalid regions, and
task-label mismatches.
