# Phase 06B active engineering checkpoint — 2026-11-16

**IMPLEMENTED, ACCEPTANCE MATRIX RUNNING.** Base `7be823a860dea05955c495586e115776d93f6166`, tree `e45aef22f314e56b1a0278b55939293002eb1662`. Original source SHA-256 `67beddc61f82b36370bf16038c8d4610d63e4ac2f0fe54d8042692bd6ae96f3b`, independent harness `7d64bc18a7839786636c4a45365dd6d3e7ca42f0392b9c56f491bb2897954414`. Owner override applies certified unity/0.5 DSD64/128 admission. Source restored from verified 06A bundle; reference original evidence is preserved outside this source tree.

Work units: (1) baseline+role parity reproduction; (2) minimal role fix; (3) private decoder–bounded FIFO–encoder composition; (4) planner/CLI route; (5) count/word/layout/failure tests; (6) matrix regression; (7) final full archive. None yet qualified. Never infer PASS from an incomplete command. Resume from `git log` and `evidence/phase06b/`, re-run incomplete gates. Default auto stays legacy; Phase 07 AUTO is not in this phase.

**Active Phase 06B gate checkpoint (continued).** The corrected `transcode` suite
has completed 10 independent count/bit-oracle cases, 23 FIFO schedules, 18
physical DSF/DFF comparisons and 9 packed adapter comparisons (PASS; see
`evidence/phase06b/transcode-gate.log` outside the source tree). The first
probe failure was a test-only incorrect negative DSD carrier (`SOX_SAMPLE_MIN`
in place of `-SOX_SAMPLE_MAX`); the second was a Python test-path precedence
error. Both are corrected. Reproduction `p06b_carried.sh` confirms four
Phase 06A role and refusal results now match the legacy CLI. This is **not yet
release acceptance**: build-matrix regressions, failure/lifecycle checks,
artifact verification, and full source packaging remain pending. If
interrupted, resume from current Git HEAD plus uncommitted changes (if any)
and the newest logs under `/mnt/data/phase06b_work/evidence/phase06b/`.

**Acceptance checkpoint 2026-11-16 (late evening, America/New_York).**
Phase 06B composition, the four owner-reported Phase 06A role/refusal
corrections and inherited encoder route test update are implemented.
`tests/pcm64/transcode.py` now checks 10 source-bound two-clock cases,
24 FIFO schedules, 18 physical DSF/DFF bit comparisons, 9 packed/expanded
input comparisons, an independent binary64 decoder plus certified encoder
replay, gain and permutation order, four physically injected output failures,
truncation, source alias/sentinel protection, the owner's 8 role/refusal
commands and a C coordinator lifecycle/sticky-failure selftest (17 assertions).
The native-static acceptance suite passes. The remaining build variants and
other regression gates are still being run; **never promote partial matrix
status to a release verdict**. Receipts are in `evidence/phase06b/` and the
resumable driver `evidence/phase06b/repro/run-matrix.sh` in the full archive.

---

# Phase 06A: FLAC qualification update (2026-11-16)

**Current state:** The previously unrun FLAC qualification has now been
performed with genuine FLAC 1.5.0 and libogg 1.3.6 built offline from the
Nixpkgs-pinned upstream source tarballs. The production PCM64/DSD implementation
and the frozen certified DSD64/DSD128 kernel code are unchanged. The
corrections are restricted to test infrastructure: `tests/pcm64/encode.py`,
`tests/dsd/check_p11_isa.py`, `check_p12_isa.py`, `check_p13_isa.py`,
`tests/dsd/test_isa_object_layout.py`, and this checkpoint.

- `--enable-shared --disable-static --with-flac=dyn` configures and builds.
  The actual FLAC plugin can read/write ordinary FLAC, but must refuse native
  binary64 DSD ingress. The encoder suite now inspects the real FLAC handler
  linkage using `pcm64_flac_probe capabilities`, verifies planner refusal,
  and records the built-in-only gate as `NOT_RUN` rather than failing on a
  correctly refused plugin. `io-flac` separately verifies plugin behavior.
- `--enable-shared --disable-static --with-flac=yes` configures and builds.
  Built-in integer-FLAC source audio produces bit-identical DSD64 and DSD128
  packed outputs to equivalent WAV integer audio, in both DSF and DFF. Each
  comparison checks channel identities and source-derived bit/frame counts.
  The native FLAC ingress gate is `PASS`, with 4 physical container comparisons
  and 86,784 compared interleaved one-bit decisions.
- Both FLAC configurations pass `encode`, `io-flac`, `pcm-identity`, `routing`,
  `decode`, `report-carriers`, `return-acceptance`, and ordinary `make check`.
  Individual additional PCM64 component suites have been run in the dynamic
  build; see the new archive-root evidence for exact receipts and statuses.
- The shared libtool build places actual ISA audit objects under `src/.libs/`;
  the original P11/P12/P13 disassembly harness expected static-build paths.
  The harness now resolves both authentic layouts, preferring the direct
  static object when present. A three-case regression covers both layouts
  and missing-object refusal. No object is fabricated or copied for the test.
