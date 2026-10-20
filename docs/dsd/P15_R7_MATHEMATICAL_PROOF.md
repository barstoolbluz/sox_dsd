# P15 R7 — exact-ball and reflected-support FIR mathematics

**Date:** 2026-10-19  
**Source:** SoX-NG `cc399928`; source archive SHA-256 `d058b3908817e01e937f49e0dfeee7194d847aae74f625043e881d8b8f0e9210`.  
**Scope:** Independently replayed *ideal captured-coefficient* continuum certificates. **No FFT4G execution-roundoff or release-ELF claim.**

## 1. Trusted mathematical objects and dependencies

The R7 checker extends the R6 independently implemented source-bound composite engine; it does not modify R6's alias-path recurrence, exact branch-transition checks, source binding, subtree caps, normative passband bounds, or stop-source policy. Every accepted R7 proof carries SHA-256 identities of its original canonical receipt, exact production source and stage snapshot, R5/R6 mathematical modules, and the three R7 computation modules. The sealer independently verifies all given proof leaves; a historical aggregate PASS never grants independent qualification.

`p15_r5_exact_trig.py` supplies rational Machin/alternating-arctangent bounds for π and rigorously outward-rounded integer-grid bounds for sine and cosine. `p15_r5_integer_spectral.py` supplies exact-grid real interval arithmetic, integer square-root enclosures, and Taylor/Lagrange FIR remainder. These are the R6 trusted mathematical primitives; the R6 proof document specifies their assumptions. R7 requires Python's arbitrary-size integer and `fractions.Fraction` arithmetic to implement exact operations; no `mpmath`, `libm`, NumPy, binary64 transcendental, stochastic estimate, or unspecified `math.sqrt` output may grant PASS. Native filter/source decoder and captured SRC operator form an explicit, separately checked source-identity dependency.

## 2. Exact complex dyadic balls

Set `G=2^256`. A ball `(x,y,r)`, with integer components and `r>=0`, denotes the closed disk centered at `(x+i*y)/G` with Euclidean radius `r/G`. A certified trig rectangle `[a/G,b/G] + i[c/G,d/G]` is contained in the disk whose center is the integer floor of each coordinate's midpoint and whose integer radius is `ceil(sqrt(max(|x-a|,|b-x|)^2+max(|y-c|,|d-y|)^2))`. This uses `math.isqrt` and integer comparisons only. Conjugation maps `(x,y,r)` to `(x,-y,r)`.

For balls `(A,ra)` and `(B,rb)` in grid units, all represented values satisfy

`|ab-AB| <= |A|*rb/G + |B|*ra/G + ra*rb/G` (in grid units).

The central multiplication computes `floor(Re(A*B)/G)` and `floor(Im(A*B)/G)`, inducing an additional Euclidean central rounding error strictly less than `sqrt(2)` grid units. The new radius is

`ceil((ceil(|A|)*rb + ceil(|B|)*ra + ra*rb)/G) + 2`.

Because `2 > sqrt(2)` and `ceil(|A|)` uses an integer square root with upward correction, this is outward even with negative midpoints and cancellation. Exponentiation by repeated squaring and multiplication therefore rigorously contains `exp(2πikm)` for integer `k>=0`; negative `k` is handled with conjugation, which is sound on the unit circle. The finite coefficient exponents are bounded to prevent unreviewed resource explosions. There is no floating-point radius propagation.

## 3. Certified Fourier/Taylor continuum bound

For exact binary64 coefficient fractions `h[k]` and rational frequency `m`, the ball recurrence bounds each complex midpoint phase `exp(2πikm)` on the `G` grid. Multiply by the exact binary64 coefficient using outward interval scaling. Accumulate all complex derivatives of

`H(f)=sum_k h[k] exp(2πikf)`

using the identity `H^(j)(m) = sum_k h[k](2πik)^j exp(2πikm)`. For each `j` the real and imaginary intervals contain the derivative exactly. With `r=(hi-lo)/2` and `p=order+1`, the Taylor/Lagrange remainder follows from the global bound `|H^(p)(f)| <= (2π)^p sum_k |h[k]| |k|^p`:

`|H(f)-H(m)| <= Σ_{j=1..p-1} |H^(j)(m)|*r^j/j! + (2π*r)^p * Σ|h[k]|*|k|^p /p!`.

