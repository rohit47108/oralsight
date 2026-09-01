# Stoma3D ML research scaffold

This package validates patient-disjoint dataset manifests, computes calibration and
subgroup summaries, evaluates fixed release gates, generates model cards, and exposes
audited-data-only baseline training entry points.

It contains **no medical images, trained weights, or claims of clinical validity**.
All model heads remain disabled until an evaluation file independently satisfies its
complete gate. Passing a competition gate is not clinical validation.

## Local checks

```powershell
$env:PYTHONPATH = "ml/src"
python -m unittest discover -s ml/tests -t ml -p "test_*.py"
python -m stoma3d_ml.manifest ml/manifests/dataset.example.csv
python -m stoma3d_ml.gates ml/examples/evaluation.disabled.json
```

With `uv`:

```powershell
uv sync --project ml --extra dev
uv run --project ml pytest ml/tests
```

## Audited training entry point

The command validates licensing, consent scope, patient-level splits, task labels,
and on-disk paths before importing optional ML libraries or creating an output:

```powershell
uv run --project ml --extra research stoma3d-train-baseline `
  --task anatomy `
  --manifest C:\path\to\audited-manifest.csv `
  --data-root C:\path\to\controlled-dataset `
  --output-dir ml\artifacts\anatomy-run `
  --acknowledge-audited-data `
  --dry-run
```

Remove `--dry-run` only after the audit succeeds. Outputs contain aggregate metrics,
configuration, and weights; the trainer never copies source images into the run folder.

## Segmentation candidate selection

Experimental segmentation runs must use `--validation-only`. In that mode the trainer
does not open the locked test images and does not write release evidence:

```powershell
uv run --project ml --extra research stoma3d-train-release `
  --task segmentation `
  --manifest C:\controlled\smart-om-segmentation.csv `
  --data-root C:\controlled\smart-om `
  --output-dir C:\controlled\runs\segmentation-candidate `
  --image-size 384 `
  --batch-size 8 `
  --epochs 30 `
  --learning-rate 0.00012 `
  --segmentation-architecture presence_gated_unetplusplus_efficientnet_b3 `
  --segmentation-loss-version tolerant_boundary_v2 `
  --validation-only `
  --acknowledge-audited-data
```

After the architecture, epoch, and thresholds are frozen, evaluate the exact selected
checkpoint without retraining it:

```powershell
uv run --project ml --extra research stoma3d-train-release `
  --task segmentation `
  --manifest C:\controlled\smart-om-segmentation.csv `
  --data-root C:\controlled\smart-om `
  --output-dir C:\controlled\runs\segmentation-locked-evaluation `
  --image-size 384 `
  --batch-size 12 `
  --epochs 30 `
  --learning-rate 0.00036 `
  --segmentation-architecture presence_gated_unetplusplus_efficientnet_b3 `
  --segmentation-loss-version tolerant_boundary_presence_v3 `
  --evaluate-frozen-run C:\controlled\runs\segmentation-candidate\run.json `
  --acknowledge-audited-data
```

The evaluator verifies the source JSON, model, and ONNX hashes; loads only test rows;
copies the exact frozen artifacts; and writes aggregate release evidence. The older
`--refit-source-run` path remains available for explicit refit experiments, but a refit
is a different model and must not be presented as the selected validation checkpoint.
A failed locked gate remains disabled.

Two compatible validation-only checkpoints can also be interpolated into one model
with `stoma3d-segmentation-soup`. The command tests only declared interpolation
weights on validation data and exports one ordinary checkpoint for the exact frozen
evaluation above. It never loads test rows.

## Optional Autooral training supplement

The Autooral authors provide 420 pixel-masked oral-ulcer images for academic,
non-commercial research. Stoma3D does not redistribute those images. Download and
audit the archive from the
[authors' repository](https://github.com/wurenkai/HF-UNet-and-Autooral-dataset), then
generate a training-only supplemental manifest:

```powershell
uv run --project ml --extra research stoma3d-prepare-autooral `
  --dataset-root C:\controlled\Autooral_dataset `
  --output-manifest C:\controlled\autooral-training-supplement.csv `
  --archive-sha256 <audited-archive-sha256> `
  --acknowledge-academic-only-license `
  --acknowledge-audited-data
```

Pass that CSV with `--supplemental-segmentation-manifest` and its controlled root with
`--supplemental-segmentation-data-root`. Supplemental rows are accepted only for the
training split, require patient IDs and approved provenance fields, and never replace
SMART-OM validation or locked-test evidence.

## Re-identification release evaluation

Re-identification uses a separate locked workflow. It can deterministically build
same-lesion and region-matched hard-negative pairs from the audited sample manifest,
or accept an explicit pair CSV with these columns:

```text
pair_id,split,first_sample_id,second_sample_id,expected_match,pair_kind
```

Run a data-only check before training:

```powershell
uv run --project ml --extra research stoma3d-train-reidentification-release `
  --manifest C:\controlled\longitudinal-manifest.csv `
  --data-root C:\controlled\longitudinal-images `
  --output-dir C:\controlled\runs\reidentification-release `
  --acknowledge-audited-data `
  --dry-run
```

The release run chooses its similarity threshold on validation pairs, then opens the
locked test images once. Evidence records precision, recall, the Wilson 95% lower
bound, pair and patient counts, and the exact artifact hashes. The service release
manifest is never changed automatically. Even passing evidence permits candidate
suggestions only; every proposed link still requires user confirmation.
