# P15 high-rate continuous-frequency certification: mathematical methods

**Date:** October 18, 2026. **Scope:** the stationary composite operator formed from the exact captured binary64 FIR coefficients. **Release disposition:** P15 remains **BLOCKED** until its separate applicable obligations are discharged.

This document specifies two measured improvements to the third-pass prover: a certified complete halfband-pair norm for hierarchical alias bounds, and an early return when fully evaluated terminal upper bounds already force frequency subdivision. It also records exact-word cache and policy-endpoint corrections and the numerical-library assumptions. None changes production audio code, filter coefficients, normative bands, alias membership, or release policy. The evidence paths below are relative to this document's directory.

## 1. Operator, frequency population, and acceptance inequalities

An SRC stage with input clock \(F\), interpolation factor \(L\), decimation factor \(M\), and signed-index FIR coefficients \(g_k\) has normalized response

\[
G(x)=\frac1L\sum_k g_k e^{2\pi i kx},\qquad
x=\frac{f+\delta}{LF}.
\]

The stage constructor preserves the source-derived centered halfband indexing, overlap/save post-peak origin, rational-polyphase preload, and exact clock mapping. The inverse-stage population contains every one of the \(M\) branches, with high-rate arguments separated by the output clock. Folding to the preceding input clock uses exact rational arithmetic. Complete paths retain their signed frequency shifts and every stage factor. These are inherited constructions in `p15_src_bound_operator.py`, `p15_src_stagewise_alias_proof.py`, and `p15_src_stagewise_continuum.py`; the new methods do not reinterpret them.

Different reverse paths can feed the same primitive native source-frequency family. Their physical contribution is coherent. If \(T_p(f)\) is a path transfer, the triangle inequality gives

\[
\left|\sum_{p\in\mathcal F}T_p(f)\right|
\leq\sum_{p\in\mathcal F}|T_p(f)|.
\]

Every path remains in the right-hand sum, including repeated source families. The lattice checker verifies the represented exact native-frequency lattice separately from path count. No RMS estimate, small-path cutoff, or deduplication is permitted.

For a passband segment, let \([D_-,D_+]\) enclose the unique direct path magnitude and let \(A\) bound every other path's magnitude sum. The conservative complete transfer enclosure is \([\max(0,D_- - A),D_+ + A]\). The normative mathematical requirements are the unchanged \(0.0001\) dB envelope and \(160\) dB coherent-alias suppression, with amplitude limits \(p_\pm=10^{\pm0.0001/20}\) and \(a=10^{-8}\). Native-source stop mode instead bounds the sum of all paths whose native source frequency can reach or exceed the profile's specified stop boundary \(S\).

Exact rational alias transitions are split before a stationary schedule is reused. Analytic one-sided limits cover shared routing endpoints; zero-width points retain their own endpoint checks. A source-stop family touching or crossing \(S\) is conservatively included for the whole segment. This may overestimate below-\(S\) contributions but cannot omit a required source. The new subtree bounds preserve that rule. A cell is complete only when successful source-bound receipts exhaust its canonical intervals; a local result cannot establish missing coverage.

## 2. Exact halfband-pair theorem

The shortcut admits only \(L=1\), \(M=2\), an exact 2:1 clock relation, unique integer tap indices, finite binary64 coefficients, central coefficient exactly \(1/2\), exact reflected symmetry of every nonzero coefficient, and exclusively odd nonzero support away from the center. Approximate symmetry is insufficient. Exact zero taps, including signed zeros, do not alter the polynomial.

Write

\[
H(x)=\tfrac12+Q(x).
\]

Reflected real coefficients make \(Q\) real; odd support gives \(Q(x+1/2)=-Q(x)\). Thus the two complete inverse-decimation branches obey the exact identity

\[
|H(x)|+|H(x+1/2)|
=|\tfrac12+Q(x)|+|\tfrac12-Q(x)|
=2\max(\tfrac12,|Q(x)|).
\]

This holds through sign changes, cancellation, and zeros, including \(|Q|>1/2\). It is an identity for the **sum of magnitudes**, not a cancellation assumption between different source paths.

Periodicity, evenness, and antiperiodicity imply \(\sup_{x\in\mathbb R}|Q(x)|=\sup_{x\in[0,1/4]}|Q(x)|\): reflection maps negative arguments to positive ones, and \(|Q(1/2-x)|=|Q(x)|\) folds the remaining half-period. Therefore a uniform enclosure \(|Q|\leq B\) on that closed quarter-cycle proves the global pair bound

\[
C=\max(1,2B).
\]

