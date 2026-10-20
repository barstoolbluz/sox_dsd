# SoX-NG P15: adversarial audit of the original spectral prover

**Date:** 19 October 2026  
**Source authority:** `sox_ng-P15-adjudicate-cc399928.tar.gz`  
**Source SHA-256:** `d058b3908817e01e937f49e0dfeee7194d847aae74f625043e881d8b8f0e9210`  
**Audit classification:** No demonstrated false-PASS *mathematical prover* defect. The historical receipt *reader* has a reproducible integrity-check omission, addressed by an additive, read-only adjudicator. The complete ideal-operator spectral **proof** gate remains **CONDITIONAL**; pragmatic **engineering acceptance is recommended** at a declared trusted-computational-base level. These are separate decisions.

## 1. Scope and authority

Read `docs/dsd/DSD_DESIGN.md`, especially normative section 8.6.1, and inspected the original source implementations and coefficient bindings. The complete-chain passband requirement is an absolute magnitude error of **0.0001 dB**, with source-stop and unwanted coherent alias upper magnitude **strictly below 1e-8** (-160 dB relative to unity). The effective passband for `adapt` is intersected with `0.475*min(R,Fout)`. Native source-stop band and complete output Nyquist are not reduced by that adaptation. No relaxation is made here.

The independently captured source operator is an ideal infinite stationary FIR/polyphase cascade. This audit does NOT qualify the actual release binary's arbitrary-input FFT4G execution error, finite streaming boundaries, or release ELF identity. Those are separate obligations explicitly required in section 8.6.1.

### Identity, replay and accounting

- Original source archive SHA-256 matches the authority above.
- Cumulative R6-R9 proof add-on: **145/145 existing SHA-256 records verify**; no original production DSP files were changed by this audit.
- Original campaign `p15_full_band_campaign.py --summary-only`: **11,516/11,516** complete; **72** SRC-active cells; 24 distinct captured SRC rate pairs; **0 OPEN/missing**.
- The new `p15_final_receipt_adjudicator.py` compares **all 11,516** on-disk historical receipts byte-for-byte against those in the SHA-verified *original compressed archive*, rechecks canonical identity and reported numerical policy inequalities, and finds **2,850 passband + 8,666 source-stop** reported PASS records with one common method string. Receipt-inventory digest: `b72841ffb59e5016e12db4360458895223f454271e9d4504e74aa6ee39d34e99`.
- **41** relevant original/R9 regression tests executed: OK (2 skipped). **17/17** newly authored focused adversarial tests executed: OK.
- `p15_r9_src_strong.py --prove-all` independently reverified the existing **179 native-domain cover leaves** and **330 stronger whole-stage SRC leaves**, proving **958/958** v2 DSD256 source-stop jobs over eight cells. Independent JSON SHA-256: `4d73a7edbc304bb154ac5fb66cf739e777e0cc5a37a95b49472d6cdd23c6d003`, exactly matching prior R9 QA.

No 11,516-certificate campaign was rerun or extended.

## 2. Obligation A: numerical interval arithmetic

### Inspectable source and argument

