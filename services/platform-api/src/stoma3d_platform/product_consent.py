"""The exact current product-consent document shown before cloud capture."""

from __future__ import annotations

import hashlib

DOCUMENT_ID = "stoma3d-product-consent"
DOCUMENT_VERSION = "2026-08-06"
TITLE = "Stoma3D research application consent"
BODY = """Stoma3D is a non-diagnostic research application. It can store selected mouth images, symptom context, image observations, and reports in your protected account when you choose cloud features. Automated outputs can be wrong and do not replace an examination by a dentist or medical professional.

Only quality-accepted, sanitized captures are uploaded. You choose whether to request analysis, create a report, share selected records, or ask for clinician review. A share can be revoked. Product analytics is separate and remains off unless you opt in.

You may withdraw this consent at any time. Withdrawal stops new cloud scans and report jobs, cancels unfinished analysis work, and revokes active sharing and clinician grants. It does not erase records already stored; use Delete all data for deletion and installation-key rotation. If encrypted disaster-recovery backups are enabled, backup copies age out under the published backup-retention schedule and are not restored after a deletion request.

By continuing, you confirm that you understand this research use, its limitations, and the data choices above. This result is not a diagnosis."""
DOCUMENT_SHA256 = hashlib.sha256(BODY.encode("utf-8")).hexdigest()
