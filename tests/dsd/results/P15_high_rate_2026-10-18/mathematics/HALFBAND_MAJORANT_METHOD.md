# Exact halfband alias-pair and subtree majorants

Date: October 18, 2026. Scope: the ideal, stationary, captured-binary64-coefficient transfer operator. P15 remains **BLOCKED** pending its other spectral and execution obligations.

## Measured obstruction and selected correction

The third-pass hierarchy starts an unevaluated subtree with its path count multiplied by the exact FIR L1 gains of all remaining stages. This is a valid bound, but it is particularly conservative for the four or five repeated native halfbands in the high-rate cells. Each source halfband has an exact L1 gain near 1.5062117154; its two inverse-decimation branches consequently receive an initial bound near 3.0124234308. Five such levels contribute a bound of 248.07333465 before the profile filter is considered.

The correction supplies a uniform upper for the **sum of both branch magnitudes**, using an exact identity of the captured coefficients. It does not infer coherent phase cancellation. It does not change the audio filters, acceptance bands, or the complete path population.

The source halfband's new globally certified pair bound is less than 1.0000000077254763. Five levels therefore contribute less than 1.0000000386273817. These numbers compare mathematical upper bounds. They are not a claim of a 248-fold runtime improvement; complete-prover measurements are reported separately.

## Exact algebraic construction

Let the normalized FIR response be

\[
H(x)=\sum_k h_k e^{2\pi i kx}.
\]

The new recognizer admits only a stage with interpolation factor 1, decimation factor 2, output clock exactly half the input clock, and the following exact binary64 coefficient properties:

1. The central coefficient is exactly one half.
2. Every other nonzero coefficient has an odd integer index.
3. Every nonzero coefficient has an exactly equal coefficient at its reflected index.
4. All coefficients are finite binary64 values and indices are unique.

Unpaired zero taps, including signed zeros, do not change the polynomial. No approximate equality or tolerance is used to recognize the identity.

Remove only the exact central coefficient and define

\[
Q(x)=H(x)-\tfrac12.
\]

Even coefficient symmetry makes Q real. Odd support gives the exact antiperiodicity relation

\[
Q(x+\tfrac12)=-Q(x).
\]

The complete inverse-decimation pair consists of frequencies separated by one half of the stage input clock. Its magnitude sum is therefore

\[
|H(x)|+|H(x+\tfrac12)|
=|\tfrac12+Q(x)|+|\tfrac12-Q(x)|
=2\max(\tfrac12,|Q(x)|).
\]

The last identity holds for any real Q, including negative responses, stopband sign changes and values outside the nominal passband. In particular, it bounds the sum of magnitudes even when two source paths could interfere coherently. No cross-path phase assumption is involved.

Periodicity, reflection symmetry and antiperiodicity imply that the maximum of |Q| over the full unit circle equals its maximum on the closed interval [0, 1/4]. If B is a uniform upper on that entire interval, the complete pair norm is bounded by

\[
C=\max(1,2B).
\]

## Continuous-frequency construction and rounding

The implementation reuses the existing strict `fixed_symmetric_magnitude_bounds` evaluator on the odd polynomial Q. Starting with [0, 1/4], it accepts a closed subinterval only when its directed upper is strictly below the internal target 0.50000001. Otherwise it bisects at the exact rational midpoint. A maximum of 256 examined nodes bounds this work. Returning a norm requires the pending list to be empty, so the accepted intervals cover the complete reduced domain, without gaps or omitted boundary points.

The returned B is the maximum of the actual directed upper endpoints from those accepted intervals; it is not the target value. The multiplication by two and maximum with one retain directed endpoints. The underlying evaluator uses exact binary64 coefficient ratios and exact integer operations on a 288-bit dyadic grid, with a Taylor remainder derived from the exact absolute coefficient moment. Its trigonometric anchors are directed `mpmath.iv` enclosures at at least 75 decimal digits.

