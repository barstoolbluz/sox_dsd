# SoX-NG P15 R9 — Uniform source-stop theorem and independently checked v2 DSD256 family

Date: 2026-10-19  
Exact source authority: `sox_ng-P15-adjudicate-cc399928.tar.gz`, SHA-256 `d058b3908817e01e937f49e0dfeee7194d847aae74f625043e881d8b8f0e9210`.

## Scope and result

**PASS for the ideal-operator, composite source-stop requirement of all eight `decode.mastering.v2.dsd256` SRC-active cells.** Exactly **958 canonical source-stop jobs** are covered continuously; these are **not** passband or runtime FFT4G certificates. Every accepted worst-case composite upper is strictly below the original `1/100000000` limit. The native proof covers intermediate frequency magnitudes in `[0,88200]` Hz using 179 contiguous source-bound rational-frequency leaves and an exact split at 80000 Hz. Three independently verified global SRC stage certificates make the factorization sufficiently tight for 48, 96 and 192 kHz outputs.

The original 11516-job historical coverage inventory is unchanged and is not considered an independent mathematical proof merely because its receipts say PASS.

## Mathematical objects and exact arithmetic

The production native filter bank is a cascade of six 2:1 decimation FIRs taking `11289600` Hz to `176400` Hz. The native source spectrum is restricted to a half-open Nyquist interval and the source-stop boundary is `80000` Hz. For each intermediate frequency `x in [0,176400/2]`, the 64 complete native alias families are `x+k*176400`, `k=-32,...,31`, interpreted modulo the native clock. The `k=0` family is in the stop set only when `x >= 80000` Hz. The two closed covers meet exactly at 80000, with the boundary frequency assigned to the right-hand interval for that family. Frequencies at negative intermediate Nyquist reflect by reality and conjugate symmetry.

For FIR stage `j`, with real binary64 coefficient words `h[j,n]`, upsample factor `L[j]`, and high-rate frequency `u`, write

`G_j(u) = (1/L[j]) * sum_n h[j,n] exp(2 pi i n u/(Fin[j] L[j]))`.

Binary64 coefficients are embedded in exact rationals. The magnitude enclosures are computed with exact Python integers/rationals, outward fixed-grid trigonometric bounds and Taylor remainder bounds (R5/R6/R7); neither ordinary binary64 sampling nor `mpmath.iv` may grant PASS. Symmetry/paired-support acceleration is admitted only after exact tap-index and coefficient identities are checked.

### Lemma 1: The native uniform bound

For every `x in [0,88200]`, define

`B_N(x) = sum_{k: |x+k*176400|>=80000 (mod native)} prod_{j=0}^{5} |G_j(x+k*176400)|`,

with the above Nyquist convention. Each sum consists of **all** 63 or 64 stop-source harmonics; no cancellation is assumed. For each native stage and source-family leaf, an individual upper bound is the smaller of an exact stage interval enclosure and a uniform valid stage cap. Five exactly odd-symmetric halfband stages have reusable full-frequency bounds; the sixth native FIR has an independently checked full-frequency bound `1.001` over normalized frequency `[0,1/2]`. These caps may be loose, but never underestimate an individual magnitude.

The uniform cover consists of 179 consecutive, non-overlapping rational-frequency leaves with exact endpoints 0, 80000 and 88200. Every leaf has its family list and selected stage refinements. The independent verifier reproduces the stage enclosures for the selected refinements, checks *every* family and leaf, checks exact cover adjacency and the source/method fingerprints, and refuses any underreported upper. Its replay establishes

`B_N(x) < 13/10^10 = 1.3e-9` for the **whole** intermediate-frequency continuum.

Because every native FIR coefficient is real, the same bound holds for negative intermediate frequencies by reflection.

### Lemma 2: One-stage complete reverse-alias bound

For a rational `L/M` stage there are **exactly M** upstream high-rate branches per output frequency, including half-open endpoint transitions. The phase of each term may differ, so we bound its absolute transfer, without assuming cancellation. Let `n= sum |h|/L`, exactly rational.

* `M=1`: the branch magnitude is at most `n`. Alternatively, a whole-frequency exact FIR certificate gives a sharper upper.
* `M=2`: the sum of branch magnitudes is at most `2n`. If the stage is an exactly recognized odd-symmetric halfband, the complementary identity gives its smaller, independently bounded sum. An arbitrary real-coefficient stage can instead use an explicit two-branch certificate: normalized `q in [0,1/4]`, branch magnitudes are bounded by the FIR on intervals `q` and `1/2-q`; this is valid because for real taps `|G(q+1/2)|=|G(1/2-q)|` when `L=1`.
* Odd `M=2p+1` (the encountered `M=147`): of the complete M branches, at most one is within half an output-rate spacing of zero, and the other branches can be paired so that the k-th pair has absolute high-rate frequency at least `(k-1/2)*Fout` for `k=1,...,p`. The central branch has upper `n`. A branch at normalized magnitude `q>=q_min>0` admits the exact finite-difference upper `min(n, ||Delta^r h||_1 / (L*(2*sin(pi*q_min))^r))` for certified even orders `r=2,4,6`, since `sin(pi*q)` increases on `[0,1/2]`. The resulting `n+2*sum_k bound(k)` is a global, conservative branch-sum majorant. Dyadic quantization is always outward.