## 3. Constructing the global continuous enclosure

`p15_src_halfband_majorant.py` covers the entire reduced interval with the existing directed Taylor evaluator. It starts at \([0,1/4]\), accepts a closed subinterval only when its upper endpoint is below the exact rational internal target \(50000001/100000000\), and otherwise bisects at the exact midpoint. Returning a bound requires an empty pending list. Accepted children include their endpoints; no sampled grid or omitted boundary supplies the proof.

The final \(B\) is the maximum of the actual accepted upper endpoints, not the target. Computing \(\max(1,2B)\) retains outward endpoints. Pattern failure, insufficient precision, excessive tap count, or exhaustion of the 256-node construction budget returns `None`; the previous L1 bound remains available. The target is a cost guard for a reusable majorant, not a relaxation of spectral acceptance.

The captured native halfband has **57 taps, including 28 exact zero coefficients**. Its exact coefficient-word SHA-256 is

```text
96456acec595a7936bbafbb1173d77d6293839c4b1b63a56089c041c9a4d2f7f
```

The retained proof examined **55 nodes** and produced **28 closed intervals** covering \([0,1/4]\), with outward diagnostic pair upper **1.0000000077254763**. Its recorded construction time after stage loading was **0.062666953 seconds**. Five such levels have upper **1.0000000386273817**, compared with **248.07333464780757** from five factors of the previous two-branch L1 bound. These are bound improvements, not equivalent runtime speedups. Exact endpoint words, the complete cover, source hashes, and original implementation hashes are in [HALFBAND_MAJORANT.json](mathematics/HALFBAND_MAJORANT.json).

## 4. Complete-subtree theorem and admissibility

Let \(\ell_j=L_j^{-1}\sum_k|g_{j,k}|\), computed as an exact rational from binary64 words before outward conversion. At stage \(j\), use \(C_j\) when a complete halfband pair has been certified; otherwise use \(M_j\ell_j\). If these uniform complete-branch bounds are \(K_j\), then

\[
\sum_{p\text{ below a node}}\prod_{j=d}^{n}|G_{p,j}(f)|
\leq\prod_{j=d}^{n}K_j.
\]

Proof is induction on remaining depth. A leaf has bound one. At a preceding level, each child remainder is bounded uniformly by the same product; factor that product out of the sum and apply the complete one-stage bound. This argument permits branch frequencies and upstream subtrees to depend on the selected downstream branch.

A selected subset, such as unwanted paths or source-stop paths, also satisfies the complete bound because all magnitude products are nonnegative. The implementation takes the minimum of this valid bound and the existing selected-path-count times L1 bound. At an evaluated node the remaining product begins at the next stage. At an unevaluated node one particular current branch contributes its individual L1 factor, followed by the complete bound for later stages. Confusing these positions would give the wrong population factor.

The trie independently checks that no node has more than \(M\) children, every complete leaf has multiplicity one, and every two-child recognized halfband has shifts differing by exactly half its input clock modulo that clock. Failure disables the complete-subtree shortcut for that population and preserves the previous multiplicity-aware bound. In particular, duplicated complete paths do not silently acquire a single-path cap; distinct complete paths ending in the same native family remain represented.

No phase-aware summation was needed. The exact complement relation controls two magnitudes inside one admitted stage. The hierarchy still applies the triangle inequality across paths, valid for arbitrary relative phases. Source origins and rational mappings remain unchanged.

## 5. Terminal upper saturation

The frontier's directed interval `total` encloses the sum of upper endpoints for all active subtrees plus all finalized terminals. Each heap entry represents a disjoint selected path subset. Replacing an entry subtracts its exact stored endpoint and adds valid replacement bounds using outward arithmetic; therefore `total.b` remains a valid upper for the complete selected population.

The added accumulator \(F\) contains the sum of immutable fully evaluated terminal upper endpoints. Once \(F.a\geq\mathrm{limit}.b\), refining other nonnegative frontier entries cannot remove those fixed endpoints. Returning the current `total.b` lets the unchanged caller subdivide the frequency interval immediately. Every still-unexpanded contribution remains in `total`.

Crucially, \(F.a\) is a lower enclosure for the **sum of computed upper endpoints**, not a lower bound on actual transfer amplitudes. It cannot establish a spectral violation. Early return can produce a loose upper and preserves OPEN/subdivision behavior. Using the directed lower endpoint of \(F\), rather than a floating sum or the cancellation-widened `total`, can only delay the criterion through rounding uncertainty. `use_terminal_saturation=False` retains the previous full-refinement reference.

