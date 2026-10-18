# P15 — Source-bound numerical prover: validated even-FIR dyadic Taylor acceleration

**Date:** 2026-10-18  
**Input:** `sox_ng-P15-prover-optimization-76282bdc.tar.gz`, SHA-256 `82c6e31d24b37b18ff5c60bb18f7c1dd266988da6cace9687005c2c6384365c2`  
**Scope:** The independent ideal, stationary, source-captured FIR/SRC spectral-prover arithmetic. No production signal-processing source or filter coefficient was changed.

## 1. Distinguish the certification obligations

A finite rational alias partition establishes where a family of *analytic* stage-transfer products applies. It does not bound that product, and it does not certify a spectral inequality. A validated interval enclosure for a FIR transfer establishes only a lower/upper *bound*; `PASS-LOCAL-*` requires checking the complete coherent family bounds against the normative constants for every frequency in that interval. A release PASS additionally requires complete 72-cell frequency coverage, independently bounded same-operator arithmetic (including FFT4G execution roundoff), comparator evidence and the other independent P15 obligations. This change affects the second and, for some intervals, third steps only. Release stays BLOCKED.

The acceptance constants have **not** changed: passband error ±0.0001 dB relative to unity; coherent stop/fold/alias upper strictly below `10^-8` amplitude (−160 dB). No RMS estimate, sampled-grid condition, omitted source families, numerical cutoff or relaxed band limit is used.

## 2. Audited source-specific algebraic reduction

For a source-stage coefficient witness with binary64 coefficients `h[k]`, verified after the current operator/snapshot SHA checks, the existing trigonometric polynomial uses

```
H(x) = sum_k h[k] exp(2*pi*i*k*x).
```

If and only if `center==0`, all coefficient positions are unique, all values are finite, and every **nonzero** coefficient has a counterpart `h[-k] == h[k]` by exact binary64 equality, this becomes

```
H(x) = h[0] + 2 sum_{k>0} h[k] cos(2*pi*k*x).
```

This is an exact identity of the same source-bound polynomial, not an approximation, FIR change, or assumption of linear phase. An unpaired **zero** tap makes no contribution, and is explicitly permitted. It matters for source kind-3 polyphase carriers which retain a zero leading sentinel. A non-even witness falls back to the original validated general complex interval recurrence. Empty, duplicate, nonfinite and otherwise invalid witnesses must never be optimized into a zero filter certificate.

`STAGE_PARITY_AUDIT.json` records the independently replayable audit over all **72** SRC-active cells, **24** verified stage operator pairs and **499** stage occurrences: **all 499** are exactly even. There are **50** unique stage witnesses, all even. This audit establishes coefficient parity, not spectral acceptance.

The stage scaling by `1/L`, reverse alias paths and exact rational frequency translations are unchanged. In particular, source tap identity still passes through existing source/bank hashes and snapshot bindings. Only the *interior evaluation of the same finite polynomial* changes.

## 3. Taylor enclosure over a complete closed frequency interval

For normalized frequency `x in [a,b]`, set midpoint `m=(a+b)/2`, radius `r=(b-a)/2`, and `p=order+1` with order 1–12 (default 8). Define real derivatives

```
D_j = 2 sum_{k>0} h[k] (2*pi*k)^j cos(2*pi*k*m + j*pi/2)
      + h[0] if j==0.
```

For every `x` in the **whole closed interval** Taylor's theorem and `|cos| <= 1` give

```
|H(x)-H(m)| <= sum_{j=1}^order |D_j|*r^j/j! + R_p,
R_p <= (2*pi*r)^p / p! * M_p,
M_p = 2 sum_{k>0} |h[k]| k^p.
```

`M_p` is computed **exactly as a Fraction** from every finite binary64 word (`Fraction.from_float`), with no floating sum, dropped tap, amplitude threshold or cancellation assumption. It is safe to reuse for narrower intervals of the same immutable polynomial.

The computed signed real derivatives are intervals `[D_j^-, D_j^+]`. The variation upper uses `max(|D_j^-|,|D_j^+|)` and rational `r^j/j!` with integer **ceil**, plus `M_p * (2*pi upper)^p * r^p/p!`, also ceiled exactly. The magnitude of the midpoint signed interval is enclosed by `[0,max(|D_0^-|,|D_0^+|)]` if it straddles zero, or the appropriate positive distance from zero otherwise. Subtract the full variation from its lower endpoint and add the variation to its upper endpoint. A negative lower estimate is conservatively floored at zero by the existing stage caller. The returned magnitude bound therefore applies at both endpoints and **all interior real frequencies**, including zeros/cancellation.

## 4. How every arithmetic operation is enclosed

`p15_src_fixed_interval.py` uses an **integer dyadic grid** with `Q=2^288`. An integer pair `(L,U)` represents the exact real interval `[L/Q,U/Q]`. Interval addition/negation are exact integer operations. Interval multiplication takes the minimum and maximum of the four exact integer endpoint products, then rounds `min/Q` **down** and `max/Q` **up**, respectively. A fast two-endpoint multiplication is allowed only when both interval lower endpoints are verified nonnegative; otherwise it fails closed. Multiplication by a source binary64 coefficient uses `float.as_integer_ratio()` and integer floor/ceil, so the coefficient's bit pattern is retained exactly. Doubling/negating derivative terms is performed with integers, not rounded binary64 intermediates.

For each Fourier position an enclosing cosine/sine pair is obtained from **75-digit mpmath directed interval** trigonometry at the exact rational midpoint angle (`2*pi*m*k`). Subsequent adjacent phase positions use the exact algebraic recurrence

