# P10 closeout: set the criteria for the last two gates, then rule on them

Work in the attached tree, a `git archive` snapshot with no `.git`; the
dispatch note carries its filename and SHA-256, since a document inside the tree
cannot name its own tree's hash. It contains P00 through P10 including the
corrective and revalidation rounds.
`docs/dsd/sows/P10.md` remains the statement of work and
`docs/dsd/DSD_DESIGN.md` the authority.

P10's release disposition is `INCOMPLETE` with all three mastering profiles
unqualified and promotion blocked. Two gates remain `UNRUN`:
`representative_hardware_1hour_per_profile_isa` and
`independent_realworld_corpus`. Both now have evidence that was executed on real
hardware, recorded in `tests/dsd/results/P10_soak_1hour_sse2_2026-10-10/` and
`tests/dsd/results/P10_realworld_corpus_2026-10-10/`.

Neither gate carries a stated acceptance criterion. `qualify_p10_corrective.py`
hardcodes both to `UNRUN` and inspects no evidence path, and the second gate
does not appear in the design at all: it entered through P09's own account of
what it had not run. We left that code untouched, because writing the standard
for a run we were also performing would be self-certification.

**Outcomes wanted:**

1. An acceptance criterion for each of the two gates, derived from the design
   and the SOW rather than from the evidence that happens to exist or from this
   brief, and recorded where the collector can apply it.
2. A ruling on the committed evidence against those criteria. Whether it
   discharges the gates, partly discharges them, or does not, is yours to
   determine.
3. A decision on whether `minimum_attenuation_db` reporting only a lower bound
   is a defect worth correcting, and a correction if it is.
4. The existing gates still hold, and no profile is promoted by this round
   unless its criteria are genuinely met and demonstrated.

**A rejection is a good outcome if that is what the evidence warrants.** If the
runs are too short, the material too narrow, the coverage incomplete, or the
measurement method unsound, say so and state what would suffice. We would
rather rebuild the evidence than have a gate marked passed on our account.

## What we believe, and why you should not take our word for it

Everything in this section is our reading of evidence we gathered and
interpreted ourselves. We have been wrong in this project before, including
three mechanisms proposed and withdrawn during the P10 corrective round and two
misreadings during this work that we caught only by looking again. Treat all of
it as a report to be checked, not a finding to be inherited. You must make these
determinations.

- The one-hour soak ran 3600 audio seconds per profile, three of three rates,
  and we believe every substantive admission check passed: no nonfinite state,
  no guard-bound crossing, exact frame accounting, and the DSD64 28-bit window
  guarantee holding across 10,160,639,973 windows. The harness nonetheless
  reports `FAIL`, on `release_sequence` alone, which `soak_p10.py` defines as
  `seconds == 1800 and segment == 60`. We read that as an inapplicable
  assertion rather than an observed defect, since the harness models no
  one-hour soak, but that reading is exactly the sort of thing we could have
  wrong.
- We believe the ISA-family multiplier is one at P10, because `src/sdm_x86.h`
  selects kernels at compile time and a build without `-march` defines only
  `__SSE2__`. If that is right, one family satisfies the gate today and P11
  reopens it; if it is not, the soak covers less than we think.
- The corpus is eighteen commercial DSD releases, six per rate, none produced by
  this project or any SoX writer. Fourteen were admitted at unity reference, and
  the four rejections are the sources mastered hottest. We believe the level
  results show risk R7a does not occur on real material, since reconstructing
  each output reproduced its source excerpt's level.
- We believe admission at unity reference is decided by source level against the
  SACD reference, and that this evidence establishes no interpolation
  contribution whatsoever. The envelope of 0.5 is -6.020600 dBFS, and in
  preserve reference DSD full scale maps to 1.0, so the ceiling sits at the
  convention section 5.4 describes. Each rejected excerpt's reconstructed source
  maximum exceeds 0.5 by itself: 0.500128, 0.510970, 0.536729 and 0.548224. The
  gain ladder bounds each true requirement to the interval between the step that
  failed and the step that admitted, and for all four the attenuation implied by
  level alone falls inside that interval, so a contribution of exactly zero is
  consistent with every measurement.