Each term uses an upward π enclosure, dyadic magnitudes with integer `isqrt`, and `Fraction` to round every sum outward. The original R5 eight-term proof remains as a fallback for unsupported reflected supports. R7's faster recurrence and its order selection never relax this inequality.

## 4. Exact linear-phase specialization

For tap indices reflected about `c=(k_min+k_max)/2`, **and only if every reflected coefficient is bitwise identical**, the identity

`H(f) = exp(2πicf) (h[c] + 2Σ_{k>c} h[k] cos(2π(k-c)f))`

holds. The factor `exp(2πicf)` has unit modulus, hence the real parenthesis has *exactly* the same magnitude as `H(f)`. R7 bounds the real Taylor derivatives only, from certified cosine/sine balls for `k-c`, and applies the same exact-grid remainder. There is no tolerance-based symmetry decision. When the support is reflected but coefficients are not equal, R7 uses the more general paired identity below instead.

## 5. Exact reflected-support, asymmetric-coefficient specialization

For each pair of supported indices `k_+=c+u` and `k_-=c-u`, and arbitrary real binary64 `h_+,h_-`, the *exact* identity is

`exp(-2πicf) [h_+exp(2πik_+f)+h_-exp(2πik_-f)] = (h_++h_-)cos(2πuf)+i(h_+-h_-)sin(2πuf)`.

R7 checks **all** positions pair off exactly before applying this identity. The real and imaginary derivatives are separately enclosed by outward integer-grid products, with signs obtained from the exact four-cycle of sine/cosine derivatives. The global Taylor remainder is `Σ_pairs (|h_+|+|h_-|)|u|^p`, multiplied by `(2πr)^p/p!` as above. A central unpaired coefficient, when present, contributes exactly to derivative zero and zero to higher derivatives. The phase removed from the original response has unit modulus, so the magnitude envelope of this transformed signal is the desired envelope. Negative taps, cancellation, integer or half-integer center, and non-palindromic input are admitted without approximation. If the support does not pair exactly, the generic certified recurrence applies.

## 6. Composite recurrence and acceptance

`p15_r7_engine.FastComposite` subclasses the independently justified R6 `ExactComposite`; only source-locked FIR interval calls and the halfband global-Q computation use the new R7 primitive. R6 enumerates exact rational inverse-clock branches, checks interior branch transitions and native harmonic completeness, builds a no-double-count path trie, retains all repeated source families, and bounds coherent aliases by triangle inequality. Wanted-path lower and upper bounds are stagewise products of valid FIR lower/upper bounds; the unwanted bound is conservatively added to the upper and subtracted from the lower. Normalized production stage gain includes the exact interpolation factor `1/L`; extra L1/finite-difference/halfband bounds may only *lower the upper*, never raise a lower. The existing R6 mathematical lemmas remain required assumptions and are included in the combined addon.

Every accepted R7 leaf must satisfy the **original** `DSD_DESIGN.md §8.6.1` inequalities, with no change to the ±0.0001-dB tolerance or `1e-8` alias/stop threshold. The independent verifier rejects unknown method hashes, invalid/overlapping/missing rational leaves, source/operator changes, false bounds, unsafe leaves, and forged summaries. The producer chooses candidate subdivisions and can be interrupted; its reported statuses cannot grant PASS until a *separate* full replay verifies all canonical interval leaves.

## 7. Exact scope and remaining gap

The independently sealed manifest `P15_R7_CC399928_REPLAYED_EVIDENCE.json` verifies 87/11,516 canonical intervals, comprising two complete source/rate cells: `dsd64.mastering.pcm44100` (43/43) and `dsd256.mastering_v2.pcm44100` (44/44). The remaining 11,429 canonical mathematical qualifications are **OPEN/CONDITIONAL**, not FAIL. In particular, `dsd256.mastering_v2.pcm384000` remains OPEN under bounded high-rate attempt due to computational resource/refinement costs; no physical or FFT4G release obligation is changed.

Independent verification is conditional on the explicitly stated source-to-operator capture and R5/R6 mathematical arguments being sound; no claim is made that this checker or the original production history has been formally verified by a proof assistant or cryptographic execution attestation.
