# Phase 05A checkpoint (UTC 2026-11-13)

Status: RUNNING / acceptance UNVERIFIED. This file is the durable checkpoint
for interrupted sessions; only full gate receipts in evidence may claim PASS.

Accepted input: Phase04 HEAD ed5de7b27a6c42f74f6172ee5260acadb8848980,
source tree c3b3b93c61e2f9af99d2c3e0362f81190761446e.
Original source attributed commit 4548be78cf8b0be49026dd105f3888b8b2f0c28d,
original input SHA256 67beddc61f82b36370bf16038c8d4610d63e4ac2f0fe54d8042692bd6ae96f3b,
harness SHA256 7d64bc18a7839786636c4a45365dd6d3e7ca42f0392b9c56f491bb2897954414.
Phase04 delivery VERIFY_RETURN.sh PASS, history.bundle clone and fsck PASS.

Branch: phase05a-native-pcm; repository /mnt/data/sox_phase05a_work/working-repo
Build root /mnt/data/sox_phase05a_work/build-phase05a.
Baseline (no FLAC): configure/build, Phase01 foundation, Phase02 io,
Phase03 large-wav, Phase04 routing passed before editing, in ../baseline-*.log.

Implemented at this checkpoint:
- Private bounded native binary64 PCM coordinator, frame/accounting, ordered gains,
  finite word identity, explicit EOF, failure latching, caller-owned scratch.
- Actual WAV/FLAC reader adapters and single descriptor-preserving WAV writer
  integrated into an explicit --precision 64 PCM-only CLI route; no legacy
  fallback on native failure, no changed public effects/sample API.
- Corrected exact64 plan facts, ordinary PCM --precision auto/32 handler
  compatibility, PCM-only headroom refusal, WAV unsigned bits and non-WAV
  floating endpoint label.
- Independent direct buffer probe: 7,023 assertions passed.
- CLI `pcm-identity` suite PASS in a second local built-in FLAC 1.5.0 build,
  compiled offline from the immutable Phase04 vendored FLAC/ogg input. Nine
  independent FLAC code fixtures checked 121,387 exact F64 values; 25 gate
  groups. First no-FLAC build is still available as an optional topology.
  Coverage: raw sample identity, 32/24/16/8 normalization, ordered gain,
  target integer and FLOAT32 quantization,
  channel/no-op, alias/sentinel, hostile fenv, injected writer close/write,
  stdout and report, plan overhead/throughput. Receipt in ../accept-05a/.

**Next before finish**: rerun predecessor suites in built-in FLAC topology;
run CLI and make check; check signal and reporter receipts against final code;
create full delivery including all immutable Phase04 evidence/inputs;
checksum, fresh extract, git replay and rebuild before claiming acceptance.

Reproduce initial acceptance:
  cd /mnt/data/sox_phase05a_work/build-phase05a
  make -j8 && make check-pcm64 PCM64_SUITE=pcm-identity PCM64_RESULTS=/mnt/data/sox_phase05a_work/accept-05a

Current status: RUNNING/UNVERIFIED until all tests rerun on final commit.

2026-11-13 18:02 UTC: Phase04 routing suite PASS_WITH_NOT_RUN (108 checks,
256 commands) in built-in FLAC and 79 checks in no-FLAC; native 05A suite
PASS 25 groups including SIGINT after committed header and writer-clip
accounting. DSD CLI and make check still UNRUN on final changes.
