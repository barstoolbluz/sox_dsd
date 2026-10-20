# SoX-NG P15 R6: independent integer/rational composite interval proof

**Date:** 2026-10-19  
**Base:** exact source archive SHA-256 `d058b3908817e01e937f49e0dfeee7194d847aae74f625043e881d8b8f0e9210` (`cc399928`)  
**Purpose:** provide a qualified independent mathematical path for ideal stationary coefficient/composite SRC certificates under DSD_DESIGN §8.6.1.  
**Scope ruling:** the exact checker has verified **two entire canonical 1-kHz intervals**, not the 11,516-interval campaign. The **independent spectral mathematics campaign gate remains CONDITIONAL**. This report does **not** qualify FFT4G execution roundoff, startup/finite-stream samples, measured release ELF identity, physical performance, or full P15 release.

## 1. Method and trusted base

The newly installed `p15_r6_exact_policy.py`, `p15_r6_exact_composite.py`, and `p15_r6_witness.py` independently verify continuous-frequency candidate subdivisions. The proof arithmetic uses only Python unbounded integers, exact `fractions.Fraction`, integer `math.isqrt`/`factorial`, and the two **byte-identical R5.1 proof companions** `p15_r5_exact_trig.py`, `p15_r5_integer_spectral.py` (supplied with the input handoff). No `mpmath.iv` result, binary64 transcendental approximation, `numpy` FFT or sampled waveform drives a certificate PASS. `float.as_integer_ratio()`/`Fraction.from_float()` decode an already source-verified IEEE-754 finite binary64 coefficient exactly, including its sign; no decimal-to-float coefficient conversion is used by the proof kernel.

**Required external source-binding trusted base, not silently re-proved in R6:** `p15_src_bound_operator.py`, `p15_src_capture_matrix.py`, `p15_src_stagewise_alias_proof.py`, `p15_src_complete_aliases.py`, `p15_numerical_reference.py`, and `certify_filters.py` resolve the source-captured production stage topology, halfband/native filter words, clocks and snapshots. `verify_pair` compares all pinned source hashes and source-bound stage-snapshot SHA-256; exact C-hex native coefficients are compared against their existing bank manifests. The R6 proof assumes the established source-to-stationary-stage correspondence for the **ideal operator**, and does not claim to derive FFT4G rounded execution from those coefficients. All R6 methods and source-binding files are SHA-pinned separately in every proof. A historical receipt's per-leaf generating-prover revision remains unauthenticated by these newer pins.

The independently checked mathematical claims are conditional only on integer-arithmetic language semantics, exact input/source parsing, the stated elementary identities, and the established ideal-stage binding. No unqualified interval numerical backend is in the **arithmetic acceptance path**. External libraries imported by the source-binding tools do not supply acceptance bounds. Ordinary `float` values are used for identity validation, not to decide safe spectral inequalities.

## 2. Lemma A: exact pi and transcendental enclosures

`p15_r5_exact_trig.py` encloses pi using Machin's identity

\[\pi=16\arctan(1/5)-4\arctan(1/239).\]

For \(0<x<1\), the alternating expansion of \(\arctan(x)\) is bounded by its next omitted term. R5 evaluates 78 terms at 1/5 and 20 at 1/239, using exact rational numbers; `pi_interval` verifies interval width \(<2^{-310}\) and \(3<\pi<22/7\). Given rational cycles \(r\), periodic argument reduction to \([-1/2,1/2)\) is performed with exact modulo. For \(x=2\pi r\), exact rational pi endpoints are rounded *outward* to a 312-bit dyadic grid. The central grid argument's sine/cosine uses a 62-term Taylor series; its Lagrange remainder is bounded by \((22/7)^d/d!\) with \(d=124\) for sine, \(d=123\) for cosine. Every grid multiplication/division uses integer floor/ceiling endpoints. Argument uncertainty is added via the global Lipschitz bound \(|\sin x-\sin y|,|\cos x-\cos y|\le |x-y|\). A final outward reduction to 256-bit dyadic endpoints encloses the exact trigonometric values. Oversized arguments and insufficient input-domain precision **refuse**.

