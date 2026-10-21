# P15 SOURCE operator rebind — independent verification and resumption

**Date:** 2026-10-20  
**Original source snapshot:** `sox_dsd/main@adebf704`  
**Unmodified input tar SHA-256:** `a7ffd051e93c1774c73c28ada387388226e087b5e433f0f30ce67b8eb4c756b1`  
**Disposition:** **The current 24 captured SRC stage operators match byte-for-byte; their current source bindings are repaired.** This is a bounded-source-evidence result, not new mathematical certification or a declaration about all possible runtime samples.

## What changed and what did not

The uploaded archive was independently inspected and compared to the working tree. Exactly 32 preexisting files changed; none of the original source or production C DSP implementation files changed. There are 24 `operator-binding.json` replacements, one active `SUMMARY.json` revision, and seven updates to P15 Python checks/adjudicators. The active `stage-snapshot.json` bytes, earlier frozen stage directory, P00 SHA-256 inventory, 11,516 historical certificate reports, and 35-file source pin selection remain untouched. Source hashes drifted in exactly `src/dsd.c`, `src/dsd_public.c`, and `test/Makefile.am`, but these three files were *already changed in the supplied snapshot*; this corrective package does not edit them.

The new test-only exporter was built from the supplied actual C sources, with GCC 14.2.0, the ordered-SRC build flags and `-ffp-contract=off`. Its binary/wrapper identity is recorded in `BUILD_PROVENANCE.json`. All 24 captured stage snapshots compared **byte-for-byte** to the active previous snapshots, including coefficients and clock/phase metadata; source/operator receipt changes were restricted to `source_sha256` and the exporter hash. The 72-cell worklist enumerated **214,432** source alias families. The updated matrix `SUMMARY.json` differs only in its source hashes. These observations establish invariance of the *captured private SRC stage realization*, not the non-SRC DSD decode profile default or the complete runtime path.

## The deliberate pinning policy

**Keep the broad 35-file pin set.** It is an identity envelope around executable DSP sources, the capture/alias code, build integration and the historical worklist. A changed but observationally neutral input should cause a deliberate refusal, followed by audited recapture. This is a useful fail-closed tradeoff; removing the three changed files merely to get green tests would allow unreviewed drift. Broad pin coverage is not a proof every file is numerically reachable by the private SRC stage.

**Mechanical regeneration may be done locally** without re-asking the original reviewer *only* after: (1) the exact OLD:NEW source file digests are independently reviewed and explicitly authorized; (2) the same 35 pins are retained; (3) a fresh C exporter is compiled against the exact current source; (4) all 24 snapshots compare byte-identically; (5) every changed receipt differs only by `source_sha256`/`exporter_sha256`, the summary only by `source_sha256`; and (6) a new immutable, versioned audit directory preserves predecessors. `scripts/rebind_p15_src_operator.py` enforces those mechanical prerequisites; it does **not** prove a source edit cannot change runtime route selection, default profile, or full-chain numeric output. Changes affecting those require separate human/engineering review. Never mechanically replace full-chain certificates or reinterpret historical release approval.

## Historical provenance is kept honest

The historical P00 index was not edited. Its 32 previously indexed changed-file preimages and exact original SHA-256 digests are retained under `preimages/`; the dated `ADMISSION.json` authorizes *only* those 32 exact old/current pairs. The closeout validator verifies that every admitted file has the historical SHA-256 preimage, that each current file matches the independently recorded revision, and that all 24 stage hashes match their original bytes. No unrestricted "skip mismatches" exception was introduced.

The historical 11,516 receipts still carry their original source identity. `p15_historical_campaign_binding.py` validates that identity against the audited old bindings and the unchanged stage snapshot, rather than claiming historical receipts were freshly issued under the new source hashes. The independent receipt-only adjudicator inspected 2,850 passband and 8,666 stopband reports. This checks report consistency with claimed limits; it is **not** a new independent arbitrary-input FFT4G proof, spectral continuum calculation or raw metrology replay. 1,351 `.npz` are intentionally absent per the supplied transport. Legacy `p15_current_closeout` itself reports `BLOCKED` and does not authorize a P16 transition; this operator rebinding does not change that gate decision. Any external P16 authorization is a separate authority.

## Verification and tests

