# Phase 08 arithmetic proposals: decoder P3, encoder P2, gain P1

**Status: PROPOSED, NOT OWNER-ADOPTED. D11 P2/P3 and D6's numeric `pow` limit remain OPEN.**
The signed [owner record](amendments/PHASE08_OWNER_DECISIONS_2026-11-20.md)
controls acceptance. These statements cannot be used as a universal
same-operator certificate until all missing terms are derived, tested and
approved. A finite corpus or CLI/public-API agreement is not a proof of a
bound for every accepted stream.

## Numerical model and matrix

The intended model uses IEEE-754 binary64, round to nearest ties to even,
finite intermediate values, gradual underflow, no FTZ/DAZ, no reassociation
across the named kernel boundary, and exact versions of the checked-in
binary64 coefficients. Source-to-binary correspondence requires compiler and
linker flag/assembly evidence, not just a source-code hash. If one of these
conditions fails, the bound does not apply. The sign-off must identify the
compiler, flags, OS, CPU/ISA and output container for each admitted route.

The **required universal domain** (D11) consists of **every stream that the
named route accepts**, including every permitted finite length and valid
partial block, subject only to documented resource limits and refusals. No
artificial peak, energy, length or bandwidth restriction may be introduced to
make the result provable. All gain and output options accepted by a route
must also be covered or explicitly refused. This proposal is incomplete for
that domain.

## P3: five-stage unified decoder DSD64/128, before the final SRC

Let `u = 2^-53`; use each coefficient's **exact binary64 value** as a rational
number. For stage `j`, let `L_j` be its tap count, `A_j = Σ_i |h_j[i]|`,
`U_0 = 1`, `E_0 = 0`, and `η = 2^-1074`. The physical chronological
DSD input is ±1 and can be extended by exact zeros at both finite boundaries.
A **candidate** uniform forward-error envelope for the five FIR stages is:

```text
k_j      = 2*L_j + 4
γ_j      = (k_j*u)/(1 - k_j*u)            (requires k_j*u < 1)
U_j      = A_j * U_(j-1)
E_j      = A_j * E_(j-1) + γ_j*A_j*U_(j-1) + L_j*η
```

At DSD64/128 the stage cascade has four common symmetric 57-tap half-bands,
followed by the selected mastering or wideband bank (117/153/257 taps).
The phase, exact sample count, zero extension and group-delay discard are
**part of the operator**, not error allowances. They are independently
implemented by `tests/pcm64/qualification/unified_reference.py`, which uses
full convolution in extended precision rather than mirrored production rings.
The test checks 64 cases against genuine production output and records errors
and provisional envelopes. The test's 4× margin for reference evaluation is
a finite witness tolerance, *not* an adopted bound.

**Open items:** prove `k_j` covers every arithmetic path of all enabled FIR
kernels, including center pairs, FMA variants, tails and denormals; audit
coefficients and accumulation details to rule out overflow; bound error in
sample-count/rate mapping; derive exact source-audited effective private SRC
operator `W[n,j]` and its phase/coefficient interpolation rounding; construct
an independent same-operator reference with at least 75 decimal digits;
combine `E_5` with `B_src[n]`, coefficient error, and upstream gain error as
in `DSD_DESIGN.md` §8.6.1; check every accepted final PCM output rate and
channel/domain/format combination. There is no licensed shortcut from the
former v2 fixture's 2^-48 allowance (D14) to this new bank.

## P2: v1 source front end for certified v3 DSD64/128 encoders

Preserve the exact coefficient and operation identities of `src/pcmdsd.c`
from `595d401`. The front end performs native conversion/interpolation plus
its frozen prefilter. For each rate conversion or FIR stage, an analogous
*same-operator* analysis needs an independent exact rational coefficient and
phase schedule, the live source's arithmetic graph, and bounds for coefficient
construction and state updates. If `W_j[n,i]` is the **same effective
operator as production** and `B_in[i]` is an already proved bound, a proposed
recurrence is:

```text
B_out[n] = γ(N_ops[n]) * Σ_i |W_j[n,i]| (|x[i]| + B_in[i])
           + Σ_i |W_j[n,i]| B_in[i] + B_coeff[n] + B_other[n]
```

`N_ops` must include the real interpolation/phase arithmetic and not be
estimated from an unrelated, fixed ideal Kaiser filter. `B_coeff` and
`B_other` may not be set to zero without a source-level proof. The
nonlinear certified switched-resonator's state and one-bit decisions have
separate accepted recurrence and input-envelope contracts; an FIR error
estimate alone does not certify equal one-bit output for all accepted inputs.

**Open items:** the source-audited `W` and complete operation counts for both
SRC stages and the prefilter; input decoder/PCM rounding terms for WAV and
FLAC; the clipped/admitted interface semantics; same-operator high-precision
cross-checks for each ISA; integration with the frozen resonator certificate.
The existing `src/pcmdsd` source and certification have not been changed.

## D6 amplitude multiplication and headroom

For a decimal dB setting `d`, the intended amplitude factor is
`g = 10^(d/20)` for `gain` and `h = 10^(-d/20)` for headroom. Exactly
0 dB uses an identity path without a multiplication; `--dsd-level sacd`
uses an exactly representable factor 2. For nonzero dB inputs, a bound must
include the actual platform `pow` implementation's rounding, the parse of
the decimal argument, the conversion of `d/20`, and the final multiplication.
A conservative decomposition is
`B_gain ≤ |x|*B_pow + |g|*B_input + u*|g*x| + B_subnormal`, conditional on
no overflow; the `B_pow` term has **no accepted platform value** yet. Do not
substitute an assumed correctly rounded libm or claim all `pow` results are
within 1 ulp without a verified runtime-specific premise.

## Evidence and stopping rule

- Independent native-clock reconstruction: finite checks PASS; universal
  P3 and final SRC OPEN.
- D13 locked predecessor check: PASS; it deliberately refuses reference
  updates and retains the 19 historic v2 receipts.
- New independent **accepted** unified decoder words: D16 OPEN, awaiting
  owner reason/approval/predecessor.
- Certified encoder frontend identity from `595d401`: unchanged; P2
  source-stage bound and independent universal proof OPEN.
- Numeric `pow` limit: OPEN pending a target-build-specific error model.

Do not claim Phase 08 release qualification or automatic native routing from
these finite results. P16's separate historical authorization and waiver are
recorded in the owner decisions; they do not close D11 or D16.
