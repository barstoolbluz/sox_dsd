# P10 closeout: certify, or say what prevents it

Work in the attached tree, a `git archive` snapshot with no `.git`; the dispatch
note carries its filename and SHA-256. `docs/dsd/sows/P10.md` remains the
statement of work, `docs/dsd/DSD_DESIGN.md` the authority, and
`tests/dsd/reference/p10_ratification_criteria.json` the criterion your
ratification round wrote.

Both halves of `independent_realworld_corpus` have been measured on the hardware
and the material, and by your own collector every P10 gate now passes with no
release gates remaining. What is left is the certification that collector
declines to issue for itself.

## Where this now stands

Your own collector, `qualify_p10_ratification.py`, run unmodified at its default
paths with both corpus arms in place, reports every gate `PASS` and
`remaining_release_gates` empty. It also reports `qualified` false, `promotion`
BLOCKED, and `profile_activation` as "UNQUALIFIED: requires explicit positive
certification; P15 governs defaults". Recorded in
`tests/dsd/results/P10_gate_assessment_2026-10-11/`.

So the measuring is done and the remaining step is a judgement your collector
deliberately declines to make for itself.

What we did since you last saw this tree, each item our reading of runs we
performed and interpreted ourselves:

- **`PCM_AUDIO`**, with your `corpus_pcm.py` unmodified: 51 measurements, 17
  independent commercial releases at each native rate, all admitted at unity,
  frame and window counts exact, levels inside tolerance, DSD64 population
  within 4 to 24 across 40,303,869,246 complete windows. Evidence under
  `tests/dsd/results/P10_realworld_corpus_2026-10-10/` as `pcm-*.json`, with the
  narrative in `tests/dsd/results/P10_pcm_corpus_2026-10-11/`.
- **`DSD_NATIVE`**, measured earlier with our own driver: 18 releases, 14
  admitted at unity, 4 explicitly rejected and then admitted under declared
  attenuation between 0.1 and 1.0 dB.
- **The read/repack throughput gate**, which your validation left to a prepared
  host: the hotfix measures `-4.43%` on `dff-6ch-repack-small`, sixteen of
  sixteen workloads passing, worst noise 0.91%. Evidence:
  `tests/dsd/results/P10_hotfix_throughput_2026-10-11/`. Note your collector's
  `inherited_prepared_host_read_repack` still cites the 2026-10-09 run; this
  newer measurement is not wired into it.

One correction we owe you: the corpus gate read `PARTIAL` only because we filed
the PCM records in a directory of their own, while your collector reads both
domains from one base and looks for `pcm-sources.json`, `pcm-unity.json` and
`pcm-ladder.json` beside the DSD files. Your layout was right and ours was
wrong; the records now sit where you put them. Nothing was re-measured.

## You cannot re-run this corpus, and your criterion already allows for that

We had drafted this section to warn you that the corpus is not reproducible in
your environment, and then found your collector already says so itself:
"Recorded hardware provenance and audio hashes are operator-supplied; external
commercial sources are not distributed or re-rendered here." You built the gate
to accept attested measurement with provenance. We note it anyway because it
bears on how much weight the ruling can carry: 19 privately held commercial
releases and a real-hardware soak cannot be re-executed by a model session, and
never will be.

What the tree does let you check without any audio: whether the collector
implements your criterion; whether the receipts are internally consistent and
fail closed when tampered with, which your `test_p10_pcm.py` and the eighteen
adversarial tests in `test_p10_ratification.py` already exercise; whether each
entry carries the provenance the criterion demands; whether the coverage follows
from the rows rather than from a summary; and whether the bitstream statistics
are sound by construction via `dsd_windows.py --self-check`.

If a receipt we did not record would change your confidence, name it and we will
re-run. The material stays here; the measurements can be regenerated to any
specification you set.

## Outcomes wanted

1. Confirm or reject that assessment. If you accept it, say so against your own
   criterion rather than against our account of it.
