# SoX-NG P15 R6: persisted mathematical-engineering checkpoint

**Date:** 2026-10-19. **Starting identity:** `cc399928` source archive SHA-256 `d058b3908817e01e937f49e0dfeee7194d847aae74f625043e881d8b8f0e9210`.

## Completed and sealed

1. Verified all 49,323 archive members extracted under `sox_ng/` and original source archive digest; verified separately supplied proof companion's SHA256SUMS. No production `src/rate.c`, `src/fft4g.c`, or FIR processing changes.
2. Inspected the actual legacy composite modules and full governing §8.6.1 design. Historical campaign inventory remains 11,516 distinct receipts (2,850 pass; 8,666 stop; 72 source/rate cells). No historical receipt edited.
3. Audited the existing R5.1 pure-integer trig/FIR enclosures; installed byte-identical copies. Independently implemented exact-ln10 policy, composite SRC branch recurrence and alias cap, exact-frequency leaf witness replay, fail-closed verifier, deterministic evidence sealing, unit tests, real-certificate corruption tests.
4. **Source-bound real full-canonical mathematical proofs:** `MASTER64_44100_PASS_0000_1000.json` and `MASTER64_44100_STOP_0000_1000.json`, under `tests/dsd/results/P15_R6_EXACT_COMPOSITE_2026-10-19/`. Both independently replay and PASS; 8 passband leaves, 1 stop leaf, 165 FIR evaluations total, 180 alias frontier expansions total. No finite-point-only conclusion.
5. **19/19 unit tests; 5/5 corrupted real witness refusals.** `EVIDENCE.json` records the hash-bound stage/operator and method identities, complete historical inventory, independent certificate replays and seven-gate outcome.

## Exact unresolved obligations

- **11,514** of the 11,516 canonical original receipts still need independent mathematical proof witnesses under the new sound verifier (or a complete separate theorem proving the original interval backend/composite source recurrence mathematically valid). No aggregate historical PASS flag discharges these obligations.
- **High-rate computational tractability:** attempted `dsd256.mastering_v2.pcm384000`, `[0,1000]`, with the bounded producer; first leaf exceeded the external 60-s execution guard, yielding no certificate. The producer checkpoint is atomic *between* leaf visits, but a single expensive leaf cannot presently be preempted safely by its `deadline_seconds`; must address this before a fleet-wide campaign. Do not claim high-rate coverage or falsely mark computational timeout a spectral FAIL.
- **Provenance:** Historical generating-prover revision hash is not attested by existing aggregate receipts. No retrospective manifest authenticates the original execution.
- **Separate release obligations:** arbitrary-input actual compiled FFT4G correspondence, multithread cache contract or verified single-caller restriction, final ELF identity and runtime FP mode, and end-to-end finite-stream/roundoff release theorem. Physical measurements passed for historical host/binaries but are not transferable without binding.

## Next minimal coherent mathematical change

Bound per-leaf work safely (including within alias/FIR calculations), use sound cheap global majorants and adaptive shorter exact rational leaves for expensive 384-kHz / DSD256 paths. Run only source-bound proof generation for original canonical jobs with no R6 witness, retaining atomic OPEN checkpoints and hashes. Verify each candidate leaf against the independent `--verify` path; do not trust historical interval maxima. The historical campaign is already a coverage inventory and should not be recomputed as exploratory PASS flags.

## Reproduction / integration

Install the additive proof overlay into a clean, SHA-verified original source snapshot; in source root run:

```sh
PYTHONPATH=tests/dsd python3 -m unittest -q test_p15_r6_exact_composite
PYTHONPATH=tests/dsd python3 tests/dsd/p15_r6_witness.py --verify \
  tests/dsd/results/P15_R6_EXACT_COMPOSITE_2026-10-19/MASTER64_44100_PASS_0000_1000.json
PYTHONPATH=tests/dsd python3 tests/dsd/p15_r6_witness.py --verify \
  tests/dsd/results/P15_R6_EXACT_COMPOSITE_2026-10-19/MASTER64_44100_STOP_0000_1000.json
PYTHONPATH=tests/dsd python3 tests/dsd/p15_r6_adversarial_replay.py
PYTHONPATH=tests/dsd python3 tests/dsd/p15_r6_seal_evidence.py --out /tmp/R6_SEAL_REPLAY.json
```

The sealer's regenerated JSON differs from packaged `EVIDENCE.json` only in the `source_archive_verified_directly` flag if called without `--source-archive` (and must otherwise reverify mathematical and source content). Method-module hashes are included literally in each proof. If a bound method module is modified, existing R6 proof objects require a deliberate source-hash rebinding and full exact replay; do not silently edit or re-sign them. Original historical receipt files are immutable.

**Final checkpoint status:** mathematically substantive but **P15 independent ideal spectral gate CONDITIONAL**; 2 independently qualified exact jobs, 11,514 OPEN. Overall P15 OPEN. This is the maximal justified conclusion from this handoff.

## Download-distribution re-extraction QA

Both archive members and byte contents were rehashed after packaging. The independently extracted complete proof-source tree passed its 11,790-entry file digest manifest, 19 tests, two real complete-interval certificate replays and all five deliberately corrupted proof refusals. The addon member list was compared to every original source archive file name: zero collisions. See `P15_R6_CC399928_ARCHIVE_MANIFEST.json` distributed with the response for archive-level hashes and sizes.