- `tests/dsd/p15_src_bound_operator.py:81-94,326-395` and `tests/dsd/p15_src_continuum_bounds.py:31-45,61-90`: captured tap words are parsed with `float.fromhex`, checked for finiteness and topology, and converted to exactly represented Python binary64 floats. `Fraction.from_float` and `float.as_integer_ratio` used by the majorants retain the exact binary64 dyadic rational, including negative values and subnormals.
- `tests/dsd/p15_src_continuum_bounds.py:39-40`: rational endpoints become `iv.mpf(numerator)/iv.mpf(denominator)` with outward endpoint rounding. The checker accepts rational frequencies, not a floating midpoint approximation. Raw dyadic conversions in `p15_src_fixed_interval.py:24-73,99-111` use exact integer floor/ceiling; signed negative endpoints were adversarially tested.
- `tests/dsd/p15_src_interval_recurrence.py:19-80`: for asymmetric FIRs, endpoint intervals enclose each complex Taylor derivative and the global order-(r+1) remainder via `sum |c_k| (2*pi*|k-center|*radius)^(r+1)/(r+1)!`. The complex rotation recurrence reanchors every 48 steps; every rotation is an interval operation. Cancellation does not remove terms from the *remainder*.
- `tests/dsd/p15_src_symmetric_interval.py:21-54` and `p15_src_fixed_interval.py:75-189`: exact coefficient symmetry is checked before real-cosine reduction; the fixed-point engine performs interval additions/multiplications with Python integers and outward dyadic rounding. Its derivative moments are exact rational weighted tap sums, and the global Taylor remainder includes every nonzero symmetric tap. The mathematical derivation is standard Taylor/Lagrange, not empirical spectral sampling.
- `tests/dsd/p15_src_continuum_bounds.py:92-136`: the original direct complex evaluator uses `iv.sqrt(re**2 + im**2)` at the midpoint with outward interval derivative norms. `p15_src_interval_recurrence.py:67-71` uses the same norm inequality. For a nonnegative interval norm, this is conservative; near-zero cancellation can reduce its lower bound but cannot enlarge a false lower bound through cancellation.
- `tests/dsd/p15_src_continuum_bounds.py:237-245` constructs 0.0001 dB thresholds from directed interval `ln`, `exp` and reciprocal operations. `tests/dsd/p15_src_stagewise_continuum.py:333-395` compares **inward threshold endpoints** against **outward FIR endpoints**, not float-rounded display values. The latter are generated only after a PASS decision (`nextafter` toward the appropriate infinity).

### Explicit third-party trusted base

Inspected the installed **mpmath 1.3.0** implementation, not merely its documentation: `mpmath/libmp/libmpi.py` functions `mpi_add`, `mpi_mul`, `mpi_div`, `mpi_pow_int`, `mpi_sqrt`, `mpi_pi`, `mpi_cos_sin`, `mpi_exp`, and `mpi_log`; and `mpmath/libmp/libelefun.py` functions `mpf_cos_sin`, `mod_pi2` and `cos_sin_basecase`. The interval basic operations dispatch to directed `round_floor`/`round_ceiling` endpoint arithmetic. `mpi_sqrt` is monotonic with correctly directed integer-square-root calculations. `mpi_cos_sin` evaluates the quadrant endpoints with working precision, widens results, includes intervening extrema, and returns [-1,1] when the interval spans enough quadrants. The trig evaluator uses variable-precision pi/2 reduction and a series-based sin/cos core, widened by a small error guard before interval rounding.

**Smallest unproved mathematical premise:** the size of that internal transcendental error guard, and all its argument-reduction boundary cases, was not independently proved sufficient for *every* possible production anchor in historical runs. Mpmath's implementation is credible and the relevant source paths are bounded and inspected; this is not an observed underbound. Five selected rational anchors were compared against independent exact-integer R5 trig enclosures; interval comparisons were consistent. Such finite checks corroborate but do **not** establish the universal numerical theorem. Likewise the historical mpmath build/version is not recorded in each receipt. The separate R5-R9 engine proves selected claims without trusting mpmath.iv; it does not retroactively replace every original trig operation.

**Assessment A:** Directed basic arithmetic, exact dyadics and Taylor recurrences have justified source-level enclosures subject to the stated transcendentals trusted-base assumption. No false-PASS counterexample was found. Do not claim formally proved `mpmath.iv` trig correctness from this audit.

## 3. Obligation B: exhaustive alias enumeration

`tests/dsd/p15_src_stagewise_alias_proof.py:43-93` builds real FIR stages from the source-captured SRC and verified native banks. Each rational L/M stage applies the input-high-rate response `G(f)/L`; `rate_half_fir`, FFT convolution, and order-0 polyphase clock ratios are admitted only with matching metadata. Unsupported high-precision clocks and interpolation forms are refused, not approximated.

`tests/dsd/p15_src_stagewise_continuum.py:116-207` performs a reverse-stage enumeration. At one output frequency f, with an inherited shift b, choose exactly the integer indices

