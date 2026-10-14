# P15 closeout adjudication (2026-10-14)

**Release decision: BLOCKED.** The first-release qualification is **not closed**.
Do not set production mastering `qualified` bits, change automatic decode/
encode policy, select a new ISA default, claim device compatibility, or start
P16 on the strength of this review. The historical P10 scalar mastering
certificate remains positive only for its pinned revision and scope.

## Input, custody and authority

- Reviewed `sox_ng-P15-closeout-f5b961c1.tar.gz`, SHA-256
  `6e7739527e3b976ead736db91cebd578c7908a02a00c49f348fabdb22863726c`;
  its reported source revision is `f5b961c1` and it contains no Git history.
- Authority: `docs/dsd/DSD_DESIGN.md`, especially 6.1, 6.4, 6.5, 8.6,
  10.4-10.7, 11 and 13; `docs/dsd/IMPLEMENTATION_PLAN.md` P15;
  `docs/dsd/sows/P15.md`. The brief's assertions and result READMEs are
  claims to test, not signed acceptance certificates.
- Machine-readable current adjudication:
  `tests/dsd/results/P15_closeout_adjudication_2026-10-14/review.json`,
  produced by `tests/dsd/p15_closeout_review.py` from preserved bytes.
  `tests/dsd/results/P15/release/release-manifest.json` is the **earlier
  historical inventory** and remains byte-identical. Its six `UNRUN` labels
  describe what the original program knew, not the latest evidence state;
  do not rerun its writer over that historical receipt.
- This adjudication accepts **two gates with strictly stated scope** and keeps
  **four mandatory gates open**. A scoped pass never grants the complete P15
  release. We have not amended any DSP acceptance number or manufacturing
  performance requirement to manufacture a PASS.

## Each of the six original gates

1. **Full independent 3 x 9 x 2 numerical release matrix: OPEN.** There are
   54 reported scalar cells, 270 reported forced-tier jobs counting scalar,
   and 96 selected ISA detail comparisons. All 324 stored cell JSON files
   match their `.sha256` companions; recorded counts, sampled SRC and graph
   checks are consistent, and the isolated FIR errors fall within the
   design's existing FIR-only roundoff bounds. The saved instrument marks
   every cell *unqualified*. The 54 sets of raw numerical arrays from the
   full-scalar session plus 270 forced-tier sets (`arrays/*.npz`), optional
   `src-raw`, and `graph-raw` were **not bundled**. Its original independent
   reviewer therefore exits **1** on a missing raw digest at the first cell;
   row checksum verification cannot substitute for recomputing waveforms.
   Crucially, no full composite SRC spectral extrema/coherent-alias
   certificate exists. The FIR's approximately 2e-16 observations cannot
   certify end-to-end resampling.

   **Correction to the submitted README:** its claim of 54/54 *full binary64
   hash equality across five tiers* is false on the submitted records. All
   54 cells contain four distinct hashes (scalar; SSE2; AVX1 and AVX2 together;
   AVX-512). Zero of the 216 non-scalar-to-scalar binary64 hashes matches.
   The reported maximum per-sample scalar-vs-vector difference is at most
   `4.440892098500626e-16`, comfortably a roundoff-scale observation, not
   an identified decoder defect. The contract permits such roundoff. An
   int32-output or equality-of-quantized-audio finding is not binary64
   bit identity. Preserve the original mistaken README and apply this
   documented correction rather than editing historical evidence.

2. **Physical Intel AVX-512 performance: UNRUN.** No pinned, repeatable
   physical Intel performance receipt was supplied. The Xeon CPU market
   includes AVX-512-capable machines; Intel's disabling that instruction
   set on some client parts does not make the criterion technically
   impossible. Local unavailability is a legitimate operational constraint,
   **not a passing test**. No Intel-specific preference or vendor-equivalence
   claim is authorized. The current P15 contract explicitly requires this
   test. Removing it would require a separately reviewed, feature-scoped
   design amendment; no such amendment is made here.

3. **Physical older AVX1-only performance: PASS, SCOPED.** The replacement
   Intel Xeon E5-1680 v2 receipts are now internally consistent, unlike the
   previously rejected Threadripper `host.txt` and console-only claims.
   `check_p15_avx1_receipt.py` returns `ADMISSIBLE_FOR_INDEPENDENT_REVIEW`,
   with zero problems. The stored kernel JSON supplies 15 individual
   repetitions in each scalar/SSE2/AVX1 `fir-single`, `fir-block`, and `sdm`
   arm, source/build hashes, affinity and CPU-time measurements. The host
   record identifies AVX support and no AVX2, the three measured arm clocks
   are 3000 MHz, and the output hashes support a correct within-host
   scalar-versus-vector result. This **does discharge the missing physical
   older-AVX kernel-performance observation**. Source and result provenance
   are operator-supplied, not cryptographically attested silicon. It does
   **not** establish an AVX1 end-to-end dispatch advantage, a new CPU policy
   entry, or performance on every older AVX CPU. Do not impose cross-host
   scalar SDM output byte identity: section 8.6 does not promise it.