The original implementation's binary64 coefficients and stage ratios are retrieved from the same SHA-bound production operator snapshots as earlier R6–R8 work; the verifier refuses a new topology or mismatched source.

### Lemma 3: Cascaded SRC alias bound

Let `A_j(f)` be the coefficient along inverse SRC path `j` to a particular intermediate frequency. The triangle inequality and induction over reverse-stage branches give

`sum_j |A_j(f)| <= product_{stage s in SRC} B_s`,

where `B_s` is a valid global one-stage branch-sum bound from Lemma 2. This product includes every reverse path and is valid at rational branch transitions by one-sided limits and continuity of the FIR response; no phase cancellation is credited. Repeated paths are deliberately overcounted, which is conservative.

For any output frequency `f`, the SRC paths reach a collection of intermediate frequencies `x_j`. Source-stop harmonics at each `x_j` have total native transfer at most `B_N` (Lemma 1). Reordering a sum of **nonnegative** magnitudes and applying the triangle inequality establishes

`sum_{all native source-stop harmonics s} |composite_C_s(f)| <= B_N * sum_j |A_j(f)| <= B_N * product_s B_s`.

Therefore **one** native continuum certificate plus **one** global SRC norm certificate discharges **every** canonical source-stop frequency interval of that operator, without creating a per-interval proof transcript. This theorem covers the complete output continuum even when the output clock exceeds the intermediate clock.

### Lemma 4: Three sharpened whole-stage witnesses

The whole-frequency witness producer partitions `[0,1/2]` for the two `M=1` filters and `[0,1/4]` for the `M=2` stage. At each accepted closed rational leaf, it proves the original FIR or exact complementary-pair upper is **strictly less** than the advertised cap. The independent verifier *recomputes* all leaf enclosures, refuses gaps/overlaps/missing endpoints, checks source SHA/method SHA and exact binary64 tap identity, and checks the strict inequalities. The proof never trusts the producer's chosen subdivisions or summary.

| Rate | SRC stage | Multiplicity | Uniform cap | Independent complete leaves |
|---|---:|---:|---:|---:|
| 48000 Hz | first SRC | 1 | 1.01 | 165 |
| 192000 Hz | first SRC | 1 | 1.01 | 99 |
| 96000 Hz | second SRC | 2, paired | 1.10 | 66 |

These three witnesses replace loose L1 majorants of approximately 2.829, 2.756 and 5.513, respectively, while preserving the original filter and all aliases. Other stages use the baseline exact-rational lemma.

## Verified eight-cell bounds

The full `--prove-all` replay recomputed every stage witness and all 179 native-domain leaves. The 8 reported conservative composite amplitude bounds (rounded **up here for display** to the indicated digits) are:

| Output | Canonical stop jobs | Composite source-stop upper | Disposition |
|---|---:|---:|---|
| 44100 | 23 | 7.166630e-9 | PASS |
| 48000 | 24 | 9.150380e-9 | PASS |
| 88200 | 45 | 7.150976e-9 | PASS |
| 96000 | 48 | 4.275916e-9 | PASS |
| 192000 | 96 | 6.479021e-9 | PASS |
| 352800 | 177 | 3.575488e-9 | PASS |
| 384000 | 192 | 9.298302e-9 | PASS |
| 705600 | 353 | 3.654141e-9 | PASS |
| **All eight** | **958** | `all <1e-8` | **PASS source-stop only** |

Authoritative exact fraction bounds, every stage bound and all SHA identities are in `P15_R9_ALL_V2_DSD256_STOP_VERIFIED.json`; not the rounded display table.

## Explicit non-claims

1. This proof **does not** establish wanted passband magnitude/ripple or passband coherent-alias acceptance of the other canonical jobs.
2. The scope is **only** the DSD256 `decode.mastering.v2` native filter family and eight source-bound SRC operators; other profile native stage coefficients or stop thresholds cannot inherit this result without their own proof.
3. No statement is made about arbitrary-input FFT4G floating-point roundoff, final release binary correspondence, physical-host benchmarking, or DSD256 native runtime behavior.
4. The mathematical argument uses ordinary, accepted identities for real finite FIR Fourier transforms, triangle inequality, rational-stage alias branch completeness, integer arithmetic, and the separately audited R5/R7 trigonometric/Taylor kernel; it is not machine-checked in Lean/Coq.
5. The source/capture bindings show correspondence to the **packaged** original cc399928 source. A new SHA file does not retroactively authenticate historical executions.