`kmin = ceil((-L*Fin/2 - f - b)/Fout)` and
`kmax = ceil((+L*Fin/2 - f - b)/Fout) - 1`.

Since `L*Fin = M*Fout`, this half-open interval always contains **exactly M integers**. A folded upstream argument uses `floor((f+b+k*Fout + Fin/2)/Fin)` to canonicalize the signed Nyquist interval. Both ceiling and floor are evaluated with exact `Fraction` objects; the code detects *all* interior discontinuities of the affine integer quotients, returns the first exact `BranchBoundary` or refuses if an expected discontinuity cannot be located. The campaign splits at each returned rational boundary and re-enumerates. On shared endpoints, one-sided limits and the continuous real FIR response keep the supremum bounds valid. For genuine captured native clocks, the final enumerator compares its represented primitive source shifts against the entire exact lattice, enforcing every member, endpoints and all multiplicities (lines 182-205).

`tests/dsd/p15_src_complete_aliases.py:51-72` independently derives the native source harmonic set and checks its count from `Fout/U`; repeated paths reaching the same harmonic are not deduplicated in the certifier. The admissibility test requires one direct path in passband mode; more than one cannot yield a passband PASS. A tested synthetic two-decimator cascade enumerated all four exact native source shifts, and a falsified period/lattice was refused. An intentionally wrong rational transition or boundary would be detectable in the exact-branch tests.

**Assessment B:** The argument supplies a general branch-completeness invariant for the supported stage forms, not just a midpoint observation. No credible omitted-family or boundary false-PASS mechanism was identified.

## 4. Obligation C: conservative composite recurrence

`tests/dsd/p15_src_stagewise_continuum.py:210-313` bounds the magnitude of a complete reverse path by the product of stage norm intervals, each divided by its interpolation factor L. Its source-stop predicate includes a path if `max(|lo+source_shift|, |hi+source_shift|) >= S`: since the source frequency is affine across the interval, this is the maximum of the convex absolute value, and including a touching/crossing path over the *whole* segment can only overcount.

For passband, if the unique direct-path magnitude lies in `[D_lo,D_hi]`, and `A` is an upper bound on the sum of *all* other complete path magnitudes, the reverse triangle inequality gives

`max(0,D_lo-A) <= |H_wanted| <= D_hi+A`.

A complete source-stop upper is the sum of all path upper products whose primitive source frequency lies in the stop set, including duplicate/coherent paths. No phase cancellation is credited. Distinct paths to an identical source harmonic can only reduce the true coherent magnitude relative to this triangle upper; they can never make it larger.

`tests/dsd/p15_src_branch_bound.py:32-164` computes the path population bound, with L1 majorants for unevaluated stage factors. The recurrence `sum over paths of product |stage response|` is conservative by induction: replacing any subtree by an upper bound for all its descendants maintains the majorant. The whole-stage factors and reported halfband pair bounds are never multiplied without validation of their structural preconditions. The acceptance predicate is strict with the original thresholds (`stagewise_continuum.py:383-386`).

The R9 independent source-stop factorization is compatible with this same recurrence: native global transfer `B_N <= 1.3e-9`; globally certified SRC reverse branch-sum `<= product(B_stage)`; hence the composite stop upper `<= B_N * product(B_stage)`. Its independent replay covers all 958 stated stop jobs. It is **not** evidence of universal passband approval.

**Assessment C:** The algebra and normalization are sound for the admitted ideal stationary FIR/polyphase operator; no demonstrated invalid gain product, incorrect coherent-alias summation or cancellation-based false PASS.

## 5. Obligation D: pruning, caching, conservative shortcuts