- Long independent DSD regression targets have separate logs and receipts.
  A timed-out or failed target must not be relabeled PASS; see the archive-root
  acceptance matrix for the final results and their scope.
- Offline dependency kit SHA-256:
  `3a5082945d0e92560da3a730160a2223dcbdc2791a276c9ff63739f485abcdff`.
  Archive-root `inputs/` and `evidence/phase06a/flac-qualification/` retain
  the kit, commands, extracted-version identity, receipts, and logs.

For the complete prior 06A engineering record, the historical checkpoint below
is preserved verbatim. Its original missing-FLAC/CONDITIONAL status is
superseded by this dated update. The archive-root `HANDOFF.md`, `RESUME.md`,
`SOURCE_STATE.json` and `ACCEPTANCE_MATRIX.json` supply the current release
status and continuation commands.

---

## Historical checkpoint before FLAC dependency delivery

# SoX DSD binary64: Phase 06A source checkpoint

**State: implementation and available-environment tests PASS; complete Phase 06A
acceptance CONDITIONAL.** This file accompanies a full source snapshot; the
archive-root `RESUME.md`, `HANDOFF.md`, `SOURCE_STATE.json` and `SHA256SUMS` are
the authority for package identity and exhaustive gate receipts.

## Provenance and requirements

- Required accepted starting commit: `14ee4d738d532a6d41671e65aba575f832064bb4`, carrying the Phase 05B play-wrapper gate correction.
- Original redacted source input SHA-256: `67beddc61f82b36370bf16038c8d4610d63e4ac2f0fe54d8042692bd6ae96f3b`.
- Original historical attribution `4548be78cf8b0be49026dd105f3888b8b2f0c28d` is **not** the imported Git implementation commit.
- Corrected immutable qualification harness SHA-256: `7d64bc18a7839786636c4a45365dd6d3e7ca42f0392b9c56f491bb2897954414`.
- Frozen DSD64 certificate: `96751b42b30b633e4b0ebc4d65fef4a4ab8988b6642ceef3bc279441bc07ae21`.
- Frozen DSD128 certificate: `2fcb74eb3974f9cf91a1b0913ed68e2b60df31222f157d41a0dc2fd0691d8010`.
- `inputs/OWNER_OVERRIDE.md` in the full archive supersedes the old 0.9/0.45 default warn contract for certified DSD64/DSD128. Preserve the accepted unity/0.5 contract and strict post-interpolation admission.

## Completed engineering units

1. Explicit `--precision 64` PCM-to-DSD64/128 source path, preserving the native source-rate double words through the existing SRC, interpolation, headroom, and frozen resonator. Gain operations retain their order. No source PCM `sox_sample_t` intermediate.
2. Existing DSF/DFF packed writers and nontruncating same-descriptor destination acquisition; exact source-derived native bit count, channel-role mapping, bounded working storage, protected report commits, and failure propagation.
3. Disabled-native PCM identity gates execute and pass; an unavailable native encoder is correctly reported `NOT_RUN`.
4. Post-clip admission oracle tests over 336,767 assertions, exact DSF/DFF payload comparisons, independent frozen recurrence/recovery state and negative controls.
5. CLI report-carrier regression tests for mixed-case effect filenames, `-` file operands, `SOX_OPTS`, pipe commands, numbered `newfile` destinations and hardlink/symlink aliases (`PCM64_SUITE=report-carriers`: 17 cases).
6. Default, native static, no-native static, shared-no-libltdl, no-FLAC static and sanitizer decode verification. Frozen source/proof subtree byte-identical to accepted Phase 05; selected default/32 output matches baseline byte-for-byte in 15 cases.

## Incomplete qualification

The environment has runtime `libFLAC.so.14` but lacks FLAC development headers (`FLAC/all.h`) and cannot resolve package repositories. The required `--enable-shared --disable-static --with-flac=dyn` configuration consequently has **not** compiled here, nor has real direct FLAC PCM-to-DSD encoding been accepted. This is UNRUN, never PASS. Some non-required ASan suites exhibit existing interposer/LSan issues; preserve actual stdout, exit status and independent accepted baseline instead of labeling them passed.

## Continue from the shipped full archive

```sh
sha256sum -c SHA256SUMS
./repro/verify-phase06a.sh
mkdir -p build-flac-dyn
cd build-flac-dyn
../source/configure --enable-shared --disable-static --with-flac=dyn
make -j4
make check-pcm64 PCM64_SUITE=encode
make check-pcm64 PCM64_SUITE=io-flac
make check-pcm64 PCM64_SUITE=pcm-identity
make check-pcm64 PCM64_SUITE=decode
make check-pcm64 PCM64_SUITE=report-carriers
make check
```

Run FLAC qualification on a host with real development headers. Record the
FLAC binary/codec hashes and complete per-case receipts, then repackage and
make a new acceptance decision. Until then the result is CONDITIONAL.

**Next phase, only after accepted 06A:** Phase 06B consumes the accepted 06A
revision and composes the binary64 DSD decoder with the certified encoder,
without modifying frozen kernels. The existing `auto` route stays legacy; no
DSD-to-DSD transcoding is claimed in this subphase. Interrupted audio jobs
restart from original inputs rather than resuming partial native state.
