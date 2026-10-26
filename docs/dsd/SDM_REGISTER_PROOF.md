# Register-resident normal SDM: equivalence argument

This change starts from the source in `sox-dsd-fp-proven-2026-10-26.tar.gz`
(SHA-256 `60dd5878a8eb16341a56508fe7f010f227e5a1eb59da6cf63d31ae95120ef0c9`).
The independent oracle is the original `sdm.c` normal step and original
`dsd_kernels_scalar.c` block, frozen under
`tests/dsd/reference/sdm_register_oracle/` with source hashes. The production
copies of `sdm.c` and `dsd_kernels_scalar.c`, coefficients, legacy effect,
and automatic dispatch policy remain unchanged. The shared acceptance header
retains its original default expansion; only the four isolated SIMD translation
units select the local decision expression described below.

## Arithmetic contract

The optimized path requires binary64 intermediates, no reassociation, no FMA
contraction, and the caller's rounding mode. Builds used for qualification
specify `-fno-fast-math -ffp-contract=off -frounding-math -fno-lto` and isolate
each ISA translation unit. The normal fast path is disabled on i386 and when
`FLT_EVAL_METHOD != 0`. Every MXCSR exception must be masked, and DAZ and FTZ
must be disabled. Other environments use the unchanged scalar block.

Let `s[i]` denote the old bank, `n[i]` the candidate bank, `x` the current input,
`y` the previous decision, and `R` one binary64 rounding operation in the
current rounding mode. The scalar operation graph is:

```
n[0] = R(R(R(s[0] - R(g[0]*s[1])) + x) - y)
n[i] = R(R(s[i] + s[i-1]) - R(g[i]*s[i+1]))   (1 <= i < N-1)
n[N-1] = R(s[N-1] + s[N-2])
v[0] = R(x + R(a[0]*n[0]))
v[i] = R(v[i-1] + R(a[i]*n[i]))               (1 <= i < N)
```

There are no coefficient changes, skipped zero products, approximate
operations, or alternate reduction trees. Scheduling independent coordinate
graphs in parallel does not change any operand or rounding point. Each
decision add depends on the immediately preceding add, in ascending coordinate
order. For finite accepted arithmetic, induction over coordinates gives the
same decision accumulator; induction over accepted frames gives the same
decisions and state. Exceptional payloads are handled by scalar replay below.

For AVX, the state is held as coordinates 0..3 in a 256-bit register, 4..5 in a
128-bit register, and coordinate 6 or 6..7 in another register. A cross-half
permutation forms `[s2,s3,s4,s5]`; a shuffle forms `[s1,s2,s3,s4]`. Therefore
the four middle lanes calculate exactly coordinates 1..4 above. SSE2 uses
the same graph in pairs 1..2 and 3..4. Register shuffles only copy bits.

Order eight calculates coordinates 5..6 in a pair and coordinate 7 with its
separate terminal addition. Order seven first forms `[s5+s4,s6+s5]`, then
applies the multiply/subtract only to the lower lane. Its upper lane is the
terminal addition. No operation uses inactive coordinate 7. First-coordinate
arithmetic remains separate in both layouts. The AVX-512 translation unit
uses this narrow layout; there is no assumption that a 512-bit recurrence is
faster.

The input and both state banks are binary64 memory objects in the original
implementation. Keeping a completed binary64 result in an SSE/AVX register
instead of reloading it cannot add precision. Each candidate bank is written before the swap, as in the original recurrence;
coordinates outside the active order retain their initial bits in both banks.

## Finite decision and exceptional values

The already-established finite-decision implication remains applicable:
every active `n[i]` contributes `a[i]*n[i]`, including zero coefficients. A
NaN state produces a NaN term; an infinite state produces an infinity or NaN.
Once a serial sum becomes nonfinite, later IEEE additions cannot make it
finite. Thus finite completed `v` implies finite active `n[i]`.

Reordering independent computations can choose different NaN payloads. When
`v` is nonfinite, the optimized block exports the accepted prefix and invokes
the unchanged scalar step on the failing input. The active bank is still the
old bank. The scalar step overwrites the complete candidate bank in its
original operation sequence, producing the original rejected-bank bits,
coordinate behavior and nonfinite monitor update. This is a correctness
path, not an approximate substitute.