Audit detail: the Taylor polynomials have highest powers 123 (sine) and 122 (cosine); thus remainders of orders 124 and 123 are appropriate. Signed integers are divided by their positive denominator using mathematical floor and ceiling, including negative endpoints. The bound uses \(22/7\) only as an *upper bound* on \(|x|\), never as a substitute for pi.

## 3. Lemma B: independent exact FIR interval enclosure

For finite exact binary64 coefficients \(c_k\), signed integer tap indices \(k\), and rational phase center \(c\), define

\[H(f)=\sum_k c_k\exp(2\pi i(k-c)f).\]

Let \(m=(a+b)/2\), \(\rho=(b-a)/2\), and Taylor degree \(N\). For every \(f\in[a,b]\):

\[|H(f)-H(m)|\le \sum_{j=1}^N\frac{|H^{(j)}(m)|\rho^j}{j!}+\frac{(2\pi\rho)^{N+1}}{(N+1)!}\sum_k |c_k|\,|k-c|^{N+1}.\]

This is Taylor's theorem applied termwise to finitely many complex exponentials, followed by the triangle inequality and \(|e^{i\theta}|=1\). `certify_fir` encloses all midpoint derivatives with exact rational coefficients, integer-grid complex multiplication/rotation, and Lemma A. Rectangular interval bounds on real/imaginary components produce magnitude enclosures via integer `isqrt`: floor gives a lower, ceiling gives an upper. Every variation and moment term is rounded *up*, while the center lower endpoint is rounded *down*. The final lower is `max(0,center_lower-variation)` and upper is `center_upper+variation`, divided by the stage's exact positive interpolation factor \(L\). Real symmetry is **not assumed** by this general-purpose FIR checker; negative coefficients, signed tap indices and cancellation are admitted. This differs from the historical 75-digit interval recurrence.

The frequency interval must be within the stage highrate domain \([0,1/2]\) after exact sign reflection, and the kernel refuses unsupported tap/degree/argument sizes. Negative, zero and near-zero central response do not license a positive lower bound absent proof.

## 4. Lemma C: exact finite-difference majorant

Write \(H(z)=\sum_k c_k z^k\). For integer \(p\), \((1-z)^p H(z)\) has the exact convolution coefficients \(\Delta^p c\), including **zero extension at both ends**. For \(z=e^{2\pi i f}\), \(|z|=1\):

\[|H(z)| \le \frac{\sum_k |(\Delta^p c)_k|}{(2\sin(\pi a))^p}, \qquad 0<a\le f\le b\le 1/2.\]

The numerator is computed from a common exact dyadic denominator, using integer differences; R6 evaluates \(p=2,4,6\). The denominator uses Lemma A's *lower* enclosure of \(\sin(\pi a)\), exploiting sine's monotonicity on \([0,\pi/2]\). If \(a=0\), the sine lower bound is nonpositive, or support spans too many positions, the shortcut refuses and uses Lemma B. It is **only an upper bound**, never a lower. The implementation uses it only if decisively below a conservative internal cost guard (\(10^{-9}\)); this is not a relaxed release threshold. Every used difference bound still enters the entire coherent alias sum.

## 5. Lemma D: halfband pair shortcut, independently recertified

Only when exact tap inspection establishes \(h[0]=1/2\), \(h[-k]=h[k]\), and all other nonzero coefficients have *odd* \(k\), define \(Q(f)=\sum_{k\ne 0}h[k]e^{2\pi i kf}\). Then \(Q\) is real/even, \(Q(f+1/2)=-Q(f)\), and

\[|H(f)|+|H(f+1/2)|=2\max(1/2,|Q(f)|).\]

Absolute periodic/reflection symmetry reduces the needed complete global \(|Q|\) domain to \([0,1/4]\). R6 independently partitions that entire domain, rechecking each interval with Lemma B's **integer** evaluator. A 256-node ceiling prevents runaway; a failed tight proof falls back to the globally valid \(2\max(1/2,\sum_{k\ne0}|h[k]|)\), not an assumed near-unity value. No historical `mpmath.iv` halfband-majorant receipt is trusted. Cached halfband majorants are keyed to the loaded immutable stage instance and exact coefficients; coefficient mutation requires new instantiation/source verification.

