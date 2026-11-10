# SoX DSD binary64: Phase 02A resume and scope boundary

**Status: Phase 02A source implementation PASS; Phase 02 (whole) INCOMPLETE.** This file travels inside `source/` in the handoff. The enclosing package's `RESUME.md`, `SOURCE_STATE.json`, checked `SHA256SUMS` and `evidence/phase02a/` provide the authoritative exported-archive and extraction verification.

## Immutable provenance

- Accepted Phase 01 input commit: `f0383d70ee871d10dfaea7042a0bfc0f77054168`, tree `b0222f5215ebdc88a850c8a1bd7b0cbaffd15407`.
- Original snapshot attribution `4548be78cf8b0be49026dd105f3888b8b2f0c28d` is **not** an imported Git implementation commit.
- Original snapshot SHA-256: `67beddc61f82b36370bf16038c8d4610d63e4ac2f0fe54d8042692bd6ae96f3b`.
- Immutable v2 harness SHA-256: `7d64bc18a7839786636c4a45365dd6d3e7ca42f0392b9c56f491bb2897954414`.
- Owner DSD64/DSD128 unity/no artificial front-end attenuation or clip ceiling decision remains in effect; no DSP kernel, effect, frontend CLI default or DSD profile changed.

## Completed units

1. First committed private-handler dispatch and build integration: `b7ae49d`.
2. Direct private WAV FLOAT64/FLOAT32/integer8/16/24/32 I/O, same-descriptor nontruncating native output acquisition and exact known-length bounded writer: `3305f7a`.
3. Independent RIFF/RIFX encoder and parser, true byte-level oracle, exact rational quantization and failure-sensitive Linux I/O fault gates: `89dd021`.
4. Mask/metadata correctness and observed fault hook telemetry: `a91c0c5`.

All of these commits are reachable from the full `git/history.bundle` in the parent archive. Native PCM processing is **not** exposed on the production CLI. Unknown or large WAV growth, large RF64, FLAC and full coordinator are deferred to later phases; no data silently passes through the legacy int32 bridge in the private direct path.

## Source-checkout gates (all PASS on this source revision)

- `autoreconf -fi`, `./configure --disable-shared --enable-static`, `make -j12 V=1`.
- `make check-pcm64 PCM64_SUITE=foundation`: **PASS**, 81,539 independently derived stream cases.
- `make check-pcm64 PCM64_SUITE=io-wav`: **PASS**, 224,027 decoded words, 9,074 finite FLOAT64 inputs, rational quantizer, 39 expected rejections, observed fault hooks, and 350,000 six-channel frames under a 96 MiB process virtual-memory limit.
- `make check`: **PASS**, including the ordinary WAV regression tests.
- A separately configured rebuild of parent Phase 01 for further A/B comparison exceeded its allotted process time and **is not a verified gate**. Ordinary CLI WAV smoke and the complete ordinary test suite passed. No assertion about that optional A/B was used for acceptance.

## Continue after interruption

Consult the enclosing archive's root `README-HANDOFF.md`, `RESUME.md`, `SOURCE_STATE.json` and `evidence/phase02a/RESULTS.md`. Check the bundled hashes and restore `git/history.bundle` before editing. A gate interrupted mid-run is UNRUN until its command returns zero and its receipt is checked. Build from this source by running:

```sh
autoreconf -fi
./configure --disable-shared --enable-static
make -j4 V=1
make check-pcm64 PCM64_SUITE=foundation PCM64_RESULTS="$PWD/evidence/phase02a-foundation"
make check-pcm64 PCM64_SUITE=io-wav PCM64_RESULTS="$PWD/evidence/phase02a"
make check
```

The next accepted input is the verified **Phase 02A FULL** archive, not the Phase 01 snapshot. Phase 02B must first recheck this safe writer, then add direct FLAC ingress without changing the proven WAV path. A separate Phase 03 handles RF64 and stdout-pipe qualification. A shell's `>` redirection can truncate before SoX starts; this writer does not protect against shell-side effects. After the validated descriptor is explicitly truncated and the header committed, an output error can leave partial bytes and must be reported as failure.
