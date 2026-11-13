# Phase 05A implemented: source and resume checkpoint (2026-11-13 UTC)

This source branch implements the Phase 05A **native PCM-only** binary64
coordinator. It does not implement DSD reconstruction/encoding in strict64.
Auto/32 and the DSD defaults retain the existing execution path. The full
handoff's root `RESUME.md`, `SOURCE_STATE.json`, and `evidence/phase05a/`
contain the acceptance decision and executed, binary-bound gate receipts.

Accepted predecessor: Phase 04 result
`ed5de7b27a6c42f74f6172ee5260acadb8848980`, tree
`c3b3b93c61e2f9af99d2c3e0362f81190761446e`.
Source attribution `4548be78cf8b0be49026dd105f3888b8b2f0c28d`
(source archive SHA-256
`67beddc61f82b36370bf16038c8d4610d63e4ac2f0fe54d8042692bd6ae96f3b`);
qualified independent harness archive SHA-256
`7d64bc18a7839786636c4a45365dd6d3e7ca42f0392b9c56f491bb2897954414`.
Neither of these source identities is the Phase 05A implementation commit.

Changes:
- `src/dsd_f64.c/h`: bounded fixed-shape interleaved F64 coordinator,
  borrowed input, copy-only identity with finite-word preservation, ordered
  gains, final role permutation, partial progress/EOF and latched failures.
- `src/sox_ng.c`: explicit strict64 PCM-only runner with a single source and
  output, existing gain parser/factors and actual plan ownership; no int32
  intermediate; legacy graph preserved. DSD profile selectors cannot be
  silently ignored by an ordinary PCM command.
- `src/wav.c`, `src/formats.c`, `src/dsd_plan.c/h`: exact WAV/FLAC reader
  eligibility, retained-descriptor native WAV output, explicit output-depth
  handling, endpoint saturation count and accurate plan/report engine facts.
- `tests/pcm64/pcm_identity.py`, `coordinator_probe.c` and routing tests:
  independent word-level oracle, negative controls, stream/lifecycle,
  auto/32 comparison, mask cases, planning and throughput receipt.

**Reproduction from source** (out-of-tree build; gcc/clang, autotools, Python3):

    mkdir build && cd build
    ../source/configure --without-flac --disable-shared
    make -j4
    make check-pcm64 PCM64_SUITE=pcm-identity PCM64_RESULTS="$PWD/results-05a"
    make check-pcm64 PCM64_SUITE=routing PCM64_RESULTS="$PWD/results-routing"
    make check-dsd-cli
    make check

The strict64 FLAC ingestion gate requires a built-in FLAC build. An offline
FLAC 1.5.0/libogg source archive and setup script are preserved in the
handoff's immutable `inputs/` from Phase 04. Configure a second build with
those development libraries and `--with-flac=yes`, then run the same gates.
A no-FLAC topology rightly marks its FLAC-specific check NOT_RUN rather
than claiming FLAC exactness.

**Next:** Phase 05B consumes accepted 05A (`PHASE-05B.md`) and connects the
existing qualified DSD decoder to this coordinator. Do not infer completion
of Phase 05, nor authorization of an automatic DSD native route, from 05A.
