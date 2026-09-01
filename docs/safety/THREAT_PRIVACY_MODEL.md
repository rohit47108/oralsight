# Stoma3D threat and privacy model

Status: design and verification checklist for a competition research prototype. It is
not a certification, legal opinion, HIPAA claim, or guarantee of security.

## Assets and trust boundaries

Sensitive assets are oral photographs, symptom responses, approximate observation
locations, reports, encryption keys, model outputs, and pseudonymous local identifiers.
Model weights, manifests, aggregate metrics, and rule/model versions are integrity
sensitive even when they contain no direct identifiers.

Trust boundaries:

1. Camera/OS into the mobile process.
2. Mobile memory into encrypted local database and files.
3. Sanitized request across TLS to the stateless inference service.
4. Request parser into bounded multipart handling, temporary spooling where FastAPI uses
   it, in-memory image decoding, and model execution.
5. Signed/versioned response back into schema validation and encrypted local storage.
6. Optional OIDC sign-in into the stateful platform API and consented sync to private
   object storage, PostgreSQL metadata, and a durable Redis-backed job queue.
7. Worker processing into reports, videos, projected-color GLBs, encrypted exports, and
   retention/deletion records.
8. Expiring fragment-secret sharing and explicit clinician grants into the web portal.
9. User-initiated local export into the operating-system share surface.

The inference service has no account database, object store, analytics pipeline,
retained job queue, or model-improvement ingestion path. The separate optional platform
does retain consented account records and artifacts under the published schedule. Cloud
records are never silently enrolled into model training.

## Threats and required controls

