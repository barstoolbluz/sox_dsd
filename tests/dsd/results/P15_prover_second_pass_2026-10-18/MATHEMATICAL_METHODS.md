# P15 rigorous continuum prover: second-pass mathematical changes

**Date:** 2026-10-18. **Status:** proof-of-ideal-captured-coefficient local intervals only, P15 BLOCKED.

This is an implementation record, not a complete proof of source coefficient generation, FFT4G runtime arithmetic, all-band SRC performance, or physical DSD256 comparisons. It extends the first-pass methods in `../P15_prover_optimization_2026-10-18/MATHEMATICAL_METHODS.md` without changing any acceptance tolerance, filter coefficient, runtime DSP source, or pinned source path.

## 1. Exact complete reverse-path population when source families collide

An earlier guard required a bijection from all reverse stage paths to the native source-frequency lattice. That is false for some factorized, source-bound SRC operators. For example, the 88,200 -> 96,000 -> 48,000 route has 9,408 complete reverse paths but only 4,704 distinct primitive source-frequency families. The 176,400 -> 192,000 -> 96,000 route has the same 2-to-1 multiplicity; a DSD256 case has 18,816 paths and 9,408 distinct primitive families. The duplicated paths cannot be silently dropped: they represent contributions from different intermediate branches of the actual cascade.

The second-pass `complete_paths` retains every reverse path. Each path is constructed from **all** inverse branches for every source-bound native and SRC stage using rational clocks, exact half-open Nyquist conventions, exact midpoint branch selection, and exact rational splitting at a schedule transition. At each stationary interval, let `F_native` be the native clock, `Fout` the final output clock, `U` the exact source-bound output period, and `delta=Fout/U`. At the exact rational interior midpoint `m`, independently compute

    lower = ceil((-F_native/2 - m) / delta)
    upper = ceil(( F_native/2 - m) / delta) - 1.

For physically clock-consistent native stages, each completed path's exact native offset must be `s*delta` for an integer `s` between these limits. The set of path offsets must cover **every integer** in this entire range. Multiplicity is permitted; omissions and out-of-lattice paths are refused. The stage source clock is required to equal the native clock for collision admission. A narrow compatibility path for earlier artificial synthetic fixtures that have deliberately inconsistent fake native clocks continues to require the prior one-path-per-family condition; it cannot admit a collision.

The direct marked path must be unique in passband mode. All other complete paths, INCLUDING paths from the same primitive source family as the direct one, enter the conservative unwanted upper majorant. For each source frequency `s`, the true cascade transfer is the coherent sum of its paths `A_p` (with possible complex time origins). For exact inputs and every continuous frequency in a stationary interval:

    |sum_{p in family s} A_p| <= sum_{p in family s} |A_p|.

Consequently, the sum of absolute bounds over **all** non-direct paths is a valid upper for every unwanted harmonic (and potentially an overestimate when other paths hit the wanted family). The main-path lower and combined upper use

    |A_direct + sum_{p != direct} A_p| >= |A_direct| - sum_{p != direct} |A_p|
    |A_direct + sum_{p != direct} A_p| <= |A_direct| + sum_{p != direct} |A_p|.

The existing hierarchical prefix tree contains a leaf for every completed path and multiplies unevaluated prefixes by their exact descendant **path counts** and source-binary64 FIR absolute L1 upper gains. It therefore remains sound when paths share final native frequencies. No RMS summation, phase-cancellation assumption, numerical alias cutoff, or loss of duplicate branches occurs. A structurally admitted path population is NOT a spectral PASS; actual strict inequalities still must be proved by `certificate`.

The default maximum complete-path count is raised from 12,000 to 20,000, enough for the maximum 18,816 complete paths in the source-bound 72-cell population. The limit remains finite, configurable, and fail-closed. The first-pass independent point sampler now accepts multiple paths per family for diagnostics and reports the full path sum rather than falsely rejecting it. A point sample NEVER grants a continuum certificate.

## 2. Exact reusable derivative weights

For an exactly even, finite, real FIR with binary64 source tap values `c_k`, the centered real transfer is

    H(x) = c_0 + 2 sum_{k>0} c_k cos(2*pi*k*x).

