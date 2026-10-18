# Read-only review of the final packaging utility

Date: 2026-10-18. Reviewed source: `execution/package_final.py`, SHA-256 `ab92225cc264d6a4beafd7e8ae54ee05fe7e1edd4a0f25fbebef44f0585cfb0c`.

This is a source review of the packaging guards, not a successful final packaging run. At review time the final numerical campaign and final scalar-admission inventory were incomplete. No frozen proof, harness, integration patch, historical receipt, or package utility was changed by this review.

## Guards already present

The original archive digest is pinned to the submitted third-pass source. Every inherited regular file in the full deliverable comes directly from that archive, except the four explicitly admitted proof/test preimages. Each replacement must match both the integration baseline hash and the frozen candidate postimage. The integration application result and patch hashes are checked, as are all sixteen current source/test postimages and the final imported proof-module map.

The inventory allows exactly the twelve declared new source/test files outside the new evidence directory. Other non-cache additions or changes to inherited regular files fail the build. Each new payload is rehashed as it is packaged. The completed full archive is reopened, every regular payload is hashed again, and the entire file/hash map and original link map are compared. The compact archive similarly contains an explicit SHA-256 map and is independently reopened and checked. Archive member duplication and unsafe original root/path components are rejected.

The selected-campaign preflight checks complete configured job populations, pinned aggregation inputs, resource/proof identities, and admission of current PASS receipts by exact SHA. A missing final continuation, coverage summary, or normative readjudication prevents successful packaging. The utility writes outside the repository into a new directory, so it does not overwrite the source or prior evidence.

These checks are adequate to detect an incorrect integration patch or an altered payload in either completed archive. The current working tree contained **zero symlinks** at the time of this review; no actual missing symlink payload was found.

## Recommended final guard: reject changes after inventory capture

The full `working` dictionary is captured before packaging. Source/evidence files are checked when read, and new evidence visible during the later compact scan will normally cause a failure if absent from that dictionary. There is no final recapture of the complete path/hash inventory before success is reported.

Consequently, a new non-evidence file added after the original inventory, or an evidence file added after the compact enumeration, can be absent from both archives without a final mismatch. A file changed after its final read can also leave a successful report describing an earlier snapshot while the supposedly frozen worktree has changed. This is a guard gap found by code inspection, not an observed mutation during this campaign.

The smallest correction is to recompute the same non-cache working path/hash inventory after both archive verification passes and require exact equality with the initial inventory. Fail on any newly added, removed, or modified entry. Keep the two independently verified archives bound to that single frozen inventory. A source-identity record of the packaging utility and the final inventory digest would also make the delivery validation easier to replay.

The inventory presently skips working symlinks silently. Since this working tree contains none, an explicit rejection of unreviewed working symlinks is economical and cannot drop a current payload. Alternatively, compare all symlink identities against the inherited archive and explicitly allow only those unchanged inherited links. This closes the related possibility of silently omitting a newly introduced evidence link.

## Recommended final guard: bind the delivered report to the final inputs

The utility currently checks only `coverage_final_01/SUMMARY.json`'s completion status before running a separate current-input readiness check. That readiness check does not validate the bytes or provenance of the already generated coverage report. Thus a stale completed summary from another input snapshot is not rejected solely by that status check.

Before packaging, verify `coverage_final_01/SHA256SUMS` and `census_final_01/SHA256SUMS`. Also compare the coverage summary's recorded report-code hash, census-summary hash, strict-readjudication hash, per-label plan paths/hashes, and expected/observed populations with the actual final files and configuration. Its source/design binding and recognized proof snapshots should agree with those admitted by the preflight. An exact immutable replay of `aggregate_final.py` into the existing census/report directories is another valid check, although it does more work.

The utility should also require the independent complete-cell verification records for every complete cell claimed in the final report, validate their manifests and statuses, and confirm that their cell IDs, canonical counts, and selected raw-receipt hashes agree with the delivered evidence. This is an omission guard for the requested independent verification artifacts; it does not replace the global canonical coverage proof or rerun numerical arithmetic.

## Integrity rerun completed during this review

The separate final inherited audit succeeded under `authority/final_integrity_2026-10-18/`: all **16,711** previously pinned files and all **33,487** inherited files in the broader scope remain byte-identical to the supplied archive. Its `INTEGRITY.json` and `INHERITED_FILES.sha256` are themselves byte-identical to the initial audit results. This audit ran in 9.782 seconds on CPU 8 at nice 15, with peak RSS 68,532 KiB. It is compatible with new evidence being added because its selected inherited population is fixed.

No production-code, coefficient, normative-band, or release-policy change was observed. P15 remains BLOCKED. Final package success still requires the remaining campaign, final strict scalar readjudication, completed coverage report, and independent cell verification records.