## 6. Lemma E: complete reverse branch enumeration

For a stage input rate \(F_i\), interpolation \(L\), decimation \(M\), output rate \(F_o=LF_i/M\), a downstream frequency \(f\) and current inherited shift \(b\), the complete inverse-stage highrate frequency population is indexed by all integers \(k\) obeying

\[-LF_i/2 \le f+b+kF_o < LF_i/2.\]

Exactly \(M\) integers satisfy this half-open inequality for each frequency. R6 independently implements exact-rational ceilings, exact input-clock wrapping, and exhaustive enumeration for every stage in reverse order. On a frequency interval it *does not* accept a branch set seen only at its midpoint: it compares the integer-valued branch and wrap functions at both endpoint limits, derives their next rational transition exactly, and returns a required **interior split** on any change. Ceil at the upper edge uses the limit from below for decreasing linear arguments; floor similarly uses its limit from below for increasing arguments. A transition at the common closed endpoint is assigned to adjacent limits; finite trigonometric responses extend continuously to the endpoint. This creates a disjoint-interior, shared-endpoint complete cover with no unproved midpoint omission.

At the native boundary, R6 independently checks **every expected harmonic** in the exact lattice \(f+s F_{out}/U\) lying in \([-F_{native}/2,F_{native}/2)\). It requires integer lattice shifts and cardinality, and retains every distinct stage history even if multiple paths land on one harmonic; such contributions may add coherently. For a passband proof exactly one all-zero-shift direct path is required. Stage rate products, stage count and all resource ceilings are checked before certification. This path enumerator is separate source code from P15's earlier `complete_paths`; comparisons with it are *corroboration*, not the proof premise.

## 7. Lemma F: complete composite magnitude and pruning

For any path, the absolute transfer cannot exceed the product of the appropriate per-stage interval upper bounds divided by each stage \(L\). The wanted path's lower is the product of nonnegative FIR lower bounds. At all frequencies the full actual desired coherent contribution obeys

\[|C_{wanted}| \ge \max(0,\prod_j L_j^{(low)}-\sum_{p\ne wanted}U_p),\]
\[|C_{total}| \le \prod_j U_j^{(direct)}+\sum_{p\ne wanted}U_p.\]

For source-stop mode, include **every** path whose native input-frequency interval intersects \(|f|\ge S\); intersection instead of full inclusion is a deliberate conservative overcount at boundary crossings. No RMS sums, magnitude cutoffs or alias-family deduplication are permitted.

R6 constructs a trie from the complete explicit path population. At each node, the exact `count` of descendants times the exact remaining per-stage \(L^1\) FIR norms is an upper bound. It may also use the tighter *full-branch* cap \(\prod_j M_j\|H_j\|_1/L_j\), substituting Lemma D's full complementary pair norm only for stages with valid halfband identity and source-clock pair spacing. Trie validation rejects duplicate full paths, an impossible branching count, an invalid halfband pair, or mixed stage topologies. A *subset* of valid branches cannot exceed the full nonnegative majorant. Every heap replacement subtracts an exact rational old upper and adds exact rational child bounds, preserving a bound on all included descendants; heap ordering is a performance hint and never affects soundness. A saturated evaluated leaf stays in the total. Early termination at a normative limit is allowed only if the **complete retained exact upper** is strictly below it. Resource exhaustion returns OPEN.

These lemmas establish the composite upper/lower enclosures for the **fixed, source-bound ideal stationary stage operator** on each accepted leaf. No phase-cancellation credit is needed or granted.

## 8. Lemma G: exact policy threshold

The normative \(\pm0.0001\) dB amplitude boundaries are \(10^{\pm 1/200000}=\exp(\pm\ln(10)/200000)\). R6 establishes \(\ln(10)=3\ln 2+\ln(5/4)\) using positive atanh series at exact arguments \(1/3\) and \(1/9\), with exact geometric series tail bounds. Exponential Taylor truncation is bounded by \(e^{|x|}|x|^{N+1}/(N+1)!\), using \(e^{|x|}\le1/(1-|x|)\) for \(|x|<1\). All operations are exact rational. To PASS, the wanted *lower* must exceed the **upper** endpoint of the lower permissible transfer; the total *upper* must be strictly below the **lower** endpoint of the upper permissible transfer. The coherent unwanted/native-stop bound must be strictly below **\(1/100000000\)**. The original tolerances are not modified. An interval overlapping a threshold must split further or remain OPEN.

