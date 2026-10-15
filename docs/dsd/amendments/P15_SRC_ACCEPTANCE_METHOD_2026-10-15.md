# P15 SRC acceptance: numerical method and scope, 2026-10-15

**Disposition: the requirement is mandatory, the test remains OPEN.** This
clarifies how to apply `DSD_DESIGN.md` §§6.1, 6.5, 8.6 and 10.4; it does not
change their 0.0001-dB passband / -160-dB composite stopband and coherent
alias limits, change production code or invent a passing measurement.

## The distinction that prevents a false failure

An independent, different-design rational/polyphase (e.g. Kaiser/SciPy)
resampler may produce different samples from the private SoX SRC even when
*both* obey the same transfer specification. Neither a fixed samplewise
`1e-5`/`1e-3` deviation nor the FIR-only 8.6 tolerance is an end-to-end
acceptance criterion for two different filters. **A bound on samplewise
difference between unlike transfer functions is OUT OF SCOPE** for this
release. Keep those differences as diagnostic observations, not failures or
waivers. This is **not** an exclusion of §10.4's independent *same-transfer*
SRC arithmetic reference and transfer acceptance.

The SRC-bearing population is **48/54 v1 plus 24/27 v2 scalar cells**. The
24 v1 and 12 v2 noninteger native/output ratios are only a subset: an integer
native/output ratio can still use the SRC when its intermediate clock differs
from the destination clock. The six v1 and three v2 actual identity-bypass
cells retain the independent native FIR-only bounds.

## Deterministic, premeasurement numerical acceptance rule

For each versioned cell, independently derive the **effective production SRC
operator**, not merely a replacement resampler with similar marketing
parameters. Bind its ratio, binary64 coefficient representation and/or its
exact coefficient-generation inputs, phase/interpolation schedule, delay,
start/drain zero-extension, and final count to the measured implementation.
Verify those bindings independently of the audio exporter, and evaluate the
same finite operator at high precision (at least 75 decimal digits) from
independent code. Never feed a production output back in as the reference.
Use the same independently calculated native-FIR output as its input.

For output index `n`, write the finite equivalent SRC transfer as
`y_exact[n] = sum_j W[n,j] * x_exact[j]`; `W` includes the phase and actual
filter realization. Use the **following a priori arithmetic bound**, not a
post-hoc global epsilon:

```
u             = 2^-53  (binary64 unit roundoff)
gamma(k)      = k*u/(1-k*u), requiring k*u < 1
A[n]          = sum_j abs(W[n,j]) * (abs(x_exact[j]) + B_fir[j])
B_src[n]      = gamma(N_ops[n]) * A[n] + B_coeff[n] + B_other[n]
B_total[n]    = B_src[n] + sum_j abs(W[n,j]) * B_fir[j]
ACCEPT(n)     iff abs(y_production[n] - y_exact[n]) <= B_total[n]
```

Here `B_fir[j]` is the independently verified, propagated finite-FIR
roundoff allowance (§8.6), **not** a bound on different SRC designs.
`N_ops[n]` is a source-audited *conservative maximum* of contributing
correctly rounded arithmetic operations for the actual SRC path, including
interpolation and phase selection, recorded before evaluating residuals. A
mere tap count is inadequate when additional arithmetic contributes.
`B_coeff[n]` bounds independently verified quantization/generation and
interpolation errors **not already represented by the exact effective
operator W**; avoid counting the same error twice. `B_other[n]` bounds any
other non-ideal arithmetic on that path (including applicable subnormal or
non-correctly-rounded primitives). Both may be zero **only with evidence**.
If this algebra is not applicable to a backend primitive, supply a sound
interval/forward-error bound for that primitive instead. An unbounded term,
unknown operation count, overflow/underflow not analyzed, coefficient
identity mismatch, or unsatisfied output index **means the numerical gate is
OPEN**, not an automatically widened tolerance. Bind all bound-producing
inputs by digest. Evaluate first/last output and impulse locations explicitly,
not just a steady-state interior crop.

This formula specifies a reproducible, input-dependent envelope before
measurements; it is **not** a claim that the current instrument already
computes `W`, `N_ops`, `B_coeff`, or `B_other`. It must be implemented,
independently reviewed and evaluated for all SRC-bearing production paths.
Finite-error proof and transfer-function qualification remain distinct.

## Composite transfer / alias acceptance (also mandatory)

For all permitted clock and profile choices, apply §§6.1/6.5 to the *actual*
composed native FIR + private SRC (and to the effective representable
passband). Independently bound worst-case passband magnitude/ripple, each
stopband/image family, and the **coherent sum** of all potentially folding
images. Verify response extrema with a justified between-sample bound
(e.g. adaptive derivative/interval-bracketed search); a few clean sine tones
or selected FFT bins cannot establish the required supremum. Rational SRC
polyphase/phase behavior must be covered, including both decimation and
interpolation. Report native one-bit source noise separately from unwanted
filter/alias transfer. Check exact output length, latency/phase,
startup/drain and graph clipping/count invariance on the existing worklist.

A different-design independent SRC remains a useful cross-check for audible
content and gross transfer shape, **not** the same-transfer arithmetic oracle.
The existing sampled SRC responses, native FIR certificates, 81 scalar cells,
324 forced jobs and 144 detailed ISA observations may be **reused** if their
source/raw hashes bind to the final tree. No new full hardware/soak matrix is
requested merely because this analytical certificate is missing. Reinspect
rather than rewrite the immutable measured evidence.

**Reuse shared operator evidence.** The 72 SRC-active cells span only 24
distinct intermediate/output rate pairs. One independently certified SRC
operator may cover cells with the same coefficient realization, ratio,
phase, rounding path and startup/drain behavior; combine it with the
appropriate versioned native-FIR response and input-dependent arithmetic
bound. Different starts, lengths or coefficients still need their distinct
boundary/error checks. Do not redesign 72 resamplers or repeat otherwise
valid physical measurements to satisfy an analytical evidence gap.

**Closure conditions:** one independent same-transfer arithmetic certificate
and one independently bounded composite transfer/alias certificate covering
all 72 SRC-active cells, and a reviewed versioned release decision. The
current stripped transport omits original arrays and graph outputs; retrieve
those exact hash-matched payloads from the operator's branch for full replay,
not a fabricated replacement.