- This round made two successive errors here that we want visible rather than
  tidied away. We first described interpolation overshoot as the reason real
  material fails, which the level measurement does not support. We then
  attributed 0.06 to 0.38 dB to overshoot, which was worse: those figures were
  the gap between the level-implied minimum and whichever ladder step happened
  to succeed, so they measured the ladder's step size, not the DSP. Quantifying
  overshoot needs the maximum post-interpolation sample against the maximum
  source sample. `report.peak` tracks the former but `src/pcmdsd.c` logs it only
  on the failure path, so successful runs surface nothing and we have no figure.
  Surfacing it on success, or a harness mode feeding an external file through the
  corrective round's stage observer, would measure it.
- Two scope limits on the above, both of which we think matter. It describes
  preserve-reference DSD remodulation, where the tag is 1.0; an ordinary PCM
  source is scaled by 0.5 and carries roughly 6 dB more headroom, which nothing
  here characterises. And amplitude 0.5 separated the two groups across these
  eighteen sources without exception, but that is an observation about this
  corpus, not an admission rule: the design tests after interpolation and
  reference scaling by design, so a source under 0.5 may still exceed the
  envelope and one over it is not guaranteed to be rejected. This corpus
  exercises neither case, since the admitted all peak at or below 0.4462 and the
  rejected all exceed 0.5.
- We believe `minimum_attenuation_db` is a lower bound rather than a
  requirement, because `fail_stream` in `src/pcmdsd.c` records only the first
  failure under `if (!p->error)` and derives the figure from that one sample's
  value. Measured consequence: `Bone Machine` reports 0.0102 dB, still overloads
  at 0.5 dB, and is admitted only at 1.0 dB, against a measured sample peak of
  0.5483. We think a user trusting the field would under-attenuate and fail
  later in the stream. The code reading is ours and the inference from it is
  ours.
- We did not measure integrator state maxima or nonfinite counts over the
  corpus. No harness mode accepts an external audio file, so a CLI run cannot
  observe them. If your criteria require that coverage, the corpus evidence is
  insufficient as it stands and a harness mode would be needed. Analysis-v1 spur
  and residual measurement was also not re-run against this material.

## Situational notes, possibly wrong or incomplete — trust the tree over them

- Measurement tooling we added is `tests/dsd/corpus_realworld.py` and
  `tests/dsd/dsd_windows.py`, both in `EXTRA_DIST`. The second reads DSF with
  numpy because `reference/verify.py` walks one bit at a time and is
  impractical at hundreds of millions of frames; it carries a `--self-check`
  that asserts bit-identical agreement with that oracle, and we ran it before
  trusting any measurement. The oracle remains the authority.
- The corpus audio is not in the tree and should not be. `sources.json` records
  release identity, rate and excerpt hashes only.
- The collector already has an evidence-driven pattern: sibling gates are built
  by `make_gate(kind, ok, ..., evidence=...)` with `ok` computed from reading
  the recorded file, falling back to `UNRUN` only when it is missing. The two
  gates in question skip that and are assigned unconditionally, under a comment
  saying they are mandatory and "never implied by a 30-minute nominal synthetic
  soak or a previous version's read/repack benchmark". We read that as
  deliberate, so wiring them to evidence looks like a decision to be taken
  rather than an omission to be patched, but that is our inference about
  someone else's intent.
- `make check` and `make check-dsd` pass on this tree, with the inherited floor
  at 36 pass / 0 fail and all six P10 groups passing.
- P10's throughput gate and a corrective read/repack remeasurement both pass on
  a prepared host; a passing throughput gate is not a passing phase.
- The gate is 5% median regression, admissible only when noise is under 2%, and
  the verdict comes from the confidence interval rather than the median. See
  `tests/dsd/BENCHMARKING.md` and `tests/dsd/benchprep.sh`.
- Please return a source tree rather than a built one, keep machine-specific
  paths out of recorded results, leave previously recorded evidence as
  delivered, do not ship copies of this brief in the tree, and flag anything
  here you find to be mistaken.