```
cos(A+B) = cos(A)cos(B) - sin(A)sin(B)
sin(A+B) = sin(A)cos(B) + cos(A)sin(B).
```

All four operands are directed dyadic intervals; hence the interval recurrence always contains the true complex rotation. Re-anchoring after 48 steps reduces interval-width amplification; the re-anchor is a performance/tightness control, not an accuracy shortcut. The directed `mpmath.iv` trigonometric endpoints are read as **exact dyadic endpoint tuples** and rounded onto the 288-bit integer grid *outward*. Nonfinite/unknown internal formats fail closed. `2*pi` is likewise rounded outward before the exact rational Taylor-remainder calculation. Finally integer-grid bound endpoints are converted with directed mpmath rational conversion (`scalar`) so the caller receives a valid outward interval.

**Trusted components:** The interval-trigonometry and final rational conversion inherit mpmath's directed-rounding semantics. This is not an independent formal verification of mpmath itself. The arithmetic afterward is elementary exact integer arithmetic, with the explicitly described rounding steps. No `math.sin`, `math.cos`, NumPy FFT, ordinary binary64 sum or sampled-point verification enters the new PASS route.

## 5. Caching, alias completeness and proof reuse

The source-operator stage objects are immutable and are now memoized by immutable operator identity/profile. The stationary alias schedule is enumerated through unchanged exact-rational boundary logic. Once a whole interval has passed *all* crossover checks, dyadic children reuse its identical analytic paths: a subset of a stationary interval cannot introduce a transition absent from the parent. A split exactly at a rational crossover instead invalidates the pending schedule and enumerates each one-sided region separately. No endpoint is omitted; the analytic transfer inequalities extend to each closed interval's endpoints by continuity.

The existing path population proof tree remains intact: each unexpanded prefix contributes **all** of its descendants multiplied by the exact binary64 absolute FIR L1 gains of remaining stages. Path ordering or the new fast evaluator cannot make a rejected subtree disappear. Coherent transfers are still bounded by the triangle inequality, not RMS. This conservatism can keep some cases `OPEN`; it cannot make an incorrect `PASS` on its own. No phase-aware cancellation is assumed when summing aliases. No change was made to the pinned `p15_src_complete_aliases.py` or to production `src/*`, so the rebound operator receipt directory remains valid.

## 6. Independently replayable checks

`test_p15_prover_fixed_interval.py` checks exact integer interval arithmetic with rational reference products; algebraic symmetry validation and asymmetric fallback; randomized directed enclosures; Nyquist and rational intervals; zero and near-zero amplitudes; a 1,601-tap alternating-sign cancellation stress; independent **direct complex interval** evaluations at endpoints and interiors; an independently implemented **real mpmath interval** Taylor evaluator; multi-path/alias majorant enclosures; and both one-sided regions of an exact source-bound alias boundary. These tests exercise enclosure rather than merely approximate equality. Existing P15 stage/interval/dispatcher tests remain executable.

`p15_prover_fir_microbenchmark.py` compares the **unaltered original general complex recurrence** with the new real fixed-point arithmetic on exactly identical source FIR taps at 75-digit precision, warm in the same process. `p15_prover_benchmark.py` can replay whole canonical jobs against `baseline_code/` (byte-for-byte original stagewise numerical code from the SHA-pinned input archive) or against the corrected implementation. Each job has a hard wall-clock budget, memory counters, path/timing instrumentation and append-only, fsynced JSON-lines records. `CORPUS.json` binds the historical 43 stalls, source campaign PASS/OPEN representatives, DSD64/128/256 and 44.1/48-kHz families, plus the independent 48-job historical 600-second sample (with overlaps deduplicated). `p15_prover_build_corpus.py` rebuilds the selection deterministically from immutable original evidence.

The archived 11,516 original campaign receipts, historical 43-stall schedule receipts and 48 extended-budget receipts remain in their original locations without modification. Numerical evaluation reports, benchmark summaries and new proof evidence are separate. **None of the benchmark jobs writes release authorization or overwrites campaign receipts.**

## 7. Known mathematical limits and honest OPEN categories

- The complete original campaign has 6,835 local passes and 4,681 OPEN at 60 seconds; 3,907 OPEN were wall-budget exhaustion, 774 structural operator/path preconditions. These original counts are not silently changed by sample successes.
- Some operators factor the reduced ratio through an additional decimation, so multiple reverse **stage paths reach one primitive native source family** (e.g., `176400→192000→96000`, 160/147 followed by /2). The original unique-path check rejects this rather than guessing coherent regrouping. This project does **not** misclassify that structural refusal as a numerical timeout or weaken the check. A future exact source-family regrouping with the actual phase conventions is a separate proof obligation.
- A 60-second `OPEN` is not a spectral violation; returning `OPEN` can reflect a costly but valid bound computation, loose Taylor/L1 majorants, an insufficient node budget or a true unproved condition. Physical sampled evidence cannot resolve that distinction. The new method accelerates numerical evaluation, but does not invent a FAIL witness.
- Current certified local intervals do **not** imply spectral certification of other intervals, the 72-cell matrix, arbitrary-input FFT4G roundoff, physical DSD256 matched-comparator performance, or P15 release. v2 default promotion and P16 authorization remain blocked.

## 8. Integration judgment

This intentionally avoids a new FFT, an MPFR dependency, a custom runtime coefficient format, changes to source bindings, speculative phase-aware cross-family symbolic expressions, and a rewrite of the bounded dispatcher. Measured real-FIR hotspots dominate, and the source-proven coefficient parity admits a much smaller mathematically exact reduction. The general complex reference is deliberately retained for non-even polynomials and independent verification.