2. The explicit positive certification your collector requires, or a statement
   of what stands in its way. This is the step it will not take for itself, and
   we are not going to assert it on your behalf.
3. P10's release disposition stated plainly, including what it does and does not
   authorise. Our reading is that passing every gate is not activation and that
   P15 governs defaults, which is what your own `profile_activation` field says,
   but recording that is yours.
4. Whether the throughput gate should cite the newer prepared-host measurement
   rather than the inherited 2026-10-09 one.
5. If any of this does not close, what specifically is missing and what would
   suffice.

**A rejection is still a good outcome if the evidence warrants it.** We would
rather run more than have a phase closed on our account.

## Things we think you should weigh, and may disagree with us about

- Two inventory entries could not be used, so the PCM arm is 17 releases rather
  than 19. Van Morrison, *Live At The Grand Opera House*, and Erling Aasgard,
  *Bach Toccata and Fugue*, carry no STREAMINFO MD5, and the Van Morrison first
  track is 66 seconds against a 90-second requirement. Your driver refuses both.
  We think that is correct, because the stored MD5 is what licenses decoding
  outside the audited binary, and we think 17 still clears your cardinality
  minima with margin. The inventory now flags both, which it did not before.
- Nothing in the PCM arm was rejected, where 4 of 18 DSD-origin sources were. We
  believe that follows from the reference convention rather than indicating
  anything about the encoder: preserve reference maps DSD full scale to 1.0 and
  puts the 0.5 envelope at -6.0206 dBFS, where commercial DSD masters sit, while
  an ordinary PCM source is scaled by 0.5 and carries about 6 dB more headroom.
  If you read that asymmetry as under-stressing the PCM domain, say so.
- The five 176400 Hz releases are all Neil Young, one credited to Neil Young &
  Crazy Horse. They are distinct commercial albums from different years by two
  transfer routes, but they share an artist and catalogue lineage, and they are
  the only native material at the DSD128 and DSD256 working rate.
- Your alignment fix recovered the throughput gate and we believe it did more
  than that, since the canary is now faster than before the regression. We also
  believe the fragility is reduced rather than removed: growing an unrelated
  object by about a page still moved that workload `-2.70%`, with both read
  functions staying page-aligned. The structural claim in your comment holds;
  throughput independence does not follow from it. That reading is ours.
- We did not measure integrator state maxima or nonfinite counts over either
  corpus arm, because no harness mode exposes them for an external file. If your
  criterion needs that coverage, neither arm provides it.

## Situational notes, possibly wrong or incomplete — trust the tree over them

- Your `dsf_window_statistics` streaming reader replaced our whole-file
  approach and we kept it; its `--self-check` asserts agreement with both our
  vectorised path and `reference/verify.decode_dsf`, and passes.
- `docs/dsd/briefs/P10-ratify.md` and `P10-hotfix-pcmarm.md` are our own tracked
  briefs. Both were deleted in the last two deliveries and restored on
  integration; they are not copies for you to ship back.
- Every prior evidence directory is byte-identical across the last two rounds.
  Three defects in the ratification delivery, a stale manifest and two shipped
  build artifacts, were repaired on integration rather than returned; the hotfix
  delivery had none.
- The gate is 5% median regression, admissible only when noise is under 2%, with
  the verdict taken from the confidence interval rather than the median. See
  `tests/dsd/BENCHMARKING.md` and `tests/dsd/benchprep.sh`.
- P11 is blocked behind P10 and introduces runtime ISA kernels. The one-hour
  hardware criterion you wrote requires requalification per newly introduced
  kernel family, and today there is one, the compiled `__SSE2__` baseline.
- Please return a source tree rather than a built one, keep machine-specific
  paths out of recorded results, leave previously recorded evidence as
  delivered, do not ship copies of this brief in the tree, and flag anything
  here you find to be mistaken.
