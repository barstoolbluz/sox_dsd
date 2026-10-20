# P15 R6 independent spectral mathematics: adversarial execution record

**Date:** 2026-10-19. **Source:** `cc399928`.
**Base archive SHA-256:** `d058b3908817e01e937f49e0dfeee7194d847aae74f625043e881d8b8f0e9210`.

## Executed, not just proposed

- Independently checked the complete original canonical receipt namespace: **11,516 unique jobs / 11,516 receipts / 72 cells**; 2,850 recorded pass and 8,666 recorded source-stop dispositions. This confirms historical *coverage*, not rigorous independence of its aggregate arithmetic.
- Verified the supplied P15 R5.1 proof-companion digest list (`P15_CC399928_COMPANION_SHA256SUMS.txt`) with `sha256sum -c` before copying two original integer-math modules. The original source archive hash matched its specified SHA-256.
- Recomputed every exact-rational leaf from the production-captured source-bound stage snapshot, with the newly authored independent integer composite checker, for the complete *canonical* `[0,1000]` Hz passband and source-stop intervals of `dsd64.mastering.pcm44100`. Both were **PASS-LOCAL-R6-INDEPENDENT**, with independently reconstructed results and unchanged P15 strict policy limits.
- Passed **19/19** adversarial/analytic Python unit tests; tested malformed stage clocks, source coefficient binding mutation, negative/signed FIR taps, severe cancellation, exact Nyquist, exact branch/harmonic lattices, proper profile threshold refusal, halfband symmetry refusal, complete-quarter continuum cap and proof-record mutations.
- Deliberately corrupted **five copies** of an actual source-bound R6 certificate: source-binding identity, mathematical method hash, interval final endpoint, exact source-stop transfer value, and aggregate claim. **5/5 REFUSED; 0 false acceptances.** Original evidence was never touched. Machine-readable individual refusal explanations are in `results/P15_R6_EXACT_COMPOSITE_2026-10-19/ADVERSARIAL.json`.
- Attempted a bounded first `dsd256.mastering_v2.pcm384000` passband `[0,1000]` canonical witness. The first composite computation exceeded a 60-second outer execution timeout, without publishing a proof. Its status remains **OPEN**, and it is not counted as certified. The budget was an outer command timeout: the producer's per-leaf mathematical work does not yet admit hard mid-leaf preemption; this is a known resumption limitation rather than a proof failure.

## Reproduction commands

Run in the verified `sox_ng/` source root (with the additive bundle installed):

```sh
PYTHONPATH=tests/dsd python3 -m unittest -q test_p15_r6_exact_composite
PYTHONPATH=tests/dsd python3 tests/dsd/p15_r6_witness.py \
  --verify tests/dsd/results/P15_R6_EXACT_COMPOSITE_2026-10-19/MASTER64_44100_PASS_0000_1000.json
PYTHONPATH=tests/dsd python3 tests/dsd/p15_r6_witness.py \
  --verify tests/dsd/results/P15_R6_EXACT_COMPOSITE_2026-10-19/MASTER64_44100_STOP_0000_1000.json
PYTHONPATH=tests/dsd python3 tests/dsd/p15_r6_adversarial_replay.py
PYTHONPATH=tests/dsd python3 tests/dsd/p15_r6_seal_evidence.py \
  --out /tmp/P15_R6_INDEPENDENT_EVIDENCE.json
```

For the explicit verification of the provided base archive, also pass `--source-archive /path/to/sox_ng-P15-adjudicate-cc399928.tar.gz` to the evidence sealer. Without that optional input, it rechecks local files and independently derived certificates but correctly sets `source_archive_verified_directly=false`.

### Observed wall times (this validation environment)

CPython 3.13.5; timings for the repeat execution (not performance qualification): passband witness replay **15.67 s**, source-stop witness replay **4.82 s**, unit-test suite **3.10 s** (19 tests, 2.070 seconds reported internally). Both real witness verifications checked the complete interval and reproduced the exact bound strings. `EVIDENCE.json` incorporates the method/source/hash inventory and seven-gate status.

## Adversarial limits and remaining proof work

A successful local exact proof is **not** a release qualification; only **2 of 11,516** original canonical jobs currently have independently reconstructed proof objects. The integer checker uses a source-bound stage exporter and externally pinned source/coefficients, not a new binary-level disassembly proof. Even a fully independent ideal mathematical campaign would not discharge arbitrary-input release FFT4G arithmetic, end-to-end finite-stream error, measured binary lineage, cache-concurrency, or host sign-off.

The checker is fail-closed on exhausted FIR budgets or mathematical branch transitions, but the producer can be expensive **within one leaf**. Candidate frontier subdivision is resumable only between completed leaf visits. The DSD256/384-kHz stress probe does not qualify a single new interval. Do not interpret the absence of a completed witness as evidence of an unsound filter or as a mathematical counterexample.

Exact-integer arithmetic and the rigorously bounded ln(10)/exp transcendental operations are set out in `docs/dsd/P15_R6_MATHEMATICAL_PROOF.md`; numerical agreement alone is not the proof.

## Clean distribution integration check

A deterministic proof-source archive of **11,791 regular files**, gzip size **5.45 MB**, was extracted into a new directory. Its source checksum manifest checked **11,790 files**, all matches. Executed the 19 unit tests again (**19 PASS**), independently replayed the two actual source-bound complete canonical certificates (**2 PASS**) and reproduced all five on-copy corruption refusals (**5 REFUSED**) in that new directory. The separate addon contains only new files, tested for absence of filename collisions against the pinned source archive. Both generated archives remain below 140 MB.
