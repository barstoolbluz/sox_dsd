# P15 third pass — exact finite-difference FIR upper bounds

Date: October 18, 2026. Scope: **ideal, captured-binary64-coefficient local continuum spectral proof**, not production runtime or release approval. P15 remains **BLOCKED**.

## Assessed and discarded option

The initial attempt reduced the number of Taylor derivatives for narrow frequency intervals using the exact moment bound `M_(n+1) (2 pi r)^(n+1) / (n+1)!`. Although each selected order was rigorously enclosed, the first 1e-12 internal accuracy target could cause excessive proof-tree work; a 1e-18 target yielded negligible complete-prover improvement. That experiment is **not in the delivered numerical implementation**. Its raw experimental files are separated under `exploratory_adaptive_trials/`; the delivered `p15_src_interval_recurrence.py` is byte-identical to the second-pass source.

## New theorem and executable construction

Let the source-witness FIR be the finite Laurent polynomial

    H(z) = sum_{k=a}^{b} c_k z^k,         c_k exact binary64 rationals,

where all missing intermediate tap positions are zero and `|z|=1`. For each integer `p>=1`, construct the finite-difference coefficients

    D_p(z) = (1-z)^p H(z) = sum_k d_(p,k) z^k.

The coefficient recurrence is `d_(p+1,k) = d_(p,k) - d_(p,k-1)`, with the finite polynomial **zero-extended at BOTH boundaries**. Therefore

    |H(exp(2 pi i x))| * |1-exp(2 pi i x)|^p
       = |D_p(exp(2 pi i x))| <= sum_k |d_(p,k)|.

For any rational interval `[u,v]` with `0<u<=v<=1/2`, the function `2 sin(pi x)` is increasing. Thus, **for every real frequency x in the entire interval**,

    |H(exp(2 pi i x))| <= B_p(u)
       = (sum_k |d_(p,k)|) / (2 sin(pi u))^p.

Take the minimum of rigorously outward-rounded `B_p` for `p` in `{2,4,6}`. Each is independently a global upper; their pointwise minimum is also an upper. This uses no sampled-frequency inference, phase cancellation, RMS bound, cutoff or omitted alias.

### Exact source-coefficient identity

`p15_src_difference_upper.py` calls `float.as_integer_ratio()` for each finite binary64 coefficient, selects their common power-of-two denominator, and computes the full, zero-padded finite differences entirely with arbitrary-precision **integers**. It accumulates the exact absolute integer coefficient sum and creates its exact rational value. It does not discard small coefficients, truncate support, or sum binary64 values. Sparse positions are padded with zeros; pathologically enormous sparse spans fail back to the pre-existing evaluator rather than admit an approximate result. A rational time-origin shift multiplies the FIR transfer by a unit-modulus phase and does not alter the majorant.

The denominator is evaluated using the existing 75-decimal-digit, directed `mpmath.iv` sine and pi enclosures at the EXACT rational lower endpoint `u`, using the lower endpoint of `2 sin(pi u)`. The coefficient-sum quotient is rounded outward and its UPPER endpoint retained. An interval touching zero, an invalid normalized frequency, or a numerically unusable denominator declines the shortcut. The tool's rigorous transcendental enclosure claim remains conditional on the trusted directed implementation of `mpmath.iv`; the regression tests are not offered as a replacement for that assumption.

### How the bound is integrated

`cheap_alias_upper(stage, shift, lo, hi)` first maps the same exact source-bound high-rate shift as the existing `bounds_single` onto `[0, 1/2]` normalized cycles. It divides the resulting finite-difference upper by the exact stage interpolation gain `L`. **Only** when this conservative normalized upper is strictly below the internal `1e-10` threshold does the expensive Taylor upper evaluator get bypassed. Otherwise the existing second-pass Taylor evaluator is used unchanged. `1e-10` is a performance/quality heuristic on an INDIVIDUAL stage bound, **not a new spectral tolerance**. Any returned finite-difference bound is counted without omission in the pre-existing hierarchical, path-complete triangle-inequality alias population proof. The full direct wanted branch continues to use the two-sided Taylor bounds; the finite-difference method never supplies a needed lower bound.

An insufficient global bound can only cause more subdivisions or `OPEN`; it cannot cause an incorrect PASS because the entire magnitude contribution remains upper-bounded. The nested stage/branch population, collision-path accounting, exact rational branch-boundary splits, source operator hashes, and the strict normative `0.0001 dB` passband and `-160 dB` alias checks remain intact. The tool counts the number of cheap stage majorants actually used in each result.

### Accuracy and efficiency conditions

A finite-difference majorant may be much looser than the strict Taylor result. In the representative source 4,160-tap FIR at normalized frequency `2/5`, its conservative, global bound was nevertheless below the internal shortcut threshold. Its measured warm bound calculation is substantially cheaper than the strict local Taylor enclosure. This is not a production audio processing improvement. For FIRs whose high-frequency difference bound is uninformative, the previous implementation is retained as a fallback; no source taps or runtime filters change.

## Independent tests, source binding, and limitations

- Exact integer finite differences checked independently against binomial-convolution coefficients, including negative indices, missing zero taps, nonzero phase center and cancellation.
- The source 4,160-tap stage is checked against the retained strict Taylor result at a high-frequency image, including the expected fallback near zero.
- Synthetic adversarial envelopes near zero, Nyquist, and on signed asymmetric source taps are checked against independently evaluated high-precision complex point enclosures. These checks test implementation but **do not** establish the continuum result; the exact polynomial identity and monotone sine inequality establish that result.
- Previously established independent complex interval evaluator, exact alias-path tests, coefficient source identities and bound-population tests remain in the regression suite.
- Every final local receipt includes the captured operator snapshot SHA-256, operator binding SHA-256, normative design SHA-256, 35 pinned source identities, and hashes of eight numerical prover modules. Receipt publication is exclusive and idempotent.
- A separate zero-loss audit has reverified the 11,516 original complete-campaign receipts, 5,112 older partial receipts, 48 extended-budget samples and all 35 pinned source paths: **16,711 byte-identical files**.

**Not proved:** the remaining canonical full campaign, arbitrary-input FFT4G execution roundoff, complete source generator-equivalence obligations beyond existing bindings, or the P/S-matched DSD256 physical comparison. No authorization to promote v2 defaults, declare P15 complete, or begin P16 follows from these local results.