| Threat                                            | Required control                                                                                                                                                                                                                                                                                                 | Verification evidence                                                                                                                                 |
| ------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| GPS/identity metadata leaves device               | Re-encode image; strip EXIF/GPS; require a mouth-only user confirmation before upload; run a conservative face check on the sanitized transient service copy                                                                                                                                                     | EXIF removal is automated; physical-device privacy framing and service rejection still require verification                                           |
| Rejected capture is retained                      | Run quality/privacy checks before persistence or upload                                                                                                                                                                                                                                                          | File/database diff remains empty after each rejection class                                                                                           |
| Local theft or backup exposes data                | SQLCipher-backed database, per-install key in secure key store, encrypted image/report files, platform backup exclusions                                                                                                                                                                                         | At-rest inspection cannot recover plaintext; reinstall/key-rotation test                                                                              |
| Network observer reads image                      | HTTPS/TLS only outside loopback development; no certificate bypass in release                                                                                                                                                                                                                                    | Proxy/certificate test and release-config review                                                                                                      |
| Backend or proxy logs request bodies              | Disable body/multipart/access detail logging; use request IDs only; `Cache-Control: no-store`                                                                                                                                                                                                                    | Log-capture test contains no bytes, filenames, symptoms, or identifiers                                                                               |
| Request processing leaks image data               | Bound multipart bytes; close upload streams in `finally`; retain no application-managed copy; place parser spooling on encrypted ephemeral storage or `tmpfs` in production                                                                                                                                      | Force parser spooling and decode/model failures; verify closure, ephemeral cleanup, and no body logs                                                  |
| Oversized or malformed image exhausts service     | Enforce content type, byte/pixel/dimension and decompression-bomb limits plus bounded off-loop concurrency; require an upstream ingress timeout because OpenCV decode is not safely cancellable in-process                                                                                                       | Malformed, huge, bomb, and concurrent request tests plus deployment ingress-timeout evidence                                                          |
| Fixture output is shown for live input            | Require bundled input origin, canonical fixture region, caller-declared fixture hash, and SHA-256 of the exact uploaded bytes to all match the allowlist                                                                                                                                                         | Mutate uploaded bytes/origin/region/declared hash and verify `analysis unavailable`, never fixture output                                             |
| Forged or stale model result                      | Mobile and worker verify the detached Ed25519 signature over the exact response body and request ID before JSON parsing/storage; also validate no-store, schema, capture/region IDs, provenance, and model hashes                                                                                                | Tampered body, wrong key/key ID/request ID/region, encoded response, malformed JSON, and replay-oriented tests                                        |
| Patient leakage inflates evaluation               | Source-scoped patient-disjoint manifest validation before training/evaluation                                                                                                                                                                                                                                    | Synthetic duplicate patient across splits causes hard failure                                                                                         |
| Unauthorized dataset/model use                    | Complete inventory and approved purpose/consent fields; controlled DVC remote only                                                                                                                                                                                                                               | Audit record and manifest gate; no medical-data paths in Git/CI                                                                                       |
| Low-support subgroup is exposed                   | Aggregate metrics only; suppress groups below minimum patient count                                                                                                                                                                                                                                              | Report contains counts/reason but no metrics or patient IDs                                                                                           |
| Malicious model or rule artifact                  | Pin checksum/version; load only approved local artifact; rule digest must match clinician approval                                                                                                                                                                                                               | Checksum mismatch disables head/guidance                                                                                                              |
| Bad or partly hidden calibration card skews color | Require the exact marker, confirmed same plane, marker pose/proximity gates, all four projected patch interiors, minimum pixels, uniformity, monotonic range, no clipping, and a bounded affine fit; apply only to two copied descriptor inputs                                                                  | Out-of-frame, small, nonuniform, reordered, clipped, low-range, non-neutral, and unsafe-transform tests; size gate remains independent                |
| User believes output is a diagnosis               | Persistent disclaimer, descriptive wording, uncertainty/limitations, gated experimental panel                                                                                                                                                                                                                    | Screen-reader and exported-report content tests                                                                                                       |
| Delete-all leaves recoverable records             | Delete rows/blobs/reports, clear pending shares/exports, rotate install key, vacuum where appropriate                                                                                                                                                                                                            | Before/after inventory plus failed decryption with prior key                                                                                          |
| Shared report escapes app controls                | Explicit selection, fragment secret, short-lived HTTP-only exchange cookie, expiry, revocation, access history, `no-store`, and `noindex`; warn that a recipient can still save a copy                                                                                                                           | Exchange/content/revoke tests, browser cookie-path test, and deployed header inspection                                                               |
| Forged or replayed cloud action                   | OIDC access-token validation, exact configured role claim, database plus token-role checks, durably sealed first-admin bootstrap, trusted-operator additional/recovery commands, two-step clinician activation, bounded privileged-token age, consent gates, stable idempotency keys, and immutable audit events | Wrong issuer/audience/key/claim/role tests, concurrent bootstrap and administrator-recovery tests, activation and role-removal tests, and retry tests |
| Abandoned upload retains private bytes            | Exact size and SHA-256 checksum binding, pending-upload expiry, lifecycle sweep, and private bucket policy                                                                                                                                                                                                       | Wrong checksum/size, expired finalize, and sweep tests; production lifecycle evidence                                                                 |
| Cloud delete is incomplete                        | Immediately block normal account work, revoke consent/shares/grants, cancel work, delete live rows/objects, create a short-lived keyed server receipt, and keep only a minimal protected mobile polling receipt until completion; never run normal bootstrap while either receipt is pending                     | Idempotent delete, restart-safe same-subject receipt polling, isolation, object inventory, and restore drill                                          |

## Data lifecycle

```text
camera preview
  -> re-encode/strip metadata and run available quality preflight
  -> rejected quality or missing manual mouth-only confirmation: discard
  -> tentatively encrypt accepted local capture
  -> send transient sanitized copy to stateless API
  -> bound multipart size/pixels/concurrency; parser may spool to its temp backing store
  -> process decoded pixels in memory
  -> close upload stream in finally; retain no application-managed temp copy
  -> return no-store, versioned, signed response
  -> verify signature/key/request ID, schema, provenance, and capture identity
  -> backend quality/anatomy rejection: delete tentative blob
  -> accepted quality with unavailable learned analysis: preserve the encrypted
     observation for an explicit retry
  -> accepted result: persist encrypted metadata/blob locally
  -> optional account consent and authenticated sync to private platform storage
  -> durable job creates selected report/video/GLB/export; every artifact remains scoped
  -> optional expiring share or explicit clinician grant with audit history
  -> local or cloud delete-all; revoke access, remove live objects, rotate install key
```