Masked sticky exception flags are unions of exceptions raised by the same
active operation graphs. Re-executing a rejected graph does not clear flags.
All candidate coordinates enter the decision products before a bound test,
so a subnormal candidate has already been consumed by floating-point arithmetic.
The scalar fallback handles unmasked exceptions because lane scheduling and
re-execution would otherwise change synchronous trap ordering. No claim is
made that the optimized path preserves the number of machine instructions.

## Local decision in the isolated SIMD units

The original `sdm_normal_decision(v)` returns exactly
`signbit(v) ? -1 : 1`; it has no other operations or side effects. The four
isolated SIMD translation units opt into that same expression in the common
acceptance header. Both branches therefore return the same integer for every
binary64 representation, including negative zero, without adding a floating
arithmetic operation. The scalar/default expansion continues to call the
original helper. Existing environment and alias fallbacks remain ahead of the
specialized execution paths.

This change also covers the older order-four and order-six vector loops. It
removes an external call across which the compiler otherwise spills live
values. Its equivalence follows directly from the original helper's body;
the performance claim is measured separately. The frozen oracle retains the
original header and original helper call.

## Bounds and maximum tracking

Parallel bound comparisons are enabled only when every active bound is
nonnegative finite normal or positive zero. Their bit classifications use
integer operations, so even a signaling-NaN bound does not raise an early
exception in the gate. Unusual bounds use the scalar block. Active candidates
are finite by the implication above. The vector comparison mask is inspected
in ascending coordinate order; the first failing coordinate is identical.

Monitor maxima use `max(abs(candidate), old_maximum)` with the previous
maximum as the second operand. The scalar conditional replaces the old value
only when the new magnitude is greater; the instruction returns that same
operand for each comparison outcome, retaining the old bits on equality.
Initial monitor maxima with unusual bit patterns take the scalar path. DAZ
and FTZ also select scalar, avoiding the hardware maximum's subnormal
behavior. Absolute value clears only the sign bit.

Integer monitoring retains the original field widths and operation sequence:
28-bit history, window counts, overload indices, run lengths and saturating
counters. `first_overload_frame` uses the context's preincrement frame, not
the independently maintained monitor frame count. Existing saturation markers
are preserved unless an actual saturation assigns one. A frame-limit precheck
proves that the subsequent context-frame increment cannot wrap.

## Caching and aliases

The argument assumes initialized context/monitor objects and valid object
spans as declared by the internal API, including readable active bounds.
Input sample values themselves may be nonfinite.

No new `restrict` promise is imposed on callers. A byte-range gate checks
the context, attached monitor, full input/output spans, committed count,
active bounds, optional coordinate and optional peak. Any overlap selects
the unchanged scalar block. Range comparison uses address subtraction to
avoid overflow when computing end addresses; span multiplication is checked.
The coefficient arrays already have an immutable lifetime contract in
`sdm.h` and are not modified.

On the disjoint path, no operation within the call can read a cached field
through another argument. It is therefore valid to keep bank, frame, previous
decision, peak and monitor maxima local until return. Integer monitor fields
are updated directly for each accepted frame, in their original order; no
whole-monitor copy or padding write is needed. State vectors remain live
across samples, while each calculated bank is stored once without the former
overlapping loads. The committed count is exported once with the number of
fully accepted frames.

The fallback also corrects two preexisting vector alias defects: peak pointing
at the input sample, and input pointing into a state bank. These are demonstrated
by the independent oracle harness; no change to scalar behavior is required.

## Return-path invariant

Before each sample, the local active state, previous decision, counters and
monitor equal the scalar state after the accepted prefix. The input is read
once. Nonfinite input is rejected before updating peak; peak is updated before
the envelope and frame-limit checks. Those early failures do not calculate a
new bank. Arithmetic rejection uses scalar re-execution as described above.
Finite bound rejection leaves the calculated inactive bank, retains the old
active bank and decision, and does not update the monitor or output.

On acceptance, the sign bit of `v` selects exactly the scalar decision,
including negative zero. Only then do the bank, monitor, frame and output
advance. Export on every exit therefore yields the same output prefix, both
banks, decision, monitor, peak and error metadata. Zero-frame blocks retain
the original validation and committed-count write; they perform no recurrence
or monitor/peak update beyond any effect of that original aliased count write.
This completes the induction over all block boundaries and error exits.

Differential, sanitizer and compiled-instruction evidence complements this
argument; it does not replace it. The finite tests are extensive, not an
enumeration of all possible binary64 states.