Every coefficient is treated as its exact binary64 rational word, not a decimal approximation. Its derivative at any center `x_0` is

    H^(j)(x_0) = sum_{k>0} [2*c_k*k^j] (2*pi)^j cos(2*pi*k*x_0 + j*pi/2),

with an additional `c_0` for `j=0`. The bracketed weights `w_kj = 2*c_k*k^j` are EXACT rationals depending only on the source-verified FIR, not on the interval. `_derivative_weights(poly,order)` computes and caches their integer numerators and positive denominators, using `Fraction.from_float` and integer powers. This changes the order of exact multiplications, not the mathematical polynomial or its coefficient identity.

The existing 288-bit dyadic outward-interval operations compute `cos` and `sin` anchor enclosures from 75-digit directed mpmath intervals, convert their endpoints with integer floor/ceiling, and propagate phase rotations through directed integer interval products. The revision also caches outward dyadic interval powers of `2*pi` for the call. For each derivative, the exact rational weight multiplies the outward-enclosed phase-and-pi product via integer floor/ceiling, preserving inclusion regardless of sign or cancellation. No cached frequency-dependent approximate response replaces a verified enclosure. `even_taps` rejects non-even coefficient witnesses; those use the retained independent full complex reference routine.

The `j`-th Taylor variation is bounded by `sup |H^(j)(x_0)| * r^j/j!`, and the remainder by the exact source-coefficient absolute `(order+1)` moment times `(2*pi*r)^(order+1)/(order+1)!`. Their sums are outward rounded. For any `x` in `[x_0-r,x_0+r]`, Taylor's theorem and the triangle inequality then enclose `H(x)` and hence `|H(x)|`. This is a mathematical containment argument, conditional on the trusted multiprecision directed transcendental enclosures and exact binary64 stage witness; randomized testing is *not* substituted for that argument.

## 3. Deadline and immutable publication correction

The one-shot SIGALRM deadline can be swallowed if an internal layer catches a Python exception. After the initial wall-time limit, the dispatcher now repeats SIGALRM at 50 ms intervals until its handler unwinds. A regression test catches the first expiration and verifies a second is delivered. This preserves the cheap-case single initial timer. It does NOT impose a hard wall-clock kill on an uninterruptible native call; for strictly enforced external wall limits run the existing CLI under an OS process supervisor. The change does not authorize OPEN-to-PASS conversion.

The local-receipt writer now uses exclusive same-filesystem hard-link publication rather than `os.replace`; a concurrent result cannot overwrite an existing receipt. A byte-identical winner is idempotent; conflicting, symlinked, or mismatched prior receipts fail closed. The full campaign already used exclusive hard-link publication and is retained.

## 4. Independent checks, measured effects, limits

The new regression suite tests exact rational derivative identity for every order 0..12, directed signed rational products, 75-digit-independent complex interval point containment across cancellations and near-Nyquist intervals, exact lattice coverage in three physical source-bound SRC routes, preservation of duplicate coherent path contributions, and re-delivered deadlines. The retained earlier tests cover exact rational alias boundaries, one-sided limits, long real source FIR cancellation and multi-alias majorants. Tests establish absence of discovered implementation defects on the tested cases, NOT a universal proof of the reference library's transcendental correctness.

`RESULTS_SUMMARY.json` and `benchmarks/*.json` contain the same-host measured wall times, dispositions, resource high-water and identities. Six warm FIR sizes have 1.50x-1.73x arithmetic acceleration over the supplied first-pass implementation. A paired 40-second, DSD128 mastering -> 384k, 0-1,000 Hz passband replay proved PASS with exactly 835 FIR evaluations under **both** code versions, in 36.37 vs 25.16 seconds respectively. Three new 0-1 Hz factorized local PASS results were independently replayed and published, with pinned operator, stage and normative design hashes. Historical receipts and all 35 pinned sources remain byte-identical.

**Nonclaims:** Neither local passband result proves a whole source-stopband, all 11,516 canonical intervals, operator execution-roundoff, an arbitrary-input FFT4G bound, DSD256 physical comparator equivalence, native coefficient generator equivalence, or a P15 release gate. The 11,516 historical campaign receipts remain 6,835 local PASS, 4,681 OPEN. The optimized full campaign was NOT run. A missed proof remains OPEN, never an invented FAIL or PASS.
