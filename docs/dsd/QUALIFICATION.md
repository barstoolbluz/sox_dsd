# P15 first-release qualification and release hold

**Status: INCOMPLETE. Production default migration is BLOCKED.** This is a
release-gate record, not a claim that P10 mastering failed. The authoritative
machine-readable outcome is `tests/dsd/results/P15/release/release-manifest.json`.
Never reinterpret a tool's zero exit status as a passing release gate without
checking the instrument's result scope.

## Scope

The first release is DSD64/128/256 native reads and writes, PCM outputs at the
nine declared 44.1/48-kHz-family rates through 705.6 kHz, `mastering` and
`wideband` reconstruction, and qualified scalar guarded mastering modulation.
Scalar, SSE2, AVX1, AVX2 and baseline AVX-512F remain independently forceable
on compatible builds and CPUs. `-D` controls ordinary PCM dithering, not the
one-bit modulator. The non-DSD SoX graph and DSD-native bit chronology remain
compatibility constraints.

## Three distinct decisions

1. **P10 scalar mastering profile certificate: PASS, historical and specific.**
   The reviewer-certified P10 results are in
   `tests/dsd/results/P10_certification_2026-10-11/certification.json` and
   `docs/dsd/handoffs/P10_ADJUDICATION.md`. Their one-hour synthetic soaks,
   independent operator-supplied corpus receipts, decoder-reference rules and
   preparation host report are accepted *for the P10 candidate revision*.
   Historical failed/unrun receipts remain intact.
2. **Source lineage: reconciled with bounded scope.** The 35-input P10
   verifier is intentionally pinned to that revision. It fails on later source
   because `src/dsd_plan.c`, `src/pcmdsd.c`, `src/pcmdsd.h` and `src/sdm.c`
   changed; 31 inputs remain byte-identical to the positive certificate.
   `docs/dsd/handoffs/P11.md` explains its expected exit 1. The four source
   changes were introduced in later accepted phase handoffs; P11 scalar
   differential CLI results are bit-identical for six P10/P11 cases, and P11
   through P14 executed their own numeric and kernel regression suites.
   This P15 pass reruns the changed-version preflight and integration tests.
   The P15 ledger includes historical and current file digests. **It does not
   regenerate, rebase or edit the P10 certificate.** New P15 planner changes
   receive their own current-revision tests; the historical certificate is
   not expanded to cover those changes.
3. **Production release and dispatch promotion: BLOCKED.** A positive
   historical certificate plus passing present-host smoke tests is not the
   entire release qualification. Keep `src/pcmdsd.c` production `qualified`
   flags false and the CLI's legacy default until the mandatory open jobs
   pass and their evidence is reviewed. This is deliberate fail-closed
   behavior, not a missing code-switch fix.

## Evidence and host limits

The inherited P07 executable suite exercises the 3 native x 9 PCM x 2 profile
routing/count integration grid. P06 filter certificates, independent P07 SRC
reference comparisons and P09 frozen `analysis-v1` are separate mathematical
quality controls. The P15 regression repeats all 54 native/profile/PCM-output cells both as
`--dsd-plan` decisions and as *executed, rendered PCM* conversions. Each
rate-pinned versioned ID must produce byte-identical audio to its human
profile alias. This verifies execution and identity, but it does *not*
measure frequency response. A release-strength numerical grid must recheck
every rate/profile's scalar response and selected cross-ISA cells against the
frozen high-precision references, including stopband aliases and 48-kHz
fractional SRC. Synthetic native-bit format tests are not substituted for
valid audio spectral certification.

The physical AMD Threadripper 7970X AVX-512F record is in
`tests/dsd/results/P13_amd_physical_avx512_2026-10-12/`. It measures a faster
`fir-block` microkernel but neutral conversion decode and slower whole-graph
encode under forced AVX-512F. The follow-up establishes that the FIR is not a
material share of decode runtime on that workload. Therefore **no AMD AVX-512
preference** is justified. The static virtualization labels inside that
historical matrix are wrong for its physical AMD host; read its independent
`host-provenance.txt`. Keep old raw fields unmodified.

An Intel Xeon Platinum 8488C test recorded forced correctness/cross-vendor
agreement on a limited stimulus in inherited P13 evidence, but it was not an
independently repeatable physical Intel *performance matrix*. This host in
P15 is virtualized and is no substitute for physical Intel or an older AVX1
physical performance measurement. The operator reported Intel physical silicon
unavailable in one earlier assessment; that is an operational constraint,
not a technical demonstration that Intel AVX-512 can never be tested.

P11's QEMU feature-restricted Sandy Bridge compatibility receipt proves AVX1
instruction execution without AVX2; it does not establish physical throughput.
Prior one-hour scalar/ISA soak state receipts have their historical scope;
there is no full current P15 physical-hardware long-run matrix with fresh
sources present in this environment. The 2x six-channel DSD256 benchmark
reference-host target and bandwidth-matched control remain unverified in P15.
Virtualized timing is development data only, not dispatch-selection evidence.

## Exit semantics and required continuation

The P15 manifest generator returns zero when its *evidence inventory* was
written and lineage checks are consistent. Its `status` remains `BLOCKED` and
`default_promotion_authorized` is false until all mandatory gates pass.
Pass `--require-qualified` to require release readiness (exit 2 for an honest
blocked release, exit 1 for corrupt/unexpected certificate lineage).

Only reopen the named, actual gaps. Do not increase guard bounds, relax
analysis-v1 thresholds, install an untested FMA preference, silently attenuate
PCM, normalize DSD reference levels, or invent a hardware receipt. Upon
closure, separately authorize a source change to the default mode, mastering
`qualified` flags and verified selected CPU preferences, then rerun every
regression and hardware acceptance gate on the delivered source.

The CLI exposes explicit pinned IDs before promotion for source-compatible
reproducible selection. Encoding with a pinned ID is still refused by the
production path while the release gate is open; the P10 candidate harness is
not a user-facing mastering output path.

## 2026-10-13 P15 question follow-up (not a release promotion)

See `P15_QUESTIONS_ADJUDICATION_2026-10-13.md` for the explicit 30-integer / 24-fractional independent-reference split, the 54-cell/tier functional qualification versus selected detailed cross-ISA comparison, the proper separation from P09 `analysis-v1`, and the reason cross-host scalar SDM file-hash equality is not promised. The supplied `P15_avx1_physical_2026-10-13` folder is **not** admissible older-AVX evidence: its `host.txt` names an AVX2-enabled Threadripper rather than the AVX1-only machine claimed by its README, and the raw performance receipts are absent. The six existing release gates stay open. No automatic default, encoder qualification bit or ISA preference changes in this follow-up.