## 9. Proof-carrying certificate verification

A candidate proof names one **unchanged canonical** `p15_full_band_campaign.py` 1-kHz job and its SHA-selected original historical receipt, the source + stage exporter SHA binding, the design SHA, and the exact verifier-module hashes. It supplies exact rational subdivision endpoints and reported exact rational leaf bounds. The verifier, `p15_r6_witness.py --verify FILE`, **never trusts these reported numbers**: it independently reconstructs all paths, rigorous stage bounds, full alias upper, direct lower, source-stop classification and policy for *each supplied leaf*. It demands exact equality of reported and recomputed bounds. Sorted leaves must partition the **entire original requested interval**, with no gap, overlap, out-of-range endpoint, missing branch transition, invalid source pin or unrecognized profile. A claimed summary is independently reconstructed; corrupted or absent evidence is REFUSED. The canonical historical aggregate receipt does not influence the recomputed mathematics (except as a SHA-bound job/inventory identity), and is never edited.

A producer may search candidate subdivisions and persist an OPEN checkpoint. A resumed checkpoint is **only a hint**; it cannot produce a PASS proof until complete re-verification. The proof is a short *replayable program-input certificate*, not an enormous transcript of generated Taylor terms: its sufficiency relies on independently audited exact verifier source and source-bound coefficients, rather than trusting the former producer.

## 10. Executed production-source evidence (two complete canonical intervals)

Cell: `dsd64.mastering.pcm44100`, input native 2,822,400 Hz; intermediate 88,200 Hz; output 44,100 Hz; full band/campaign canonical `[0, 1000] Hz`.

| Checked mode | Independent status | Source-bound leaf cover | Strict exact-policy outcome (display approximations only) |
|---|---|---:|---|
| Passband | PASS-LOCAL-R6-INDEPENDENT | 8 exact `[0,125] ... [875,1000]` subintervals | lower wanted \(\ge 0.99999984277236\); total upper \(\le 1.000000157098523\); coherent unwanted upper \(\le 3.403684850\times10^{-11}\) |
| Native source-stop | PASS-LOCAL-R6-INDEPENDENT | 1 exact `[0,1000]` interval | native-stop coherent upper \(\le 5.460728229\times10^{-9}\) |

All inequality decisions in the verifier use **exact fractions**, not these rounded displays. The passband witness required 152 independent FIR evaluations and 160 alias-frontier expansions on fresh replay; the stop witness required 13 FIR evaluations and 20 expansions. Both proof JSON files were independently replayed successfully after publication. Tests include an analytically soluble two-branch halfband fixture and intentionally corrupted leaf, source, and coverage records.

**What this proves:** the R6 integer method can independently establish the *complete continuous-frequency spectral mathematics* for a production-source-bound canonical passband and a matching canonical native-stop interval. The checker is not merely another validation of historical PASS flags.

**What it does not prove:** all remaining 11,514 canonical intervals; source-to-final-ELF correspondence; floating-point execution roundoff; or physical release qualification. No cryptographic attestation to the original October 18 prover execution is inferred from subsequent R6 source hashes.

## 11. Exact remaining mathematical work

The original 11,516 aggregate receipts remain a source/coverage inventory, not self-contained per-leaf mathematical proofs. The exact checker and witness format are implemented and exercised over two real intervals. The **remaining ideal-operator mathematics gate** requires independent R6 proofs (or equivalently audited source-level mathematical validation of the older backend and complete recurrence) for every **other 11,514** original canonical jobs; doing the 11,516-point exploratory search again is not needed. Checking candidate R6 leaves is deterministic and independent; newly generated subdivision hints may be spread across resumable resource-bounded runs. Prioritize common 44.1-kHz cells, then the costly DSD256/384-kHz stage topologies, without changing tolerance or DSP code. Do not declare the entire mathematics gate PASS until the exact complete set is qualified. The FFT4G release arithmetic is a *separate* outstanding gate.
