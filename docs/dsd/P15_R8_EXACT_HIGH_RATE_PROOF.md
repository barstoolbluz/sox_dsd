# P15 R8 — independently replayed high-rate composite SRC interval

Date: 2026-10-19. Original source archive `sox_ng-P15-adjudicate-cc399928.tar.gz`, SHA-256 `d058b3908817e01e937f49e0dfeee7194d847aae74f625043e881d8b8f0e9210`.

## Certified result

**Independent ideal-operator spectral PASS for precisely one complete canonical interval:** `dsd256.mastering_v2.pcm384000`, `decode.mastering.v2.dsd256`, 384000 Hz output, passband `[0,1000] Hz`. The exact native DSD rate is 11,289,600 Hz. The source-bound chain comprises 5 halfband-by-2 stages, 1 further /2 stage, a 1005-tap 2x interpolator and a 4160-tap 160/147 SRC stage. There are 9408 complete reverse alias paths, 9407 unwanted paths and a unique wanted path. The ten adjacent 100 Hz segments cover the entire canonical interval, with no gaps. Each segment passed *independent recomputation* from source-captured tap words and the original spectral bounds, using the original exact rational path enumerator and the strict original policy.

Source/digital-frequency identities and all method source hashes are bound in the machine-readable receipt `tests/dsd/results/P15_R8_INDEPENDENT_2026-10-19/highrate_0_1000.json`. The recorded PASS is not a sampled FFT result, not a historical PASS-flag replay, and not a claim about floating-point FFT4G execution or the final ELF.

## New lemma: outward dyadic compression

For exact rational enclosure `l <= x <= u`, let `G=2^192` and define `L=floor(lG)/G`, `U=ceil(uG)/G`. Elementary properties of mathematical floor and ceiling imply `L <= l <= x <= u <= U` even for negative rationals. Thus replacing every accepted `FastComposite.stage_bounds` pair `(l,u)` with `(max(0,L),U)` retains the nonnegative transfer-amplitude enclosure. Every subsequent composite operation is monotone in nonnegative stage upper/lower magnitudes: wanted lower is a product of lower bounds, wanted upper is a product of upper bounds, and unwanted upper is a complete nonnegative majorized path sum. Lower bound of wanted-minus-unwanted uses subtraction of a sound upper. Neither rounding nor pruning can reduce an alias upper or increase a wanted lower. The R6 and R7 FIR, exact source/operator-binding, path enumeration, halfband and finite-difference lemmas remain part of this theorem's explicitly stated trusted base.

R8 does not use binary64 arithmetic in its acceptance comparisons. Exact `Fraction` floors/ceilings and all alias sums preserve strict inequalities for original ±0.0001 dB and `<1e-8` stop/alias limits. The 192-bit unit is enormously smaller than the available safety margins; this *statement about margin* is not used to assert correctness, because directionality of the rounding is sufficient on its own.

## Reproduction

Apply the prior R6+R7 additive proof distribution to an unmodified, SHA-verified `cc399928` source and then unpack this R8 additive archive. In the `sox_ng/` root:

```bash
PYTHONPATH=tests/dsd python3 -m unittest -v test_p15_r8_dyadic
PYTHONPATH=tests/dsd python3 tests/dsd/p15_r8_highrate_witness.py \
  --verify tests/dsd/results/P15_R8_INDEPENDENT_2026-10-19/highrate_0_1000.json
```

The second command independently recomputes all 10 exact rational leaf enclosures, enforces canonical frequency coverage and binds exact source+method identities. It may require several minutes on a modest CPU. An independently failing leaf returns nonzero instead of a PASS. Additional result generation is resumable via `--produce PATH --step 100` but must never replace the immutable delivered proof accidentally. The included tests deliberately corrupt schema, certificate state, method SHA and coverage endpoints, and all are refused.

## Exact limits of the result

The prior R7 distribution independently verified 87/11516 canonical jobs. This R8 distribution adds exactly one different canonical job, for 88/11516 total independently qualified jobs across the combined records. The remaining 11428 jobs are not independently qualified merely because their historical aggregate receipts say PASS. The independent global ideal-operator spectral mathematics gate is **CONDITIONAL**. The physical/FFT4G/final-ELF gates remain as they were. No mathematically correct statement in this document promotes a local proof into full-campaign approval.

**Why a one-time source proof alone is not enough:** The original 11,516 receipts contain aggregate numeric bounds, without source-bound independent mathematical derivations for every leaf, and the original generating prover revision is not fully attested. A theorem about the current checker does not retroactively establish that an unrecorded historical computation used that exact checker. For the spectral gate to PASS, each remaining canonical interval needs a valid independently qualified certificate, or a separately derived analytic theorem whose hypotheses apply to the exact captured stages and that covers the entire remaining continuum. Neither is supplied here.
