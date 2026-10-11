# P10 closeout: certify, or say what prevents it

Work in the attached tree, a `git archive` snapshot with no `.git`; the dispatch
note carries its filename and SHA-256. `docs/dsd/sows/P10.md` is the statement of
work, `docs/dsd/DSD_DESIGN.md` the authority, and
`tests/dsd/reference/p10_ratification_criteria.json` the criterion your
ratification round wrote.

Both halves of `independent_realworld_corpus` have now been measured on the
hardware and the material. We believe that leaves nothing left to measure and
that the remaining step is the certification your collector declines to issue
for itself. That belief is ours; the determination is yours.

## What we read from the evidence

Our reading of runs we performed and interpreted ourselves. We have been wrong
in this project before and corrected by review more than once.

Run unmodified at its default paths, `qualify_p10_ratification.py` reports every
gate `PASS` with `remaining_release_gates` empty, alongside `qualified` false,
`promotion` BLOCKED and `profile_activation` as "UNQUALIFIED: requires explicit
positive certification; P15 governs defaults". Recorded in
`tests/dsd/results/P10_gate_assessment_2026-10-11/`.

- `PCM_AUDIO`, using your `corpus_pcm.py` unmodified: 51 measurements across 17
  independent commercial releases at each native rate, all admitted at unity.
- `DSD_NATIVE`, using our own driver: 18 releases, 14 admitted at unity, 4
  rejected then admitted under declared attenuation of 0.1 to 1.0 dB.
- The read/repack throughput gate your validation left to a prepared host:
  `-4.43%` on `dff-6ch-repack-small`, sixteen of sixteen passing, worst noise
  0.91%, in `tests/dsd/results/P10_hotfix_throughput_2026-10-11/`. Your
  collector's `inherited_prepared_host_read_repack` still cites the 2026-10-09
  run instead.

The corpus gate had read `PARTIAL` because we filed the PCM records in their own
directory while your collector reads both domains from one base. Your layout was
right. The records now sit where you put them and nothing was re-measured.

## Outcomes wanted

1. Confirm or reject that assessment against your own criterion.
2. The explicit positive certification, or what prevents it and what would
   suffice.
3. P10's disposition stated plainly, including what it does not authorise.
4. Whether the throughput gate should cite the newer prepared-host measurement.

**A rejection is a good outcome if the evidence warrants it.** We would rather
run more than have a phase closed on our account.

## Where we may be wrong

- Neither corpus arm measures integrator state maxima or nonfinite counts. No
  harness mode exposes them for an external file. If your criterion needs that
  coverage, nothing here supplies it.
- Nothing in the PCM arm was rejected, where 4 of 18 DSD-origin sources were. We
  read that as the reference convention: preserve maps DSD full scale to 1.0 and
  puts the 0.5 envelope at -6.0206 dBFS, where commercial DSD masters sit, while
  an ordinary PCM source is scaled by 0.5 and carries about 6 dB more headroom.
  If you read it as under-stressing the PCM domain instead, say so.
- The PCM arm is 17 releases, not the 19 inventoried. Two carry no STREAMINFO
  MD5 and your driver refuses them; one of those also has a 66-second first
  track. We think refusing them is correct and that 17 still clears your minima,
  but that is our judgement about your criterion.
- The five 176400 Hz releases are all Neil Young, one credited with Crazy Horse.
  Distinct albums, different years, two transfer routes, one catalogue lineage,
  and the only native material at the DSD128 and DSD256 working rate.
- Your alignment fix recovered the throughput gate and we think overshot it, the
  canary now being faster than before the regression. We also think the
  fragility is reduced rather than removed: growing an unrelated object by about
  a page still moved that workload `-2.70%` with both read functions staying
  page-aligned. The structural claim in your comment holds; throughput
  independence does not follow from it. Both readings are ours.
- This gate cannot be discharged by re-execution, now or ever: 19 privately held
  commercial releases and a real-hardware soak. Your collector already says so,
  recording that provenance and hashes are operator-supplied and external
  sources not re-rendered. If receipt-level scrutiny is insufficient in
  principle, that is a finding about the criterion and we would rather have it
  than a ruling nobody can stand behind. If a receipt we did not record would
  change your confidence, name it and we will re-run.

## Situational notes, possibly wrong or incomplete — trust the tree over them

- Your `dsf_window_statistics` streaming reader replaced ours and we kept it;
  its `--self-check` asserts agreement with both our vectorised path and
  `reference/verify.decode_dsf`, and passes.
- No previously recorded evidence was altered. Running your collector at its
  default output path overwrote the delivered
  `P10_ratification_2026-10-10/qualification.json`; it is restored
  byte-identical and the new assessment writes elsewhere.
- P11 is blocked behind P10 and introduces runtime ISA kernels. Your one-hour
  hardware criterion requires requalification per newly introduced kernel
  family; today there is one, the compiled `__SSE2__` baseline.
- Please return a source tree rather than a built one, keep machine-specific
  paths out of recorded results, leave previously recorded evidence as
  delivered, do not ship copies of this brief in the tree, and flag anything
  here you find to be mistaken.
