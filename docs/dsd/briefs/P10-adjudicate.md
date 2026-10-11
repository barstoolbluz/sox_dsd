# P10 closeout: rule on the last gate

Work in the attached tree, a `git archive` snapshot with no `.git`; the dispatch
note carries its filename and SHA-256. `docs/dsd/sows/P10.md` remains the
statement of work, `docs/dsd/DSD_DESIGN.md` the authority, and
`tests/dsd/reference/p10_ratification_criteria.json` the criterion your
ratification round wrote.

Both halves of `independent_realworld_corpus` have now been measured on the
hardware and the material. Every other P10 gate records a pass. This round is
the ruling, and whatever follows from it.

## What has been measured since you last saw this tree

Everything in this section is what we believe from runs we performed and
interpreted ourselves. You must make the determination.

- **`PCM_AUDIO`**, with your `corpus_pcm.py` and no modification by us: 51
  measurements, 17 independent commercial releases at each of the three native
  rates. We read all 51 as admitted at unity reference, frame and window counts
  exact, levels inside tolerance, and the DSD64 population inside 4 to 24 across
  40,303,869,246 complete windows. Your collector reported coverage `PASS` with
  `approved_for_profile_promotion` false. Evidence:
  `tests/dsd/results/P10_pcm_corpus_2026-10-11/`.
- **`DSD_NATIVE`**, measured earlier with our own driver: 18 commercial DSD
  releases, six per rate. We read 14 as admitted at unity and 4 as rejected and
  then admitted with explicit attenuation between 0.1 and 1.0 dB. Evidence:
  `tests/dsd/results/P10_realworld_corpus_2026-10-10/`.
- **The read/repack throughput gate**, which your validation left to us: we
  measure the hotfix at `-4.43%` on `dff-6ch-repack-small`, all sixteen
  workloads passing, worst noise 0.91%. Evidence:
  `tests/dsd/results/P10_hotfix_throughput_2026-10-11/`.

## You cannot re-run this corpus, and that is permanent

Every other P10 gate you have ruled on was reproducible in your environment.
This one is not, and will never be. The corpus is 19 commercial releases held
privately on this host, on read-only and network mounts. The audio is not in the
tree and must not be: it is third-party copyrighted material and the repository
is published. Your own ratification validation already recorded that no
commercial PCM FLAC recordings were available to you and none are bundled.

So this gate cannot be discharged by re-execution. It can only be discharged by
judging attested measurement, or else it cannot be discharged at all. We think
that is a property of the gate rather than a defect in the evidence, but you may
disagree, and if you conclude that receipt-level scrutiny is insufficient in
principle here, say so plainly: that is a finding about a gate your own round
wrote, and we would rather have it than a ruling nobody can stand behind.

What the tree does let you check, without any of the audio:

- Whether the collector's logic actually implements your criterion, in
  `corpus_pcm.py`, `qualify_p10_ratification.py` and
  `p10_ratification_criteria.json`.
- Whether the recorded receipts are internally consistent and fail closed when
  tampered with. You built exactly this machinery already: `test_p10_pcm.py` and
  the eighteen adversarial receipt tests in `test_p10_ratification.py`.
- Whether each entry carries the provenance the criterion demands: release
  identity, source FLAC and excerpt hashes, STREAMINFO MD5 and CRC result,
  source clock and family, target rate, CLI exit status, output DSF hash,
  per-channel frame and window counts, and the reference used per domain.
- Whether the claimed coverage follows from the entries: rate, family, genre and
  cardinality counts recomputed from the rows rather than taken from the summary.
- Whether the bitstream statistics are trustworthy by construction, via
  `dsd_windows.py --self-check` against `reference/verify.decode_dsf`.

If what you need is a receipt we did not record, name it and we will re-run. The
material stays here; the measurements can be regenerated to any specification
you set.

## Outcomes wanted

1. A ruling on `independent_realworld_corpus` against your own criterion, across
   both domains, on the basis set out above. Whether the evidence discharges it,
   partly discharges it, or does not, is yours to determine. If the honest answer
   is that it cannot be adjudicated from receipts, that is an acceptable answer.
2. A ruling on the read/repack throughput gate, which your own validation
   recorded as awaiting a prepared host.
3. If those close, P10's release disposition stated explicitly, including what it
   does and does not authorise. Our reading is that qualification and promotion
   are different things and that no activation happens before P15, but that is
   your call to make and record, not ours to assume.
4. If they do not close, what specifically is missing and what would suffice.

**A rejection is still a good outcome if the evidence warrants it.** We would
rather run more than have a gate closed on our account.

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