No capture is reused for training. Any future model-improvement program requires a new,
separate, informed consent flow, data governance, and threat review.

## Abuse and failure behavior

- Offline, timeout, 5xx, malformed, or unsigned non-loopback live analysis
  returns "analysis unavailable." Explicit loopback development may be unsigned.
  The installed app contains no fixture image or local fixture fallback and
  rejects fixture-derived response origins.
- The backend's exact-hash synthetic fixture is disabled by default and exists
  only for isolated service and contract testing.
- Unsupported anatomy, face presence, poor quality, high uncertainty, and
  missing model gates cause rejection or abstention; they do not fall back to a
  diagnosis.
- Missing clinician rules produces neutral information without an urgency label.
- Neutral-patch failure keeps the uncorrected sanitized-image mean redness and
  brightness, records the reason in limitations, and does not invalidate an
  independently passing marker-size estimate. A passing transform changes no
  stored pixels, masks, learned-head inputs, or care guidance.
- Registration below its confidence thresholds suppresses normalized change. A
  passing display transform may align the reveal/mask view, but it does not make
  a pair quantitatively comparable. The current release also suppresses every
  normalized and calibrated change until hash-bound, reviewer-approved
  repeat-capture evidence demonstrates no more than 10% area error.
- The service enforces byte/pixel/concurrency bounds without storing user
  identity; production ingress must still add and verify connection, timeout,
  and rate limits.
- A missing or invalid OIDC token fails closed. The mobile client treats access tokens as
  opaque and saves one only after the platform's signed-token boundary accepts `/v2/me`.
- No public endpoint creates an administrator. The offline first-admin bootstrap
  requires an exact existing active identity, a confirmation phrase, a
  zero-administrator database, a transaction lock, and a durable seal that does
  not reopen after row removal. Adding another administrator is a trusted
  infrastructure action that checks a distinct active administrator reference;
  the reference is not proof of that person's approval. Separate zero-admin
  recovery requires a sealed installation and the absence of every saved admin.
  None of the operator commands logs identity-provider subjects in audit details
  or output.
- The token validator reads only the configured access-token role claim. A generic
  `roles` claim cannot grant privileged access. Clinician approval remains pending
  until a validated token carries `clinician`; every later protected request
  rechecks that role even after a historical observation timestamp exists.
- Privileged roles expire from authorization when the access token exceeds the
  configured maximum age plus clock leeway. Provider-role removal takes effect on
  refresh and no later than that bound; this is not instant revocation.
- Sharing, clinician review, analytics, and artifact generation require separate consent
  and authorization; local capture continues to work when the platform is unavailable.

## Release-blocking privacy tests

- EXIF/GPS removal and pixel re-encoding.
- Database/file/report encryption and key storage/rotation.
- Rejected-capture non-persistence.
- Request/proxy/application log inspection.
- Upload-stream closure and cleanup of FastAPI/python-multipart spooled files on success,
  parser/decode error, and model error. In production, prove that the process temp path is
  encrypted ephemeral storage or `tmpfs`. Separately verify upstream ingress timeouts and
  bounded worker recovery; do not claim a safely cancellable in-process OpenCV decode
  timeout.
- Exact-hash fixture isolation and provenance labels.
- Full delete with filesystem/database inventory and prior-key decryption failure.
- Cloud authorization, idempotent retries, expiring upload cleanup, share revocation,
  deletion receipt isolation, and backup no-resurrection drills.
- First-admin tests for missing, inactive, mismatched, repeated, sealed, and
  concurrent targets against PostgreSQL; additional-admin tests for a distinct
  active reference; and recovery tests for the sealed zero-admin state.
- Worker inference-integrity tests for missing/no-store headers, encoded bodies,
  malformed request IDs, wrong key IDs, tampered signatures, and wrong echoed
  request IDs before JSON parsing.
- Exact-claim tests that reject a generic `roles` claim, privileged-token age tests,
  clinician application eligibility, two-step activation, repeat activation, and
  protected-route denial after provider-role removal.
- Git/CI scan for medical images, manifests, keys, databases, and model artifacts.

Unverified control status must remain "not verified"; it must not be converted
into a public compliance claim.
