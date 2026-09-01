# Repeat-capture comparison evidence

Stoma3D reports approximate normalized change only when all of these are true:

- both images pass privacy and quality checks;
- the user confirms that they show the same observation;
- the released segmentation model returns a candidate in both images;
- geometric registration has at least a 0.60 inlier ratio and no more than
  0.03 image-diagonal reprojection error; and
- approved repeat-photo evidence has a 95th-percentile registered-area error
  of no more than 0.10.

Run the evaluator only on expressly approved test-split image pairs that were
manually confirmed to show the same unchanged observation. Start from
`docs/templates/repeat-capture-pairs.csv`. Paths must be relative to the
controlled data root. The evaluator refuses unapproved rows, non-test rows,
unconfirmed pairs, unsafe paths, missing release models, and existing output
files.

```powershell
uv run --frozen --all-packages stoma3d-evaluate-repeat-capture `
  --pair-manifest C:\controlled\repeat-capture-pairs.csv `
  --data-root C:\controlled `
  --release-manifest services\inference\release\release-manifest.json `
  --output C:\controlled\evidence\repeat-capture.json `
  --acknowledge-audited-data
```

The output contains aggregate counts and errors only. It excludes participant
IDs, pair IDs, image paths, masks, and predictions. A passing number does not
activate comparison by itself. The release manifest must pin the exact evidence
hash and point to a completed `docs/templates/repeat-capture-review.json` file.
The review must name the reviewer and their role, pin the same artifact hash,
use a UTC review time, and approve the fixed review scope. The service
independently parses both files and checks that their error and hashes match the
manifest before enabling normalized change.

This result is not a diagnosis. Repeatability evidence does not establish
clinical accuracy or physical measurement validity.
