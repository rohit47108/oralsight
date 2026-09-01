# Stoma3D 2026 delivery roadmap

Internal submission target: **October 23, 2026 at noon ET**. October 24-26 is an
emergency buffer, not planned feature time. Reconfirm the controlling portal deadline
and NJ-06 eligibility before relying on either published date.

> **This result is not a diagnosis.** Passing an engineering or competition gate does
> not establish clinical validity.

## Schedule and exit gates

| Dates        | Deliverable                                                                                                                                                                                 | Exit gate                                                                                                                                      |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| Jul 22-26    | Eligibility/portal confirmation, asset audit, intended use, claims, region enum, contracts                                                                                                  | Written deadline clarification; every reused asset has checksum, license, provenance, labels, patient-ID handling, and platform status         |
| Jul 27-Aug 9 | Cross-platform walking skeleton                                                                                                                                                             | Region/capture identifiers survive consent through the local report; deletion rotates keys and removes rows/blobs                              |
| Aug 10-23    | Eight-region capture, stability/quality/privacy preprocessing, anatomy validation track, manifests, baseline training, final map asset                                                      | One accepted capture per region; rejected local-quality images are discarded; reproducible audited-data dry run                                |
| Aug 24-Sep 6 | Segmentation, descriptors, uncertainty/abstention, anatomy, appearance, disease-research heads                                                                                              | Only heads with complete evidence pass their frozen release gate; all others abstain and remain disabled in the runtime model card             |
| Sep 7-20     | Re-identification experiment, mandatory confirmation, registration, comparison, timeline, lesion pins                                                                                       | Comparison remains suppressed unless confirmation and every geometric/repeated-capture gate pass                                               |
| Sep 21-Oct 4 | Local observation PDF for clinician discussion, explanation tree, confidence constellation, intake, accessibility, guidance-rule review, offline/error behavior, deletion/security evidence | Feature freeze; signed clinician wording/rules or neutral guidance only; accessibility and deletion evidence captured                          |
| Oct 5-11     | Locked ML evaluation, physical-device testing, safety/privacy review, model cards, disclosures, source docs, judge Q&A                                                                      | Patient-disjoint evidence and model hashes frozen; two iPhones/two Android devices complete the test matrix                                    |
| Oct 12-18    | Public demonstration recording                                                                                                                                                              | Final cut is 2:45-2:55 with captions, names, audience/problem, complete flow, stack, limitations, privacy, and disclosures                     |
| Oct 19-23    | Release freeze and submission                                                                                                                                                               | Commit, builds, manifests, model artifacts, sample report, video, answers, and checksum list match; second student verifies the portal receipt |

## Ownership

This is the intended assignment template, not evidence that four students have accepted,
completed, or reviewed the work. Replace the labels with the real eligible participants
and retain review/commit evidence before submission.

| Owner     | Primary responsibility                                                   | Required cross-review                                   |
| --------- | ------------------------------------------------------------------------ | ------------------------------------------------------- |
| Student 1 | Mobile navigation, camera, accessibility, result/report UI               | Reviews API failure and deletion flows                  |
| Student 2 | Data licenses, manifests, training, calibration, evaluation, model cards | Reviews mobile provenance and model-card presentation   |
| Student 3 | Procedural 3D interaction, overlays, registration, re-identification     | Reviews capture completeness and comparison suppression |
| Student 4 | FastAPI, contracts, encryption, integration tests, deployment/release    | Reviews ML gates and competition evidence               |

Every student must be able to explain the full architecture and demonstrate the safety
boundaries. Student 4 performs the final upload; another student independently verifies
all portal fields, links, participant names, video access/runtime, disclosures, and the
submission timestamp.

## Current handoff boundary

The greenfield working tree implements a real camera/photo-library capture flow,
fail-closed API/ML contracts, procedural observation map, local protected-storage/report
code paths, comparison gating, documentation, and CI configuration. The installed app
does not bundle a demonstration image or fixture result. The released anatomy and
candidate-segmentation heads are hash-pinned and enabled; appearance,
disease-category, automated re-identification, review priority, and numeric change
remain closed because their required evidence is absent or below the release gate. The
remaining calendar items require clinician approval, physical-device testing,
production signing/HTTPS and ephemeral-storage configuration, source-license selection,
and competition administration. See
`IMPLEMENTATION_STATUS.md` for the exact blockers and `NJ06_RULES_CHECKLIST.md` for the
submission checklist.
