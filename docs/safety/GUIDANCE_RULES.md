# Guidance-rule activation procedure

The included example is intentionally disabled. The application must treat a missing,
malformed, unsigned, hash-mismatched, expired, or `enabled: false` file identically:

- calculate no urgency or review-priority level;
- display only the neutral message and “This result is not a diagnosis”; and
- record the configuration version as unavailable/disabled in the local report.

The rule engine may use only symptoms, duration, progression, image quality, and analysis
uncertainty. It must never branch on an appearance class, disease-category output, model
confidence alone, demographic proxy, tobacco/alcohol history alone, or an LLM response.

Before activation:

1. A qualified clinician authors or reviews every condition, outcome, and user-facing
   string, including the neutral fallback and demonstration cases.
2. Validate the file against `guidance-rules.schema.json`.
3. Canonicalize and SHA-256 hash the rule version, neutral message, keyed messages,
   and exact `rules` array; record that digest in approval.
4. Capture reviewer name, credentials, time, and the fixed review scope in a controlled
   release record.
5. Test rule boundaries, missing inputs, contradictory inputs, low-quality images, high
   uncertainty, and disabled/malformed configuration.
6. Set an approval expiry date and enable only the reviewed file. Any reviewed-text,
   version, or rule edit invalidates the digest and disables guidance until a new review
   is signed.

This workflow is a safety control, not proof that the resulting guidance is medically or
legally appropriate.