4. **Six-channel DSD256 2x controlled reference target: UNVERIFIED.** The
   submitted console log reports 3.83x (lower 95% bound 3.77x) at 352.8 kHz
   and 3.94x (lower 95% bound 3.92x) at 176.4 kHz. These are encouraging and
   far exceed the 2.00x design target **if the timing experiment is valid**.
   However the archive contains **no 15-repeat individual timing records**,
   no execution/fixture/checksum binding for those comparisons, and no
   independently auditable confidence-interval calculation. The nominal
   20-kHz bandwidth-matched comparison provides only nine repetitions, and
   the described `rate -v` then `sinc -20000` control is not demonstrably the
   *bandwidth-matched staged legacy control* required by 10.7: post-filtering
   cannot undo aliasing that occurred during prior decimation. Record the
   host/clock/affinity and benchmark commands, supply the existing raw paired
   samples and actual matched control, and validate both before closing;
   **do not** rerun the full DSP phase merely for this evidence gap.

5. **One-hour current-profile/ISA soaks: PARTIAL, NOT CLOSED.** Fifteen
   current-revision encoder reports cover the three native mastering rates
   and all five SDM kernel families, 3600 audio seconds per case. Raw JSON
   counters record zero failures, nonfinite states, monitor overloads or
   DSD64 population violations; counts and guard maxima are consistent.
   `UNQUALIFIED` / `status=3` in the underlying candidate harness describes
   non-activation, not an encoded-audio error. But **all fifteen sets of 61
   saved continuation states and their state hashes are missing**, as are
   the 15 machine-generated `soak-<rate>-execution.json` identity receipts.
   The existing `soak_p10.py inspect` logic explicitly requires those
   artifacts. Attach the original snapshots and execution identities (or
   rerun *only if unavailable*), then independently replay/verify them.
   The one-hour criterion in section 10.5 addresses **PCM-to-DSD**; it does
   not create a previously unstated one-hour soak requirement for each of
   the six decode profiles. Decoder long-stream/performance tests remain
   governed separately by sections 10.4 and 10.7.

6. **Independent codec/hardware corpus: PASS, SCOPED TO SOFTWARE MATERIAL.**
   The retained P15 receipts cover 18 DSD external excerpts across three
   rates (14/18 unity admissions, four expected refusals with valid explicit
   gain-ladder admissions) and 17 independent PCM recordings rendered at
   all three native rates (51 admitted cases). The original P10/P15
   independently executable *record comparison* passes. It finds **six
   changed extrema fields across three distinct sources**, not just the
   single Cantata field cited in the submitted closeout; all changes are
   permitted one-count extrema drift within the 4-24 criterion. Four ladder
   cases omitted earlier rejected gain trials, but common trial outcomes
   and terminal accepting gains agree. The actual commercial recordings
   remain privately held, so this is an audit of authenticated *recorded*
   data and an inherited P10 external corpus certificate, not a fresh
   independent audio rerender by this reviewer.

   **Scope decision:** Section 13 expressly says a physical DAC/player matrix
   becomes mandatory only for the specific **device-compatibility claim**.
   The first release advertises software DSD/PCM conversions and bitstream
   formats, not universal DAC/player or transport compatibility. The
   independent-source material obligation is discharged for that scope;
   actual physical device compatibility is **NOT TESTED AND NOT CLAIMED**.
   This makes the original compound gate `PASS-SCOPED`, not a claim that a
   hardware test ran. If device/player support is advertised later, test the
   claimed combination with meaningful loopback/capture or another
   device-level protocol oracle. Passing a generated `.dsf` or DoP payload
   to a DAC without a digital capture would provide only narrower evidence.

## SRC acceptance-envelope decision

**A universal maximum absolute sample delta against the supplied independent
*Kaiser SRC of a different design* is out of scope.** Two valid linear-phase
SRC filters with different transfer functions will legitimately produce
nonidentical PCM even in infinite precision. Treating the observed 24
fractional-cell residuals or 28 edge-dominated maxima as errors bounded by
section 8.6's *FIR-only* accumulated-roundoff formula is mathematically wrong.
The 0.00001-0.001 edge deltas do not, by themselves, prove a product defect.

