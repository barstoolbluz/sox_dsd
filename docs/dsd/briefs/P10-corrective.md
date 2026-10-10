# P10 corrective round: classify the overload, then qualify

Work in the attached tree, `sox_ng-P10corr-8572e029.tar.gz`, SHA-256
`027b0872cfe9e21910424f9307afebfb3e5f273c0530e7d92dc70e4ca88db649`, no `.git`.
It contains P00 through P10 as delivered, with P10's qualification failed and
all three mastering profiles unqualified and unpromoted. `docs/dsd/sows/P10.md`
remains the statement of work and `docs/dsd/DSD_DESIGN.md` the authority.

P10's 30-minute release sequences did not complete. All three rates failed with
`LSX_PCMDSD_INTERPOLATION_OVERLOAD` at a post-interpolation peak of
0.5032625406 against an envelope of 0.5 plus two source-int32 LSBs. The
modulator was healthy to that point: zero 28-bit excursions across 679,008,289
windows, minimum population 7 ones.

## The determination to evaluate

A human reviewer has read the design and the SOW and reached the judgement
below. **Your first task is to evaluate it, not to execute it.** Say whether it
is the proper guidance, and where it is not, with reference to the design and
the tree rather than to this brief.

> Primarily a test-fixture qualification issue, not a demonstrated DSP design
> defect. The P10 design explicitly anticipates this condition and requires the
> encoder to reject it.
>
> I checked the original design specification and P10 SOW. Section 7.2
> establishes three relevant rules:
>
> 1. The admitted modulator-domain peak is 0.5, plus a negligible
>    representation margin.
> 2. Admission is determined after interpolation and reference scaling, not
>    from the original PCM sample peaks.
> 3. Interpolation overshoot must cause an explicit failure, not clipping,
>    normalization, or an automatic change of modulator.
>
> The agent reports a post-interpolation peak of 0.5033. That exceeds the
> specified envelope by 0.66%, or approximately 0.057 dB. If the measurement is
> correct, INTERPOLATION_OVERLOAD is the required behavior.
>
> **One issue still needs verification.** The original noise peaks at 0.7. After
> the intended 0.5 reference scaling, its sampled peak would be 0.35. The
> reported 0.5033 therefore represents a 1.438x increase relative to that value.
> Interpolation can produce intersample overshoot, particularly with noise. But
> the agent should independently verify that the SRC stages have correct unity
> gain and that reference scaling occurs exactly once. An unintended gain error
> would make this an implementation defect rather than a fixture issue. The
> agent's inferred sigma of 0.118 is also not established by the first
> threshold-crossing time. It needs to measure the post-interpolation
> distribution directly.
>
> **What I would instruct the implementing agent to do**
>
> - Preserve the 0.5 envelope. Do not relax it to make this test pass.
> - Verify the actual sample peaks and RMS at every stage, including the
>   prefilter, interpolation, and scaling.
> - Retain the original 0.7-amplitude noise fixture as a regression test for
>   clean overload rejection, assuming the measured overshoot is independently
>   confirmed.
> - Create a separately versioned nominal noise fixture with documented
>   headroom, and run the complete holdout and soak qualification against it. Do
>   not silently replace or erase the failing corpus.
> - Verify that explicit PCM attenuation makes the original stimulus pass and
>   that modulation stability remains acceptable.
> - Keep the mastering profile unpromoted until every required nominal
>   qualification succeeds.
>
> **Is the design itself too restrictive?** Possibly, but this test does not
> establish that. The original design deliberately chose a conservative
> admission envelope. Its practical consequence is that some otherwise valid PCM
> signals can be rejected because interpolation creates peaks above the nominal
> DSD modulation level. That is a product-policy tradeoff, not inherently
> incorrect DSP. A future profile could admit a higher peak if independent
> stability, distortion, and long-duration tests justify it. One 0.5033
> excursion is insufficient evidence for changing the contract.
>
> **My decision:** Treat this as a fixture-classification problem, conditional
> on verifying the interpolation gain. The original noise segment belongs in the
> expected-overload corpus, not the nominal passing soak. Correct the
> qualification evidence and fixture classification without changing the
> encoder's admission policy. If independently validated, normally admitted
> material still fails systematically, reopen the design decision.
>
> There is no justification here for redesigning the modulator, increasing
> state bounds, introducing automatic gain reduction, or abandoning P10.

## Your second task, if the guidance is sound

Resolve the questions it leaves open, and then qualify.

