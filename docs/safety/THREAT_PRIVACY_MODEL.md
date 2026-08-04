# OralSight threat and privacy model

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
6. User-initiated PDF export into the operating-system share surface.

The service has no account database, object store, analytics pipeline, retained job
queue, or model-improvement ingestion path. A future clinician portal, QR link, or cloud
sync crosses new trust boundaries and is out of scope.

## Threats and required controls

| Threat                                        | Required control                                                                                                                                                                                           | Verification evidence                                                                                       |
| --------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| GPS/identity metadata leaves device           | Re-encode image; strip EXIF/GPS; require a mouth-only user confirmation before upload; run a conservative face check on the sanitized transient service copy                                               | EXIF removal is automated; physical-device privacy framing and service rejection still require verification |
| Rejected capture is retained                  | Run quality/privacy checks before persistence or upload                                                                                                                                                    | File/database diff remains empty after each rejection class                                                 |
| Local theft or backup exposes data            | SQLCipher-backed database, per-install key in secure key store, encrypted image/report files, platform backup exclusions                                                                                   | At-rest inspection cannot recover plaintext; reinstall/key-rotation test                                    |
| Network observer reads image                  | HTTPS/TLS only outside loopback development; no certificate bypass in release                                                                                                                              | Proxy/certificate test and release-config review                                                            |
| Backend or proxy logs request bodies          | Disable body/multipart/access detail logging; use request IDs only; `Cache-Control: no-store`                                                                                                              | Log-capture test contains no bytes, filenames, symptoms, or identifiers                                     |
| Request processing leaks image data           | Bound multipart bytes; close upload streams in `finally`; retain no application-managed copy; place parser spooling on encrypted ephemeral storage or `tmpfs` in production                                | Force parser spooling and decode/model failures; verify closure, ephemeral cleanup, and no body logs        |
| Oversized or malformed image exhausts service | Enforce content type, byte/pixel/dimension and decompression-bomb limits plus bounded off-loop concurrency; require an upstream ingress timeout because OpenCV decode is not safely cancellable in-process | Malformed, huge, bomb, and concurrent request tests plus deployment ingress-timeout evidence                |
| Fixture output is shown for live input        | Require bundled input origin, canonical fixture region, caller-declared fixture hash, and SHA-256 of the exact uploaded bytes to all match the allowlist                                                   | Mutate uploaded bytes/origin/region/declared hash and verify `analysis unavailable`, never fixture output   |
| Forged or stale model result                  | Verify detached signature, signed request-ID consistency, schema, capture/region IDs, provenance, and model hashes before storage                                                                          | Tampered, wrong-key, wrong-request-ID, wrong-region, malformed, and replay-oriented tests                   |
| Patient leakage inflates evaluation           | Source-scoped patient-disjoint manifest validation before training/evaluation                                                                                                                              | Synthetic duplicate patient across splits causes hard failure                                               |
| Unauthorized dataset/model use                | Complete inventory and approved purpose/consent fields; controlled DVC remote only                                                                                                                         | Audit record and manifest gate; no medical-data paths in Git/CI                                             |
| Low-support subgroup is exposed               | Aggregate metrics only; suppress groups below minimum patient count                                                                                                                                        | Report contains counts/reason but no metrics or patient IDs                                                 |
| Malicious model or rule artifact              | Pin checksum/version; load only approved local artifact; rule digest must match clinician approval                                                                                                         | Checksum mismatch disables head/guidance                                                                    |
| User believes output is a diagnosis           | Persistent disclaimer, descriptive wording, uncertainty/limitations, gated experimental panel                                                                                                              | Screen-reader and exported-report content tests                                                             |
| Delete-all leaves recoverable records         | Delete rows/blobs/reports, clear pending shares/exports, rotate install key, vacuum where appropriate                                                                                                      | Before/after inventory plus failed decryption with prior key                                                |
| Shared PDF escapes app controls               | Explicit confirmation, local-only generation, warning that recipient controls copies; no background upload                                                                                                 | Share-cancel/share-complete tests and network inspection                                                    |

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
  -> explicit local report export or delete-all/key rotation
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
- Registration below its confidence thresholds suppresses normalized change.
- The service enforces byte/pixel/concurrency bounds without storing user
  identity; production ingress must still add and verify connection, timeout,
  and rate limits.

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
- Git/CI scan for medical images, manifests, keys, databases, and model artifacts.

Unverified control status must remain "not verified"; it must not be converted
into a public compliance claim.