The *product-level* composite SRC envelope is **not out of scope**: it is
already fixed by sections 6.1, 6.4-6.5 and 10.4. Require the actual combined
transfer (including fractional SRC) over the effective output passband
`P_effective = min(P_profile, 0.475 * min(R, F_out))`, maximum absolute
passband ripple **0.0001 dB**, and guaranteed stopband/coherently summed
aliases **at most -160 dB**; independently verify complete spectral extrema
and image sums, linear-phase delay, finite-file zero-extension, frame count,
startup/drain, graph clipping and the one-int32-LSB graph comparison to the
*actual* binary64 output. Identity-rate SRC bypass is exempt from unnecessary
new SRC tests, not from FIR qualification.

For the additional **arithmetic** tolerance called for in 8.6, independently
implement the **same mathematical production SRC transfer/phase/finite
boundary convention**, using independently evaluated high-precision taps or
an equivalent error-analyzed operator, and predeclare a coefficient/roundoff
bound before comparing output samples. This is a like-for-like numerical test;
the existing different-filter reference remains a useful independent transfer
and alias cross-check. **No arbitrary numerical epsilon or post-hoc margin is
introduced here.** Until the like-for-like arithmetic check and full extrema
certificate are available, the numerical gate stays open. This is a bounded
missing *proof*, not an instruction to redesign the production resampler.

## Exit evidence and next permitted task

Recompute the current disposition without changing old results:

```sh
python3 -m unittest discover -s tests/dsd -p test_p15_closeout_review.py -v
python3 tests/dsd/check_p15_avx1_receipt.py \
  --results tests/dsd/results/P15_avx1_physical_2026-10-13 \
  --output /tmp/avx1-independent-review.json
python3 tests/dsd/p15_closeout_review.py \
  --output /tmp/p15-closeout-adjudication.json --require-qualified
```

Expected: four tests pass; physical older AVX reviewer exits `0`; the new
adjudication writer exits **2** because the release remains blocked. The
previous independent matrix reviewer exits `1` when given the archived
`scalar-full` session because `arrays/dsd64.mastering.pcm44100.npz` is absent.
All P00 checksum entries should verify after the self-excluding manifest is
regenerated last. No existing result files, accepted certificates or prior
handoff text are rewritten in this closeout.

**Next permitted work: P15 evidence completion, not P16.** Restore raw matrix
vectors/graph/SRC streams needed to review existing numbers; certify complete
composite spectra and a like-for-like SRC numerical bound; obtain physical
Intel AVX-512 performance or explicitly revise the advertised release scope;
provide source-bound repeated DSD256 comparator samples and correct matched
staging; restore state/command receipts for the fifteen completed soaks.
Then re-adjudicate P15. A future positive release decision would **still**
require targeted default/`qualified` source changes plus full regression
qualification on those changed release bytes. No release is activated merely
by changing this ledger.

## Executed review and regression checks

All code compilation and executable regressions were run on a disposable
copy of the same source tree. Build products and newly generated historical
phase outputs are **not** included in the source deliverable.

- `autoreconf -fi`: **0**, completed.
- `./configure --disable-shared --without-libltdl CFLAGS='-O2 -g'`:
  **0**, completed; the optional codec set is host-dependent.
- `make -j2`: **0**, completed.
- `make check`: **0**, completed; some optional tests reported `VOID`
  as intended by the existing harness.
- `python3 tests/dsd/test_p15.py --sox src/sox_ng --results <temporary-results>`:
  **0**, **134 passed**, **0 failed**.
- `make check-dsd`: **not completed**. It exceeded the verification
  execution limit while running P09's frozen `analysis-v1/verify.py`,
  after P00-P09 smoke, format, scalar and CLI stages had reported no
  failures. The runner was terminated externally at 180 seconds; later
  P10-P15 integration sections did not execute during this attempt. This
  is **not** reported as a regression pass and does not change any gate.
- `python3 -m unittest discover -s tests/dsd -p test_p15_closeout_review.py -v`:
  **0**, four tests passed. The tests include altered-evidence rejection
  and deterministic, nonqualifying exit semantics.
- The existing older-AVX receipt validator and independent P10/P15
  corpus comparator both passed, with bounded scope and limitations above.
- `p15_closeout_review.py --require-qualified`: **2**, as intended for
  a complete *audit* with an **incomplete release**. The same JSON is
  reproducible from the preserved archive receipts.

A complete successful P15 DSD make target, hardware run, SRC certificate,
or complete official release manifest was neither produced nor claimed.
