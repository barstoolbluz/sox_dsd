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