1. **Settle whether this is a fixture issue or a gain defect.** Measure peak
   and RMS at every stage of `source -> R SRC -> centered non-decimating FIR at
   R -> native SRC -> scale`, and establish that each SRC stage has unity gain
   and that reference scaling is applied exactly once. If a gain error exists,
   this is an implementation defect and the classification above does not hold.
2. **Measure the post-interpolation distribution directly** rather than
   inferring it. The 1.438x ratio from 0.35 to 0.5033 is either ordinary
   band-limited intersample overshoot or evidence of excess gain, and only the
   measured distribution distinguishes them.
3. **Reclassify the fixtures** as the guidance directs: the 0.7-peak noise
   segment becomes an expected-overload regression case, and a separately
   versioned nominal fixture with documented headroom carries the qualification.
   Preserve the failing corpus and its results.
4. **Qualify against the nominal fixture**, completing the holdout and the
   30-minute sequences, and confirm that explicit PCM attenuation admits the
   original stimulus with acceptable stability.
5. **Keep the profiles unpromoted** until every required nominal qualification
   passes, and report an honest negative again if it does not.

Return a complete source tree with `docs/dsd/handoffs/` entries for this round,
your evaluation of the guidance stated plainly, and a regenerated
`tests/dsd/results/P00/P00_SHA256SUMS.txt` if file hashes move.

## What we verified here, so you need not repeat it

- §7.2 exists at `docs/dsd/DSD_DESIGN.md:571` and line 573 states all three
  rules, including that the margin is "two source-int32 LSBs in normalized PCM,
  not an arbitrary percentage", and that overshoot during interpolation can
  occur "even though its stored PCM samples did not exceed full scale". The
  design anticipates this condition explicitly.
- The implementation is faithful to that: `src/pcmdsd.c:96` sets
  `envelope = .5 + scale*(2./SOX_SAMPLE_MAX)`, and `scale` is validated to be
  only 0.5 or 1.0.
- The failure is the overload path and not a state breach: `failure=2` is
  `LSX_PCMDSD_INTERPOLATION_OVERLOAD`, and the recorded `coordinate` is
  `UINT_MAX`, which only that path emits.
- It occurs 0.599 s into segment 4 of `test_p10.c:soak_source`, the
  `0.7*uniform` noise segment, by arithmetic on the recorded frame counts.
- Reproducing `soak_source` independently gives that segment a raw post-ramp
  peak of 0.699991 and RMS 0.403992, with 28.5% of samples above 0.5. The raw
  source is therefore ±0.7, and the 0.5 reference scaling is applied downstream
  rather than in the generator.
- The arithmetic in the guidance is correct: 0.653% over the envelope, 0.0565
  dB, and a 1.438x ratio from 0.35. The encoder's own
  `minimum_attenuation_db` field already reports 0.0565 dB, so it states the
  attenuation that would admit the stimulus.

## Three mechanisms we proposed and withdrew

Offered in case they save you from the same mistakes. Each was asserted before
being measured, and each is wrong. Do not inherit them.

- That `tests/dsd/p10_corpus.py` defaulting to `dbfs=-6` (peak 0.501187 rather
  than exactly 0.5) caused the failure. The soak does not use that file at all;
  its generator is `test_p10.c:soak_source`.
- That the "defined representation margin" was nowhere defined. It is defined,
  in the design at line 573 and in the implementation at `pcmdsd.c:96`.
- That the noise segment's distribution gives sigma 0.202, needing 2.47 sigma
  to reach 0.5, with roughly 70,000 exceedances expected per segment. That
  model predicts failure 0.1006 s into the segment; it actually failed at
  0.599 s, so the model is wrong by a factor of about 586. The sigma 0.118
  implied by the crossing time is an inference from a single sample, which is
  why task 2 asks for a measurement.

Situational notes, possibly wrong or incomplete — trust the tree over them:

- P10's own handoff states that the next permitted work is P10 qualification
  continuation rather than a transition to P11, and that no coefficient change,
  guard increase, limiter, hidden fallback or default activation is justified by
  the present results. This round is that continuation.
- P10's throughput gate passes, measured here against P09 on a prepared host:
  sixteen of sixteen workloads, worst +1.02%. A passing throughput gate is not
  a passing phase.
- The gate is 5% median regression, admissible only when noise is under 2%, and
  the verdict comes from the confidence interval rather than the median. See
  `tests/dsd/BENCHMARKING.md` and `tests/dsd/benchprep.sh`.
- Please return a source tree rather than a built one, keep machine-specific
  paths out of recorded results, and do not ship copies of this brief in the
  tree.
- Please leave previously recorded evidence as delivered, and flag anything here
  you find to be mistaken.