The measured obstruction was canonical job 596: DSD64 mastering to 384 kHz, 19–20 kHz passband. On its 19–19.2 kHz segment, one finalized path upper was **2.5198099933317692e-8**; the old population refinement still evaluated all 4,703 unwanted paths before returning **2.6924517427255564e-8**. Both 100 Hz children passed. The dominant factor was a loose first-2x-SRC FIR interval upper; no permanent finite-difference floor or true violation was established. See the [instrumented diagnostic](diagnostics/master64_19000_19200_instrumented.json).

The whole canonical interval passed under both methods:

| Frozen version | Allowed seconds | Wall seconds | FIR evaluations | Frontier expansions |
|---|---:|---:|---:|---:|
| First high-rate candidate | 180 | 119.957889 | 39,576 | 77,990 |
| Final candidate2 v2b | 60 | 54.872389 | 2,624 | 3,466 |

Both have exactly 15 nodes, three rational routing splits, four ordinary subdivisions, eight certified subintervals, and identical final enclosures. The final maximum alias upper is **9.998018426093185e-9**. This is a measured individual-case improvement; allowed budgets differ. [JOB596_COMPARISON.json](diagnostics/terminal_saturation_candidate_v2b/JOB596_COMPARISON.json) retains timings, CPU, memory, identities, and equality checks.

## 6. Exact-word cache identity

The first helper cached tuples of Python floats. Python equality conflates signed zeros and can equate floats with non-float numbers. Consequently an adversarial cache hit could return another zero-sign variant's coefficient hash or bypass the exact-float admission check. The [saved reproducer](diagnostics/terminal_saturation_candidate_v2b/CACHE_IDENTITY_REPRODUCER_PRE_FIX.json) establishes both defects.

The corrected entry validates taps before lookup and uses sorted `(integer index, float.hex())` words plus interval precision as its key. A miss reconstructs the exact float words and performs the same global proof. Different zero signs retain distinct identities; order permutations and matching source clocks reuse the normalized proof appropriately. Existing source runs consistently used the same words and types, so their mathematical bounds are unaffected. Different implementation versions still retain separate code hashes and replay snapshots.

## 7. Directed rounding and the trusted boundary

Binary64 coefficients are exact dyadic inputs, decoded with `as_integer_ratio` or `Fraction.from_float`. Frequencies, transitions, indices, coefficient moments, and derivative weights use exact integers and rationals. The inherited symmetric evaluator uses a 288-bit dyadic grid with integer floor/ceiling rules for interval products and Taylor remainders. Transcendental anchors use `mpmath.iv` at 75 decimal digits and are widened when converted to that grid. General complex fallback, norm products, scalar conversions, and comparison thresholds also depend on interval arithmetic. Printed binary64 enclosure summaries are diagnostic outward conversions; the proof calculations use multiprecision endpoints.