- `p15_src_difference_upper.py:22-69`: `||(1-z)^r H|| <= ||Delta^r h||_1` for integer r=2,4,6. On normalized `[lo,hi]` with `0 < lo <= hi <= 1/2`, the denominator `2 sin(pi*lo)` is the smallest possible. Its directed lower endpoint is used, so the resulting high-frequency majorant cannot be below the true `|H|`. A zero lower frequency or unusable poly returns None.
- `p15_src_halfband_majorant.py:48-105,117-135`: only exact even FIRs with central 0.5 and other nonzero taps at odd symmetric indices can use `H(x)=0.5+Q(x)`, `H(x+0.5)=0.5-Q(x)`, giving `|H(x)|+|H(x+0.5)|=2max(0.5,|Q(x)|)`. A full closed `[0,1/4]` directed Taylor cover certifies the Q majorant or the shortcut returns None. Perturbed central/paired coefficients are refused; no approximate matching.
- `p15_src_branch_bound.py:40-73`: full-subtree caps apply only if each trie leaf represents one complete path and any paired M=2 branches have the necessary half-period shift. In all other cases the original descendant-count-times-L1 upper is used. Partial included populations are safe because excluded paths have nonnegative magnitudes.
- `p15_src_branch_bound.py:76-164`: root and descendant counts include duplicates; a ready node's upper can be replaced only by an independently conservative full-branch cap. Frontier totals are maintained via outward interval operations. Replacing an upper with a separately bounded child subdivision preserves the upper by induction. Terminal saturation exits only with a **still conservative upper** above the acceptance threshold; it cannot cause PASS.
- `p15_src_stagewise_continuum.py:105-113,259-281`: cached stage bounds are local to one exact `(lo,hi)` call and keyed by immutable stage/shift terms. The global polynomial and L1 caches use frozen FIR stage identity, including actual tap contents. Halfband caches use all exact hexadecimal tap words plus precision. No stale cross-interval reuse path was found.

Adversarial fixtures exercised multiple counted identical paths, enabled/disabled full subtree caps, terminal saturation, exact coefficient perturbations, and cache separation for one-ULP coefficient changes. Every constructed upper remained conservative; tests are corroboration of the above recurrence, not proof for arbitrary data.

**Assessment D:** No concrete false-pruning, negative-coefficient, stale-cache, undercount or false PASS was found.

## 6. Obligation E: historical integrity and provenance

**Demonstrated:** all historical receipts are present *byte for byte* in the supplied immutable archive with verified SHA-256; their jobs cover the canonical plan, their source/operator/design bindings match this source snapshot, they carry one method label, and every recorded outward diagnostic bound is strictly within the applicable original limit. Source stages and raw coefficient snapshots are additionally verified using `p15_src_capture_matrix.py:29-49` and `p15_src_bound_operator.py:326-395`.

**Reproduced receipt-reader defect:** `p15_full_band_campaign.py:142-169`, used by `summarize`, validates identity/status but does not compare reported upper/lower numerical fields against the limits. A synthetic archived-style receipt with `PASS-LOCAL-STOP-SOURCE` and a *fabricated upper of 0.1* still passes `check_one`. This is a real deficiency in the receipt *reader*, not an identified false PASS emitted by the `certificate` calculation. The original verified archive has not been altered and its 11,516 reported bounds pass the stricter independent consistency checker. The additive `p15_final_receipt_adjudicator.py` rejects the forged receipt and checks immutable archive bytes before asserting historical inventory consistency. Because historical receipts lack full intermediate derivations, this cannot convert them into fully independently recomputed mathematical proofs.

**Not demonstrated:** exact archived execution-process attestation identifying the Python prover-module code hash, `mpmath` wheel/build, interpreter, flags, and execution host for all 56 historical shards; the receipts store a human-readable method label and SHA-bound *production/operator* source list but not a complete SHA-bound proof-runtime closure. Current packaged prover soundness + receipt consistency does not logically imply that exact code/runtime produced each historical bound. Retrospective source archive integrity must not be confused with an impossible retroactive signing of the historical jobs.

**Independent overlap reconciliation:** R9 independently proves **958** DSD256-v2 stop intervals. R7 independently qualifies 87 intervals over two complete source/rate cells; **23** v2 DSD256 stop intervals overlap R9. R8 adds **one** distinct high-rate passband interval. Thus `958+87-23+1 = 1,023` **distinct** independent intervals, including 981 stop and 42 pass, leaving **10,493** original local certificates without complete R6-R9 independent per-interval rederivation. Do not reinterpret the 1,023 as extra campaign results or R9 as proof of other profiles.

