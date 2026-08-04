# Aggregate evaluation contract

`oralsight-evaluate-gates` accepts one JSON object containing `evaluation_id` and the five
sections below. Values at a threshold pass; any missing, non-finite, malformed, or lower
quality evidence disables only that head. Metrics must come from locked, audited,
patient-disjoint held-out evaluation—not training or synthetic fixtures.

| Section            | Required aggregate evidence                                                                                                                                                                 |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `segmentation`     | `patient_disjoint=true`, Dice ≥ 0.70, boundary F1 ≥ 0.60                                                                                                                                    |
| `anatomy`          | `patient_disjoint=true`, macro F1 ≥ 0.80, recall ≥ 0.70 for every canonical region                                                                                                          |
| `appearance`       | `patient_disjoint=true`, ≥ 50 held-out patients per class, macro F1 ≥ 0.75, recall ≥ 0.70 per class, ECE ≤ 0.08                                                                             |
| `disease`          | patient-disjoint independent held-out set, ≥ 100 patients per class, macro F1 ≥ 0.80, sensitivity and specificity ≥ 0.80 per class, ECE ≤ 0.05, complete provenance, signed clinical review |
| `reidentification` | patient-disjoint ≥ 50 patients, ≥ 200 matched and 200 hard-negative pairs, precision ≥ 0.95, Wilson lower 95% bound ≥ 0.90, mandatory user confirmation                                     |

For re-identification, supply `true_positive_matches` and `false_positive_matches`; the
evaluator calculates both precision values instead of trusting a reported confidence
bound. Appearance class keys are `red-patch`, `white-patch`, `ulcer-like`, `mixed`,
`pigmented`, `none-detected`, and `unsupported`. Disease research keys are `normal`,
`variation`, `opmd`, and `oral_cancer`.

```powershell
python -m oralsight_ml.gates aggregate-evaluation.json `
  --output release-gates.json `
  --require segmentation `
  --require anatomy
```

Without `--require`, the command emits the complete report and exits successfully even
when heads are disabled, which supports initial model-card generation. A repeated
`--require` converts selected disabled heads into a nonzero CI result. No aggregate gate
report should include images, image paths, or patient identifiers.
