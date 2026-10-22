# Pre-registration: DSD512 modulator order study

Written **before any candidate exists**, and committed before any measurement,
so the acceptance criteria cannot be chosen to fit a result. Four orders,
several designs and three metrics leave ample freedom to pick a winner after
the fact; this document removes it.

Status: protocol only. Nothing here authorizes a capability, qualifies a
profile or changes a default.

## Question

Which modulator architecture gives the best measurable fidelity at DSD512
across an explicitly chosen signal bandwidth?

Not "repair a 37 dB defect". That premise is withdrawn: the asymmetry which
prompted this study was an artifact of our own measurement, whose stimulus
was quantized to signed 32-bit PCM before encoding and so sat on a residual
floor near -200.43 dBFS. Re-measured with binary64 input the order-reduction
penalties are comparable, 40.99 dB at DSD512 against 37.47 dB at DSD1024,
and no defect requires correction. See
`tests/dsd/results/P20_OPERATOR_QUALIFICATION_2026-10-22/README.md`.

The live question is different and better. The seventh-order candidate
reuses historical DSD256 CLANS-7 coefficients and was selected because it
passed the sustained population and stability gates that the eighth-order
candidates failed. Its -163 dBFS residual is an observed property, not a
chosen target, and -163 dBFS is not a ceiling on what is achievable. The
relevant design variable is the complete noise transfer function, not merely
its order.

One measured fact frames the stakes: **99.9686% of that residual power lies
between 40 and 88.2 kHz, and below 40 kHz it is about -198 dBFS.** Against a
40 kHz mastering passband the order reduction costs almost nothing. The
penalty matters only if the extended band is used, which is exactly the band
this study examines.

## Hypotheses, stated so they can fail

- **H1** A purpose-built design of order < 7, optimized for the chosen band
  at this clock, achieves lower in-band noise across 0-100 kHz than the
  inherited CLANS-7 at order 7.
- **H2** Stability margin increases monotonically as order falls.
- **H3** Cost falls roughly linearly with order.

**What makes CLANS-7 the winner.** If no lower-order candidate beats it on
the chosen-band aggregate while also clearing stability screening, H1 is
rejected and the inherited design is retained. That outcome is a real result,
not a failed experiment, and must be reported as such.

The objective is to find the best DSD512 noise shaper, not to defend seventh
order or to reproduce its historical coefficients.

## The measurement chain, and why the existing one will not do

`p20_audio_compare.py` decimates 128:1 to 176,400 Hz, Nyquist 88.2 kHz,
through the mastering FIR whose passband is 40 kHz. **It cannot observe
0-100 kHz and must not be used for this study.**

This study uses the wideband DSD512 reconstruction:

    decode.wideband.v1.dsd512   22,579,200 -> 705,600 Hz, 5 stages
                                pass 282,240 Hz, stop 352,800 Hz
                                Nyquist 352,800 Hz

Analysis band 0-100 kHz sits well inside that passband. The chain, its
coefficient digests and the analysis window are fixed for every candidate and
recorded per run.

## Fixed across all candidates

Native clock 22,579,200 Hz. Source rate 176,400 Hz. Reconstruction
`decode.wideband.v1.dsd512` at 705,600 Hz. Scalar kernel for all numerical
comparison; all five ISA tiers for correctness only. One analysis
implementation, one window, one normalization. Stimulus set digest-pinned
before use.

## Varies

Modulator order 4, 5, 6, 7, and the coefficient design within each order.
Controls are the two existing candidates: `encode.mastering.v1.dsd512`
(8th order, inherited, fails the sustained population gate) and
`encode.mastering.v2.dsd512` (7th order CLANS-7, passes it).

## Stimulus set

**Binary64 throughout, never quantized to int32 before encoding.** That
quantization is what floor-limited the measurement which prompted this
study, at about -200.43 dBFS, and it would hide any result better than that
floor. Every stimulus is generated and retained as f64 and its digest
recorded.

A single 997 Hz tone is insufficient and was the other weakness of the
earlier diagnostic. Required, each digest-pinned:

1. Multitone, logarithmically spaced across 0-100 kHz, crest-controlled.
2. Band-limited noise, 0-100 kHz, at -6 and -20 dBFS.
3. Near-fullscale content at 0.49, just inside the 0.5 envelope.
4. Both DC polarities at 0.49.
5. The 997 Hz tone, retained only so results tie back to prior numbers.

## Phase order, and this gating is not negotiable

The DSD1024 lesson is that short tests miss runaway: its eighth-order
candidate looked sound and went nonfinite at about 33.1M native frames. A
lower-order design can therefore win a fidelity comparison on a stimulus that
never excites it.

**No candidate receives a fidelity number before it clears Phase 2.**

### Phase 1, preregistration
This document, committed.

### Phase 2, stability screening
Per order: amplitude sweep to locate the latch threshold, both DC polarities,
and P10-method training to derive frozen guard rows. Holdout never tunes a
bound. Deliverable is a stability margin per order: peak state as a fraction
of its own ceilings, and the input level at which it first latches.

Gate to pass: no nonfinite state, no monitor overload, population within the
training band 4 to 24, and a derived guard row that holdout does not violate.

### Phase 3, fidelity across 0-100 kHz
Through the wideband chain. Reported in explicit sub-bands rather than one
aggregate, because a lower order may trade baseband for the top octave and
that trade is the question:

    0-20 kHz   20-40 kHz   40-100 kHz   100-150 kHz   aggregate

Characterize to at least 0-100 kHz and preferably 0-150 kHz. The wideband
chain's 352,800 Hz Nyquist accommodates both.

Measured per candidate, not only noise power: spectral noise, distortion,
**idle tones**, numerical stability, bitstream compliance and computational
cost. Idle-tone behaviour is specifically included because low-order shapers
are prone to it and a noise-power aggregate will not reveal it.

Results are **sampled spectra, not interval-certified**, consistent with
`amendments/CONTINUUM_EXTREMA_WAIVER_2026-10-21.md`. No continuum claim is
made or implied.

### Phase 4, cost
Paired interleaved runs, pinned to a prepared core, 20,000-sample bootstrap
on paired ratios, the method already used for the packed-input benchmark.
Existing data point for calibration: 8th order 0.935 cpu-s against 7th order
0.872 cpu-s on identical input, about 7% per order.

### Phase 5, sustained soaks, survivors only
3,600 seconds per surviving candidate per program, uninterrupted, dedicated
cores, with the sustained population band 7 to 22 enforced. Soaking every
candidate is wasteful; only those clearing Phase 2 and competitive in Phase 3
proceed.

## Ranking rule, declared in advance

Candidates are ordered by 0-100 kHz aggregate in-band noise, **among those
that clear Phase 2 and Phase 5 only**. Cost breaks ties beyond 1 dB.
Stability margin is reported but does not rank, except that any candidate
whose latch threshold is below 0.49 is excluded outright regardless of
fidelity.

A candidate that wins on fidelity and fails a soak does not win.

## Division of labour

**Model:** noise transfer function synthesis per order, optimized for the
extended band; the coefficient words; and any harness extension needed for
multitone and sub-band analysis through the wideband chain.

**Operator:** all execution. Sweeps, screening, soaks, timing, ISA matrix,
and the evidence.

This is therefore at least two rounds, not one.

## Abort conditions

- **Discharged.** The residual asymmetry was indeed an artifact of our
  measurement, answered 2026-10-22, and the study is reframed accordingly
  rather than abandoned. The reframing is the authority's own
  recommendation.
- No candidate of order < 7 clears Phase 2. H1 is then untestable and the
  study stops with that reported.

## What this cannot conclude

It cannot qualify a profile. Whichever design ranks first still requires
frozen guards, holdout, a sustained soak and a certificate before any
capability could cite it.

It cannot establish audio quality. There is no listener test and no device
in this protocol, and sampled noise power is not a fidelity certificate.

It cannot speak for DSD1024. The clock, the oversampling ratio and the band
all differ.

It must not change production code or relax an existing acceptance gate on
the strength of short-window fidelity results. The CLANS-7 candidate remains
the qualified experimental reference throughout, and a better short-window
number is not grounds to displace it.
