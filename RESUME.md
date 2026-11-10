# SoX DSD binary64 Phase 02A: resumable engineering state

**Current checkpoint:** RUNNING / UNVERIFIED as a delivery. Phase 02A is not accepted until all gates have verified receipts and the exported tarball itself has been re-checked.

- Accepted Phase 01 input HEAD: `f0383d70ee871d10dfaea7042a0bfc0f77054168` (verified via history.bundle and source/manifest comparisons).
- Original source snapshot attribution: `4548be78cf8b0be49026dd105f3888b8b2f0c28d` (NOT a Phase 02A implementation commit).
- Original source snapshot SHA-256: `67beddc61f82b36370bf16038c8d4610d63e4ac2f0fe54d8042692bd6ae96f3b`.
- Immutable corrected qualification harness SHA-256: `7d64bc18a7839786636c4a45365dd6d3e7ca42f0392b9c56f491bb2897954414`.
- Owner DSD64/DSD128 unity/no artificial front-end ceiling decision remains in effect. No DSP kernels, profiles, release defaults or CLI native switch changed.
- Coherent first implementation checkpoint: `b7ae49d` (private handler dispatch and build scaffolding). The current working tree includes native WAV I/O, safe descriptor acquisition, deterministic private probe and independently constructed fixtures. Do not treat a nonempty git status as an accepted release.
- Completed locally before first Phase 02A edit: baseline `make check-pcm64 PCM64_SUITE=foundation`, 81,539 streamed cases, PASS.
- Current draft io-wav suite in `tests/pcm64/io_wav.py`: direct invocation PASS (224,027 words decoded, 30 expected refusals, late output failures, symlink races, permission denial, no legacy CLI mutation). **Must rerun after final edits and build changes.** See external working evidence until packaged.

## Next actions and acceptance commands

1. Extend the negative I/O, no-compression writer, mixed-access, bounded memory and performance matrix where justified; inspect signed headers and warnings.
2. `autoreconf -fi && ./configure --disable-shared --enable-static` as appropriate for clean build environment; `make -j4 V=1`.
3. `make -C test pcm64_probe pcm64_wav_probe`; `make check-pcm64 PCM64_SUITE=foundation PCM64_RESULTS="$PWD/evidence/phase02a-foundation"`; `make check-pcm64 PCM64_SUITE=io-wav PCM64_RESULTS="$PWD/evidence/phase02a"`; `make check` and targeted WAV compatibility tests.
4. Commit completed gates, record exact resulting full commit and tree, export `git/history.bundle` and full `source/`, preserve all Phase 01 inputs, architecture, prompts, evidence, immutable harness; generate and validate `SHA256SUMS`.
5. Fresh extract full tarball to a new directory and verify SHA256SUMS, git history and source identity, build plus both suites. Evidence from the extraction becomes the final acceptance gate.

## Safety boundary

Named existing destinations are never opened with `O_TRUNC` or `"w+b"` in the private writer path. Existing regular-file identity and aliases are checked on the retained descriptor; explicit `ftruncate` after all precommit checks is the commit point. A caller's shell `>` redirection is outside SoX and may truncate before launch. Output can be partial if I/O fails after commit. No FLAC, RF64 or production CLI binary64 activation in Phase 02A. This package is **not** a Phase 02 acceptance until 02B passes.