The mathematical argument is conditional on the directed trigonometric enclosure implementation. The tests exercise that assumption and the implementation, but do not replace it with a sampling argument. Output binary64 numbers in the JSON evidence are diagnostics rounded outwards; the population proof uses the actual multiprecision endpoint.

If the pattern is absent, the coefficient count is too large, the requested precision is below 75 digits, or the global proof does not finish within the node budget, the helper returns `None`. The existing FIR L1 majorant remains available. The internal 0.50000001 target is a performance guard for this reusable bound, not a new spectral acceptance tolerance. The passband remains 0.0001 dB and the complete coherent-alias bound remains 1e-8 in amplitude.

The cache key contains the complete exact tap tuple and interval precision. Source stages at different clocks can reuse the normalized proof only when their coefficients and indexing match exactly. No nominal bank name is used as a substitute for the coefficient identity.

## Application to a complete or selected branch subtree

For a stage with a certified pair norm use C as its complete one-stage magnitude-sum upper. For any other stage retain the conservative complete-branch upper M times its exact FIR L1 gain, where M is the number of inverse-stage branches. A product of these per-stage complete upper bounds encloses the sum of all complete path-product magnitudes below a node, by induction over the finite branch tree.

The bound also covers a selected subset, such as all unwanted paths or the paths whose native source lies beyond the normative stopband boundary: dropping nonnegative terms from the sum cannot increase it. It is therefore valid to take the smaller of the new complete-subtree upper and the original path-count-times-L1 upper.

At an already evaluated node, the complete-subtree upper starts at the next stage. At an unevaluated node, the current node represents one particular branch, so its individual FIR L1 upper multiplies the complete-subtree upper of the later stages. This distinction avoids multiplying a selected branch by an unrelated normalized response.

The integration checks structural preconditions independently of normal source-path construction: no duplicated complete leaf; no node with more than M children; and, for every recognized halfband with two children, their shifts differ by half the stage input clock modulo that clock. If these conditions are not met, the previous bound is used. Arbitrary synthetic path tuples therefore cannot silently receive an unearned complete-pair cap.

## Actual source proof and independent checks

`HALFBAND_MAJORANT.json` contains the exact coefficient SHA-256, multiprecision endpoint words, all 28 closed intervals covering [0, 1/4], the 55-node count, the implementation and source hashes, and the recorded proof time. The recorded isolated proof took 0.062667 seconds after the source stage had been loaded. Other exploratory repetitions were around 0.04 seconds; only the recorded value is a retained measurement.

`test_p15_high_rate_independent.py` checks the following:

- Every interval of the source global cover is independently re-evaluated with the slower direct complex Taylor implementation, which uses a direct trigonometric call for each original tap rather than the symmetric dyadic recurrence.
- Direct all-tap complex enclosures check the complete pair at DC, Nyquist, a quarter-cycle, exact rational frequencies, and one-sided offsets as small as 1e-20 cycles.
- Exact pattern recognition refuses even a 1e-300 even-index coefficient, a one-ULP asymmetry, a one-ULP central-coefficient change, wrong stage rates and duplicate indices.
- A valid-pattern synthetic filter with a genuine pair norm above the internal target declines the shortcut.
- A cancellation example with sparse and signed zero taps is handled without a phase assumption.
- An incomplete one-node frequency cover returns no norm.
- Two complete inverse-decimation levels retain all four source branches and obey the product bound.

The source full-cover reference test is a second continuous-frequency calculation. The additional point tests are adversarial implementation checks; they do not establish the continuum result on their own.

## Dependencies and limitations

This method depends only on the exact captured halfband coefficient pattern and the existing directed FIR enclosure engine. The full local certificate separately retains the source identity, captured operator binding, normative-design hash and complete alias schedule. Historical pinned source and receipts remain unchanged.

The method does not certify arbitrary-input FFT4G execution rounding, the finite-start/drain production arithmetic, a physical-comparator release decision, all P15 cells, or any new acceptance band. It supplies a tighter valid upper to the same complete ideal-operator spectral inequality. Whole-cell coverage requires every applicable canonical interval to have its own verified successful receipt or an equivalently exhaustive interval cover.
