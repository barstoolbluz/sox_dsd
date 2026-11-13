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
- CLI `pcm-identity` suite initial PASS_WITH_NOT_RUN (built-in FLAC development
  headers absent in first no-FLAC build): raw sample identity, 32/24/16/8
  normalization, ordered gain, target integer and FLOAT32 quantization,
  channel/no-op, alias/sentinel, hostile fenv, injected writer close/write,
  stdout and report, plan overhead/throughput. Receipt in ../accept-05a/.

**Next before finish**: investigate FLAC library/header availability and run
built-in FLAC qualification if possible; rerun suite and predecessor suites
against final tree; run CLI and make check; inspect abnormal signal, report
failure, truncation, unknown layout and source/header hazards; commit fixes;
create full delivery including all immutable Phase04 evidence/inputs;
checksum, fresh extract, git replay and rebuild before claiming acceptance.

Reproduce initial acceptance:
  cd /mnt/data/sox_phase05a_work/build-phase05a
  make -j8 && make check-pcm64 PCM64_SUITE=pcm-identity PCM64_RESULTS=/mnt/data/sox_phase05a_work/accept-05a

Current status: RUNNING/UNVERIFIED until all tests rerun on final commit.