The correctness of **mpmath 1.3.0 interval arithmetic, including `iv.sin`, `iv.cos`, and `iv.pi`, is an inherited library assumption**. The official documentation describes interval support as experimental and notes incomplete function support: [current documentation](https://mpmath.org/doc/current/contexts.html), independently consulted [version 1.3.0 documentation](https://mpmath.readthedocs.io/en/1.3.0/contexts.html). Exact integer recurrences do not remove reliance on their transcendental anchors. Testing does not prove that library assumption or establish IEEE 1788 conformance.

### Corrected policy-endpoint representation

The audit identified an inherited third-pass defect: `db_band` rounded acceptance endpoints outward as though they were diagnostic enclosures. This widened the mathematical interval by about **2.0182e-16** at its lower edge and **4.9055e-17** at its upper edge. The original module hash and measured displacements are in [NORMATIVE_LIMIT_ROUNDING_AUDIT.json](diagnostics/NORMATIVE_LIMIT_ROUNDING_AUDIT.json). Two adversarial binary64 FIRs demonstrate actual false PASS decisions under those thresholds; these are synthetic implementation counterexamples, not violations by a production filter.

Candidate3 preserves the complete directed intervals for both exact policy limits. If \(p_-\in[l_-,l_+]\) and \(p_+\in[u_-,u_+]\), PASS requires the transfer lower bound above \(l_+\) and its upper bound below \(u_-\). A center-witness FAIL requires its entire enclosure below \(l_-\) or above \(u_+\). Ambiguous overlap remains OPEN. Keeping only the inward endpoints could introduce false FAIL decisions for legal values in the numerical uncertainty gap; both endpoints are therefore essential.

The existing string API is retained without display rounding. Each finite endpoint \(m2^{-k}\) is serialized as the exact decimal integer \(m5^k\) divided by \(10^k\); nonnegative binary exponents are exact integers. The two exact decimal endpoints form an interval string. Parsing it preserves an enclosure at the receiving precision. No comparison logic or tolerance changes.

Independent tests construct rational bounds from \(\ln10=3\ln2+\ln(5/4)\). For \(t=(x-1)/(x+1)\geq0\), the first \(N\) terms of \(2\sum t^{2j+1}/(2j+1)\) have positive remainder at most \(2t^{2N+1}/((2N+1)(1-t^2))\). Ninety terms bound each logarithm. A degree-32 positive exponential Taylor expansion uses a geometric remainder, since subsequent term ratios are at most \(z/(N+2)<1\). These rational calculations verify containment of the particular policy intervals without mpmath transcendental calls. Legal neighboring FIRs still PASS; former false-PASS examples now FAIL; values or enclosures within policy uncertainty remain OPEN. Exact examples and endpoint words are in [THRESHOLD_CORRECTION_VALIDATION.json](diagnostics/normative_limit_candidate3/THRESHOLD_CORRECTION_VALIDATION.json).

Previously issued receipts require independent comparison of their outward amplitude summaries against the exact normative limits. A bound strictly inside those limits remains sufficient; no historical receipt is rewritten or automatically upgraded. The correction changes proof-code identity, while all 35 operator-pinned source files remain byte-identical.

## 8. Independent checks, identities, and scope

The frozen v2b focused suite passed **41 tests**. The entire 28-interval source cover is re-evaluated with the slower direct complex Taylor algorithm, using direct trigonometric evaluation of original taps rather than the symmetric dyadic recurrence. This is an independent continuous-frequency calculation, although it shares the interval-library trust boundary. Additional all-tap complex point tests exercise DC, Nyquist, quarter-cycle, exact rational boundaries and one-sided offsets, cancellation, and zero responses; those point tests do not replace the interval cover.

Adversarial tests reject tiny nonzero even taps, one-ULP symmetry or center changes, malformed sibling shifts, duplicate leaves, excessive branching, partial global covers, and equal-valued non-float cache inputs. Terminal tests retain every unevaluated contribution, compare disabled-optimization behavior, verify child certification after a loose parent, and exercise exact threshold accumulation despite large subtraction cancellation. The [focused log](diagnostics/terminal_saturation_candidate_v2b/FOCUSED_TESTS.log) and test sources are retained.

The expanded candidate3 focused suite passed **48 tests**, adding six policy-rounding tests and the corrected legacy multiplicity regression. That regression retains its exhaustive reference with at least two stage evaluations and separately checks that early return still bounds all three exact unit contributions. It no longer requires unnecessary evaluation work from the optimized path. The [expanded log](diagnostics/normative_limit_candidate3/EXPANDED_FOCUSED_TESTS.log) records the result; initial test-construction and broader regression failures are preserved with explanations rather than overwritten.

A final independent population-test review explicitly disabled terminal saturation in the exhaustive comparison, required every trie edge to be evaluated, and compared the returned upper against the exact rational sum of products of independently calculated direct-complex upper endpoints. All eight population tests passed; the [supplemental record](testing/population_full_expansion_2026-10-18/RESULT.json) preserves the former test, correction, unchanged proof hashes, and log.

Source binding includes the normative-design digest, production and native-coefficient source hashes, historical coefficient manifests and worklists, stage snapshot, exporter-derived clock/origin metadata, and verified operator-binding digest. Snapshot loading refuses unreviewed stage configurations. Its independent FFT packed-bin check is a gross preparation-identity check, not an FFT4G error proof. Proof-code identity is separate from source identity: the [v2b import-map snapshot](reference_high_rate_v2_code/IDENTITY.json) contains all 15 recorded module hashes, and [candidate3 source identities](diagnostics/normative_limit_candidate3/SOURCE_IDENTITIES.json) specify the subsequent policy correction. The final continuum module hash is `2656e0fafac58a6d4cffd19002f6ff22d5a851f4e730afd9ab6e70c684f7f1b5`. Historical v1, v2a, and v2b code and receipts remain available for exact replay.

These methods establish local inequalities for the stationary ideal coefficient operator, conditional on the stated arithmetic assumptions and source bindings. They do not bound arbitrary-input FFT4G execution roundoff, qualify finite startup/drain arithmetic, adjudicate physical-comparator measurements, close separate v2 metrology obligations, or authorize release, v2 promotion, or P16. Whole-cell coverage is an additional exhaustive accounting claim made only from its actual canonical receipts.