- Recapture: **24/24 byte-identical** stage snapshots, **72/72** active cells, **214,432** enumerated alias families.
- Original archive diff: **51,066** original regular files accounted for; **32** controlled amendments; **zero** missing/retagged original files.
- The **38** `test_p15_*.py` files: **298 passed, 272 passing subtests, 14 skipped, 0 failed/error**; run logs in `logs/python_*.log`. All sixteen initially failing test files are included in this run.
- Source/adjudication regression subset: **23 passed**; `make check-rename`: **PASS**.
- Historical receipt consistency: **11,516/11,516** checked, without claiming independent mathematical proof.
- Build contract: qualified ordered-SRC C flags pass `p15_src_opt_build_contract`.
- `make check-dsd DSD_PHASE=P15` status: **PASS**. The out-of-tree harness assumes generated `src/soxconfig.h` and compiled `.o` files exist *under source tree*. Testing used temporary links to actual out-of-tree build products; these links are omitted from all source artifacts. See `logs/check_dsd_p15.log` for the complete last run.
- Rebinding script rerun with no drift is read-only and idempotent; `recover_p15_src_operator_rebind.py` provides independent preflight and resumable publication if a process terminates after audit archive creation. A second, deliberately different exporter-wrapper SHA-256 also successfully recaptured all 24 snapshots: its own identity is reported separately, while the published binding retains the exact original audited exporter identity.

## Reproduce on a suitable GNU/Linux host

The rebuilt `configure`, `Makefile.in`, generated libraries, object files and platform-specific exporter are **not** included. They must be generated using the actual source and local toolchain.

```bash
cd sox_dsd
autoreconf -fi
mkdir -p ../sox_dsd_build
cd ../sox_dsd_build
CFLAGS='-O2 -g -ffp-contract=off -DLSX_RATE_ORDERED_OPT=1 -DLSX_RATE_ORDERED_OPT_FP_CONTRACT_OFF=1' ../sox_dsd/configure --without-libltdl
make -j4 all
make -C test dsd_test_p15_src_stage_export
cd ../sox_dsd
python3 scripts/rebind_p15_src_operator.py --exporter ../sox_dsd_build/test/dsd_test_p15_src_stage_export
python3 scripts/recover_p15_src_operator_rebind.py --exporter ../sox_dsd_build/test/dsd_test_p15_src_stage_export
P15_SRC_STAGE_EXPORTER=../sox_dsd_build/test/dsd_test_p15_src_stage_export python3 -m unittest discover -s tests/dsd -p test_operator_rebind_recovery.py -v
python3 -m pytest -q tests/dsd/test_p15_*.py
```

A future reviewed source edit requires `--approve-drift PATH=OLD_SHA256:NEW_SHA256` once per changed pinned file, an **unused** `--audit-out`, and `--publish` only after independent recapture succeeds. Never reuse this dated audit directory for a new revision. The recovery tool can use `--publish` safely after validating an interrupted, already-audited publication; rerunning it on a completed tree is idempotent.

## Interruption recovery, provenance and residual constraints

The first rebinding command puts complete historical bindings and the original four audit files in a dated archive **before** it modifies active bindings. An interruption may temporarily leave a mixed set. `scripts/recover_p15_src_operator_rebind.py` verifies all archived old hashes, an independent fresh C recapture, every stage snapshot and both possible summary hashes; it refuses unknown or modified bytes. A rebuilt exporter with a different wrapper hash is allowed only when it reproduces the captured operator and, after normalizing that one non-numerical wrapper-hash field to the *original audited value*, the result matches the original new-binding SHA-256 exactly. The published receipt retains its audited exporter hash, not the verifier's differing hash. Run it without `--publish` to inspect, then with `--publish` to install only verified missing receipts. All updates write temporary files, fsync and atomically replace individually; there is no promise of transactional atomicity across the 25 files, hence the recovery command.

A miniature baseline-tree test also checked the patch installer against all 32 original preimages and 60 source/P00/stage anchors, completed 116 file additions/replacements, reran idempotently, and refused a tampered `src/rate.c`. For resumption across separate sessions, retain this entire dated audit folder together with the source snapshot and the full or patch bundle. `HANDOFF_STATE.json` records the approved digests, tests, and next commands. The downloadable patch ships its own preflighted, idempotent apply operation, while the full bundle is a complete source snapshot. Do not conflate the SHA of the original uploaded archive with the SHA of the corrected handoff.

**Boundary:** There was no modification to any production audio DSP C implementation, no claim of newly proven spectral extremum/FFT4G arithmetic, and no unilateral amendment of historical mathematical certificates or P16 release authority.
