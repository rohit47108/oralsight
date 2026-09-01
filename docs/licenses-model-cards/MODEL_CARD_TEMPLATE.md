# Model card: `<model name>`

> **This result is not a diagnosis.** Gate passage is a competition release criterion
> and does not establish clinical validity or regulatory clearance.

## Identity and release state

- Version:
- Task: `segmentation | anatomy | appearance | disease | reidentification`
- Release status: `DISABLED / ABSTAIN` by default
- Artifact SHA-256:
- Training code commit:
- Evaluation ID and date:
- Threshold version: `2026.1`
- Owner:

## Intended and out-of-scope uses

List the narrow research-prototype use. Explicitly forbid diagnosis, reassurance,
treatment, autonomous lesion matching, and care guidance from disease categories.

## Data provenance

List versioned training and held-out datasets, roles, licenses, consent scopes,
patient-disjoint split method, inclusion/exclusion criteria, and audit evidence. Do not
include patient IDs or local paths in this card.

## Evaluation

Include the complete relevant release gate, confidence intervals, calibration,
per-class results, subgroup report, failure/abstention rates, and device conditions.
Do not selectively omit a failed class or low-support subgroup.

## Limitations and monitoring

Document sampling, label, device, lighting, geography, demographic, cross-sectional,
calibration, out-of-distribution, and longitudinal limitations. State the revocation
trigger for any regression or provenance problem.

Generate the locked card with:

```powershell
python -m stoma3d_ml.model_card `
  --metadata model-metadata.json `
  --evaluation aggregate-evaluation.json `
  --output model-card.md
```
