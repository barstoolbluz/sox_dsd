# P15 optimization — measured performance and certification outcomes

**2026-10-18.** The machine-readable authority for these figures is `RESULTS_SUMMARY.json`, with raw, immutable benchmark lines in `BASELINE_*.jsonl` and `OPTIMIZED_*.jsonl`. The original submitted 11,516-interval evidence was not modified. **No full optimized 11,516-interval campaign has been run.** All PASS results below are source-bound ideal-coefficient *local continuum* proofs, never release certification.

## Reference scope and selection

The source campaign at its original 60-second per-interval budget recorded 6,835 local PASS and 4,681 OPEN (3,907 timed-out, 774 refused by a structural operator/path precondition). We independently formed a deterministic, SHA-source-bound **104-case corpus** containing every one of the 43 historically stalled intervals, 25 representative pass/stop and open/pass cases spanning DSD64/128/256 and both rate families, and the archived 48-case 600-second sample (deduplicated). `CORPUS.json` records exact canonical index and reason for inclusion. The 60-second showcase below is an intentionally selected hard-case subset, **not** an unbiased estimate of campaign-wide closure.

## Paired short-budget benchmarks on this execution host

| Corpus | Per-job budget | Original reference | Optimized prover | Actual measurement |
| --- | --- | --- | --- | --- |
| All historical stalls (43) | 4 seconds | 43 OPEN | 43 OPEN | Original 839 vs optimized 4,363 FIR interval evaluations across the same 43 intervals; median within-job evaluation count ratio **5.14x**. These short runs are all unresolved, not certified. |
| Representative (25) | 2 seconds | 2 local stop PASS; 23 OPEN | 3 local stop PASS, 1 local passband PASS; 21 OPEN | Two additional local passes at the same budget. Exact dispositions and failure reasons are in the raw lines. |

The count ratio is a **throughput diagnostic under fixed budgets**, not an end-to-end benchmark speedup claim. Some cases exit on an operator precondition before meaningful numerical work. Each `OPEN` can mean time budget or a sound refusal; the JSONL records the actual reason. Numerical evaluations in this implementation are bounded by exact source coefficients and outward-rounded intervals, not sampled FFT responses.

## Hard, 60-second source-bound campaigns

Every item below was `OPEN` for wall time in the archived source campaign at 60 seconds. The optimized times are measured on the same current host with a 60-second per-job cap. Only index 3001 was also independently rerun here under the original implementation at the identical cap (and again returned OPEN at 60.003s); do not interpret the other timings as measured baseline/optimized speedup ratios.

| Canonical index | Source-bound cell | Frequency window, Hz | Optimized wall time | Outcome | Peak process RSS, KiB |
| --- | --- | --- | --- | --- | --- |
| 577 | DSD64 mastering → PCM 384k | 0–1,000 | 60.006s | **OPEN**, benchmark time exhausted | 277,644 |
| 3001 | DSD128 mastering → PCM 384k | 0–1,000 | 34.117s | **PASS-LOCAL-BAND** | 172,252 |
| 3878 | DSD128 wideband → PCM 192k | 0–1,000 | 53.383s | **PASS-LOCAL-BAND** | 181,392 |
| 5597 | DSD256 mastering → PCM 384k | 0–1,000 | 34.191s | **PASS-LOCAL-BAND** | 180,600 |
| 6856 | DSD256 wideband → PCM 384k | 1,000–2,000 | 22.225s | **PASS-LOCAL-BAND** | 173,336 |
| 9152 | DSD128 mastering_v2 → PCM 192k | 0–1,000 | 59.822s | **PASS-LOCAL-BAND** | 181,296 |
| 9521 | DSD128 mastering_v2 → PCM 384k | 0–1,000 | 35.879s | **PASS-LOCAL-BAND** | 172,304 |

**Six new local continuous-frequency passes** were obtained from seven hard-case replays; the one remaining OPEN is **not** a witnessed spectral failure. Source-family coherent-alias upper bounds for the six PASS cases are in the machine-readable results and remain below `10^-8` in the captured interval certificates. The total transfer upper bounds also satisfy the unchanged ±0.0001 dB band requirement. No FAIL was independently established.

`optimized_dispatch_receipts/` contains a **new** bounded canonical dispatcher receipt for index 3001, with bound source identity for all 35 pinned source paths, one 0–1,000 Hz PASS-LOCAL-BAND, 835 FIR evaluations, and `qualified_release=false`. The same dispatcher invocation on the existing output directory left the receipt SHA-256 **unchanged**; its aggregate summary stayed OPEN with 11,515 still missing.

## Source FIR numerical bottleneck, measured independently

At warm steady state, the standalone exact FIR arithmetic benchmark comparing original full complex mpmath interval recurrence with exact-integer-grid cosine/Taylor interval recurrence returned approximately **8.71x (57 taps)**, **5.98x (153)**, **6.20x (720)**, **6.14x (1,005)**, **6.38x (1,845)**, and **6.14x (4,160)** faster individual rigorous source FIR magnitude enclosures, under identical phase/interval/tap input. The arithmetic benchmark's observed process peak RSS was **182,660 KiB**. Measurements are on this container and are not promised on other hardware. Exact raw medians/timings are in `FIR_MICROBENCH.json`.

`PROFILE_COSTS.json` has independent instrumented cProfile breakdowns. The high cost in long-filter cases is interval arithmetic, phase recurrence and repeated coefficient work; the new fast path avoids per-tap mpmath multiprecision interval products after an outward-rounded trig anchor. The 499/499 source stage occurrences are exactly even (`STAGE_PARITY_AUDIT.json`), enabling algebraic reduction without approximation. Original unoptimized reference remains callable for asymmetric FIRs and independent checks.

## Limits and nonclaims

- The historical 11,516 receipts are **not** recertified by the new engine. The source baseline's **4,681 OPEN** and its 774 structural refuses must not be silently reduced or relabeled.
- Certain factorized stage paths collide in primitive native source-frequency families; the unchanged safe precondition rejects them. Increased wall time cannot address that mathematical issue. Neither this optimization nor a bound on an individual FIR discharges it.
- Alias-path partitioning, calculation of a sound numerical interval, and certification of a strict spectral inequality are distinct events. Exact splits do not imply PASS.
- The triangle-inequality coherent population majorant remains conservative. No undocumented phase-cancellation or alias cutoff was introduced.
- The P15 whole-resource arithmetic roundoff proof (FFT4G), the DSD256 matched physical comparator and full source/rate coverage/release adjudication remain **OPEN**. No v2 default switch or P16 authorization follows.

For proofs of the new algebraic/numerical bounds, see `MATHEMATICAL_METHODS.md`. For executable replay and interruption-safe continuation, see `CONTINUATION.md`.