**Assessment E:** Historical inventory, byte integrity and bound-value consistency are strong and reproducible. Formal historical execution correspondence is unavailable. This is a provenance gap, not a demonstrated spectral inequality failure.

## 7. Adversarial evidence and limitations

New code: `tests/dsd/test_p15_final_prover_audit.py` (17 tests) and `tests/dsd/p15_final_receipt_adjudicator.py` (read-only). Reproductions cover exact coefficient dyadics, signed/outward dyadic grid rounding, independently cross-checked trig anchors, synthetic odd/negative/symmetric/cancelling taps, FIR normalization, halfband identity rejection on perturbed taps, exact branch transitions, complete/inconsistent source lattices, duplicate harmonic multiplicity, conservativeness under pruning and saturation, distinct coefficient cache keys, a deliberately changed real captured tap word, and forged receipt fields/bounds. No production C source was modified. The 41 existing tests (2 skips) supply additional checks for complete alias handling, source binding, continuum FIR bounds and R9 mathematics.

A finite regression suite cannot establish the universal quality of all transcendental interval arguments. The mathematical source-level recurrence is the central assurance argument. Conversely, absent an actual violation, still more independent per-interval campaigns are not automatically justified.

## 8. Final five-question disposition

1. **Actual numerical false-PASS defect?** **NO demonstrated case.** Identified and reproduced one narrower integrity-check omission in a receipt reader; a read-only independent checker now rejects it. The absence of a numeric counterexample is not a proof of absence.
2. **Historical 11,516 sufficient for defensible engineering spectral acceptance?** **YES, CONDITIONALLY**, under the accepted trusted-base policy of the inspected directed interval backend and the reasonable-but-not-cryptographically-proved correspondence of the packaged prover/method to the historical execution. Historical archive integrity and recorded inequality consistency are now verified rather than presumed.
3. **Mathematically fully qualified certifier, no assumptions?** **NO** in an unconditional/formal sense. The smallest unproved numerical premise is universal outward enclosure of the particular `mpmath.iv` transcendental implementation used at all original Taylor anchors; historical prover-runtime correspondence is a separate provenance premise. Most integer/rational, alias, recurrence and safe-optimization steps have a general correctness argument.
4. **Historical execution?** Source archive and receipts are SHA-bound and mutually byte-identical; proof-runtime execution attestation (code/library version/host) was not retained and cannot be reconstructed from those receipts. No statement about FFT4G release-roundoff is made.
5. **Ideal-operator formal mathematical gate:** **CONDITIONAL**, not OPEN/FAIL. **Engineering acceptance recommendation: YES**, for the historical spectral evidence at an explicitly documented source-audited, computational-interval, independently-corroborated assurance tier. This does not automatically make the full **P15 release** PASS; §8.6.1 also requires final same-operator arithmetic/FFT4G and other release qualification.

## 9. Stop-or-continue decision

**STOP spending substantial engineering resources generating or rederiving additional spectral intervals solely to increase proof count.** This audit found no source-level false-PASS mathematical defect or missing branch population; the existing archive is intact, all original reported inequalities are internally consistent, the significant R6-R9 exact corroboration independently replays, and the remaining questions concern trust in a small third-party transcendental backend and unauthenticated historical execution correspondence. Another 10,493 independent interval jobs would not by itself resolve the trusted-base argument or historical execution provenance.

The only defensible reason to reopen spectral mathematics is a *specific counterexample*, a demonstrated inadequacy of the identified transcendental trusted-base assumption, a changed captured production operator, or an explicit acceptance-policy decision that unconditional exact-rational proof (rather than source-audited interval verification) is mandatory. That is not a current evidence-driven request for a new campaign.

**Recommendation:** document and approve this engineering assurance tier once, then redirect work to the distinct release-execution obligations. If the authority requires an unconditional formal ideal-operator theorem, keep the mathematical proof label **CONDITIONAL**; do not pretend that the accepted engineering risk is a machine-checkable proof.
