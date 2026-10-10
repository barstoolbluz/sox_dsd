# P10: recover the throughput gate, and build the PCM arm of the corpus

Work in the attached tree, a `git archive` snapshot with no `.git`; the dispatch
note carries its filename and SHA-256. It contains P00 through P10 including the
corrective, revalidation and ratification rounds, with your ratification
adjudication integrated. `docs/dsd/sows/P10.md` remains the statement of work,
`docs/dsd/DSD_DESIGN.md` the authority, and
`tests/dsd/reference/p10_ratification_criteria.json` the executable criterion
your last round wrote.

P10 stands at `INCOMPLETE`, profiles unqualified, promotion `BLOCKED`.
`representative_hardware_1hour_per_profile_isa` is `PASS`.
`independent_realworld_corpus` is `PARTIAL`. Two things now stand in the way,
and this round is both of them.

## 1. The read/repack throughput gate no longer passes

Your `minimum_attenuation_db` correction is a real improvement and we want to
keep it: the previous message invited a reader to under-attenuate. It also costs
6.81% on `dff-6ch-repack-small`, interval [+6.54%, +7.04%] at 0.41% measurement
noise, against a 5% limit. The interval sits entirely above the limit, so this
is a failure rather than an inconclusive measurement.

We measured the delivered tree, then the same tree with only `src/pcmdsd.c` and
`src/pcmdsd.h` reverted and everything else held constant. The regression goes
away: the workload returns to -0.23%. `dsf-6ch-repack-small` moves with it,
+3.01% to -0.28%. Evidence and method are in
`tests/dsd/results/P10_ratification_throughput_2026-10-10/`.

The changed branch runs only after the encoder has already failed. It cannot
execute during a DFF read and cannot alter an output bit, so the cost is not the
code being run. `docs/dsd/OPTIMIZATION_BACKLOG.md` has recorded this workload
moving under phases that touch no read code five times now, in both directions
and never explained; this is the first time one file could be reverted to remove
one regression with everything else fixed.

**Outcome wanted:** the improved diagnostic, and a passing gate. Whether that
means holding this translation unit's shape constant, moving the message
elsewhere, making the fragment read loop insensitive to placement, or something
we have not thought of, is yours to judge. If the honest answer is that the
diagnostic cannot be kept without the regression, say so and say which you would
give up.

## 2. The corpus needs its `PCM_AUDIO` arm

Your criterion requires both source domains. The committed corpus covers
`DSD_NATIVE` only: eighteen commercial DSD releases, six per rate, measured
through the real CLI graph. The `PCM_AUDIO` arm does not exist.

**Outcome wanted:** the runnable driver for that arm, implementing your own
criterion rather than our reading of it. We will execute it on the hardware and
the material, and report what it measures.

`tests/dsd/results/P10_pcm_arm_material_2026-10-10/` inventories what is on that
host: nineteen commercial 24-bit stereo FLAC releases across 44100, 88200,
96000, 176400 and 192000, ten in the 44100 family and nine in the 48000 family,
with per-source STREAMINFO MD5s and the host constraints. Three of those
constraints shape any design: the audited executable has no FLAC handler and
rebuilding it with one would change the configuration every committed gate was
measured under; the 176400 material sits in a read-only library that must not be
mutated, so sources have to be copied out before use; and everything is on sshfs,
so each source wants reading once rather than repeatedly.

`tests/dsd/corpus_realworld.py` and `tests/dsd/dsd_windows.py` are the existing
`DSD_NATIVE` driver and its bitstream reader. Extend, replace or ignore them as
you see fit. The reader is validated bit-exactly against
`reference/verify.decode_dsf` by its own `--self-check`, because that oracle
walks one bit at a time and is impractical at hundreds of millions of frames.

## 3. The existing gates still hold

36 pass / 0 fail, `make check` unchanged, all six P10 groups passing, your
eighteen adversarial receipt tests passing, and no profile promoted.

## What we believe, and why you should not take our word for it

This is our reading of evidence we gathered and interpreted ourselves. In the
last two rounds we framed a result wrongly twice on one question and a reviewer
corrected us both times. Treat all of it as a report to check.

- We believe the 6.81% regression is caused by your `pcmdsd.c` change, because
  reverting that one file removes it with everything else constant, on a
  prepared host at 0.41% noise with a 0.0% host probe beforehand.
- We believe the mechanism is the linked image's layout, growing that
  translation unit and moving the read loop's placement or alignment. **That
  part is inference, not measurement.** We have never profiled this workload.
  The demonstrated fact is only that reverting the file removes the regression.
- We believe our `DSD_NATIVE` arm used the right reference convention, preserve
  for DSD-origin reconstruction, and that your criterion's `sacd` reference is
  the correct one for `PCM_AUDIO`. On one 20-second PCM excerpt, source peak
  -2.90 dBFS and RMS -22.88 reconstructed at -2.89 and -22.88 under `sacd` and
  at -8.92 and -28.90 under `preserve`, the latter 6.02 dB low.
- We believe the inventory is accurate but do not claim it is exhaustive. It is
  what we found and verified, not a survey of the host.
- We believe the 176400 releases' narrow provenance is worth your attention when
  weighing independence: all five are Neil Young, one of them credited to Neil
  Young & Crazy Horse. They are distinct commercial albums from different years
  by two transfer routes, DVD-Audio and HDTracks, but they share an artist and
  catalogue lineage.

## Situational notes, possibly wrong or incomplete — trust the tree over them

- Three small defects in the last delivery, repaired on integration rather than
  returned: the manifest was not regenerated after `Makefile.am`,
  `src/pcmdsd.c`, `src/pcmdsd.h` and `soak_p10.py` changed, so it failed on five
  entries; `Makefile.in` and `tests/dsd/__pycache__` were shipped and are
  gitignored build artifacts; and `docs/dsd/briefs/P10-ratify.md` was deleted,
  which over-complies with a request not to ship copies of a brief into the
  tree. No recorded evidence was altered, and every prior results directory is
  byte-identical.
- The one-hour soak evidence that discharged the hardware gate is in
  `tests/dsd/results/P10_soak_1hour_sse2_2026-10-10/`. Its harness summary still
  reads `FAIL` from the superseded `release_sequence` equality; your round fixed
  the check and ruled on the underlying records, and we left the old summary as
  recorded.
- The gate is 5% median regression, admissible only when noise is under 2%, and
  the verdict comes from the confidence interval rather than the median. A
  straddling interval is inconclusive, not a pass. See
  `tests/dsd/BENCHMARKING.md` and `tests/dsd/benchprep.sh`.
- `dff-6ch-repack-small` is the backlog's canary for a reason: `--buffer 32`
  with six channels leaves almost every read in the partial-cluster path, so it
  is the first place any cost near the read loop appears.
- Please return a source tree rather than a built one, keep machine-specific
  paths out of recorded results, leave previously recorded evidence as
  delivered, do not ship copies of this brief in the tree, and flag anything
  here you find to be mistaken.
