# Independent engineering validation: SoX-NG P15 SRC and campaign corrective

**Review date:** 2026-10-17 (UTC)  
**Method:** independent source inspection, fresh native compilation, actual test execution, source-bound coefficient recapture, numerical cross-checks, historical routing replay, adversarial receipt tests, and minimal repair.  
**Scope:** the two user-supplied archives, their actual integration, and applicable P15 acceptance requirements in `docs/dsd/DSD_DESIGN.md`. No original `sox_ng-campaign-corrective-gap.tar.gz` was supplied in this session; the complete rebinding repository did contain the original uncorrected campaign modules, the old tests and pinned historical partial campaign.

## A. Executive verdict

| Deliverable | Verdict | Grounds |
|---|---|---|
| Original `sox_ng_P15_SRC_OPT_REBOUND_FULL_2026-10-17.tar.gz` | **PASS WITH QUALIFICATIONS** | Fresh optimized/default SoX builds succeeded; real C exact-equivalence tests, ASan/UBSan test, build-admission check, both-mode real CLI comparison, all 24 recaptured source operators and targeted rebinding tests passed. General platform performance and P15 numerical release qualification are not implied. |
| Original `sox_ng_P15_campaign_corrective_2026-10-17.tar(1).gz` | **FAIL** for its receipt-import/integrity claim, **PASS** for the exercised exact-routing and bounded-execution functions | Two reproducible, limited-scope receipt-validation defects could accept an incorrectly labeled historical PASS, or changed/missing historical receipt bytes with an unchanged pinned summary. A third non-spectral integration-completeness issue was the absent scheduled-replay fixture used by an existing test. No demonstrated defect in the exact branch-boundary logic or the directed interval upper-bound computations. |
| Two **original** archives, overlaid as supplied | **FAIL** for full integration acceptance until the two receipt checks are fixed | The overlay applies cleanly even though one of its expected baseline file hashes differs, and retains the active rebinding snapshot path. Runtime and scheduling integration tests pass; receipt-import integrity does not meet the claimed contract. |
| **Corrected combined tree in the companion full source bundle** | **PASS WITH QUALIFICATIONS** | Both confirmed integrity defects fixed and the missing routing-only fixture supplied, without modifying runtime C, coefficient bytes, source-bound snapshots or mathematical interval algorithms. Corrected out-of-box 31-test suite: 30 passed, 1 skipped; independently built and used the skipped test's exporter. Ready for **opt-in repository integration, not for P15 certification or a default change**. |

**Final disposition:** **Ready for repository integration but NOT P15 certification**, *using the accompanying corrected source bundle/patch*. Do not promote mastering v2, change the SRC default, advance to P16 on the strength of this work, or call the entire spectrum certified.

## B. Genuine defects, reproductions and minimal corrections

### F1 - A stopband PASS could discharge a passband job (blocking the original historical-import validation contract)

- **Severity / requirement:** P2, local campaign integrity and no falsely proven intervals. This is a *receipt-consumption* defect, not a demonstrated error in the underlying spectral calculation.
- **Original location:** `tests/dsd/p15_full_band_campaign.py`, `check_one`, originally lines 134-154; also `summarize` around lines 315-332, which counted any `PASS-LOCAL-*` as proven.
- **Trigger:** A source-/design-bound receipt for a `mode='pass'` job has `certificate.status='PASS-LOCAL-STOP-SOURCE'`, while `certificate.band_kind='pass'`, all input/output frequencies and `governing_passband_hz` match the job, and outer `qualified_release=false`.
- **Reproduction actually executed:** `integrity_repro.py` generated a source-matching synthetic historical receipt without modifying original archived files. The original `check_one()` returned a valid document, and `import_archived_partial()` imported it as `PASS-LOCAL-STOP-SOURCE`, even though the job was `pass`. Output: `CHECK_ONE_ACCEPTS_MISMATCHED_PASS: True`, `IMPORT_ACCEPTS_MISMATCHED_PASS: 1`. This is a concrete false local-proven disposition, not a hypothetical numerical fault.
- **Cause:** `check_one()` independently checked allowed status names and a `band_kind` field but did not check that the status name corresponded to the requested band kind.
- **Small correction applied:** Require `PASS-LOCAL-BAND` only for `pass`, and `PASS-LOCAL-STOP-SOURCE` only for `stop`; also reject an inner `qualified_release=true` rather than relying only on the outer field. No changes to OPEN handling or proof thresholds.
- **Regression:** `SyntheticArchiveTests.test_receipt_pass_status_must_match_job_mode`. Now passes (the forged receipt is rejected).

### F2 - Summary digest did not bind individual archived receipts

- **Severity / requirement:** P2, historical evidence integrity and provenance. Separate from whether the archived mathematics is correct.
- **Original location:** `tests/dsd/p15_full_band_campaign.py`, `import_archived_partial`, originally lines 216-263.
- **Trigger:** With the archived `SUMMARY.json` unchanged (therefore its pinned SHA-256 still accepted), remove or alter a receipt under `receipts/`. The original importer checked the summary hash, job metadata and present receipt fields, but neither committed to the complete inventory nor independently checked receipt bytes against a pinned archive identity. A missing file was silently skipped; a changed admissible-looking certificate could be copied.
- **Evidence:** Direct source inspection plus the executed F1 import demonstration. The existing synthetic import case showed that its summary hash remained valid when receipt contents changed. This is a credible integrity failure in an explicitly historical-import interface. In the *current optimized-source tree* the older receipts additionally fail the source-binding check, so no erroneous historical PASS was observed from the actual 5,112 receipts.
- **Small correction applied:** Pin a single SHA-256 commitment to the sorted `(filename, SHA-256(file bytes))` inventory of the **5,112** supplied historical receipts; check file types, exact filename forms, inventory size against the unchanged historical summary, and aggregate digest **before any import**. The reference commitment is `7bbd0c5c2d889ad7bb46fbc27e8ba350b2c86f877b0f5f1e7c50c04a3b80347f`. This is a content identity commitment to the supplied archive, **not independent certification of its historical mathematics**. Existing source-binding refusal remains untouched.
- **Regressions:** The existing synthetic idempotent import case was extended to reject both changed receipt contents and missing receipts while the summary remains fixed. It and all other synthetic tests pass.

### F3 - Missing historical routing-only replay fixture (integration completeness; not a spectral defect)

- **Severity / requirement:** P3; the existing source-bound historical routing regression must work from an unmodified extracted distribution. This is a test-data delivery defect, not a numerical false PASS or a release-certificate defect.
- **Original location:** `tests/dsd/test_p15_campaign_dispatch_corrective.py`, its historical replay regression near lines 197-204; required but absent file `tests/dsd/results/P15_campaign_dispatch_corrective_2026-10-17/SCHEDULE_REPLAY.json`.
- **Trigger / independent reproduction:** Running the original combined test group without a manually injected replay path failed with `FileNotFoundError` for that exact JSON path. Regenerating its route-only schedules independently from the pinned historical summary and the actual optimized-source-bound stage operators produced **43/43 `COMPLETE-SCHEDULE`**, with **73 exact rational branch splits**.
- **Small correction applied:** Include this 13-KiB, deterministic replay JSON fixture at the test's existing expected path (SHA-256 `b0d35d87cb665b10f47dba335ee5723c12366428c6dc093c382b991114887f42`). Its explicit `qualified_release=false` and schedule-only classifications cannot discharge spectral bounds.
- **Regression:** The corrected final tree was tested **directly from a second pristine source extraction**, without modifying the replay-path test: 31 discovered, **30 passed and one skipped exporter-location test**. The exporter was separately compiled and used successfully for the full 24-snapshot recapture.

**Scope of the correction:** `tests/dsd/p15_full_band_campaign.py` and `tests/dsd/test_p15_campaign_corrective_synthetic.py` changed beyond the prior overlay, and the missing routing-only regression fixture was added at `tests/dsd/results/P15_campaign_dispatch_corrective_2026-10-17/SCHEDULE_REPLAY.json`. The supplied stagewise numerical correction was integrated unchanged. Production C sources, generated filter coefficients and existing archived receipts were **not** edited. No new framework, dependency, worklist semantics or relaxation of bounds was introduced.

### Observations deliberately **not** promoted to corrective blockers

1. The combined tree's `p15_full_band_campaign.py` had SHA-256 `4fd03724508ed9bd7aba4e55fec184aa5935c7c59be74427d055fd7b5bde854f` before application; the campaign overlay demanded `81f5715917c01d169ac40d1b5808957265f247d4bc53a1a58e261f1e91e587f7`. `git apply --check` nevertheless passed, and the resulting difference from the standalone overlay was **only** the intentional `ACTIVE_STAGE_ROOT` import/selection. This is a documentation/precondition discrepancy, not a broken merge. The accompanying combined patch targets the actual rebinding archive, and has been independently reapplied and compared byte-for-byte.
2. `run_campaign` deliberately never overwrites an existing `OPEN` receipt when restarted with a larger time/node allowance. An actual 0.03-second interval execution published an `OPEN` timeout receipt and a restart with larger budget left its bytes intact. This is immutable/idempotent behavior; intentional recomputation needs a new output directory or explicitly managed OPEN receipts. It is a workflow limitation, **not** grounds to redesign the scheduler.
3. `source_identity()` pins production/capture inputs, **not all Python proof/checker implementations**. Therefore a matching source identity alone does not independently ratify an old mathematical proof generated by a different checker revision. In this review the 5,112 old campaign receipts bind a different `src/rate_poly_fir0.h` and `p15_src_capture_matrix.py` source identity, and are rejected. Independent release replay remains mandatory. Do not silently relabel them as current-source proofs.
4. POSIX `SIGALRM` is a soft synchronous Python deadline, not a hard kill of an uninterruptible native call or a portable non-main-thread timeout. The implementation explicitly refuses unsupported contexts; no general-purpose subprocess execution framework is justified for the demonstrated campaign workload.

## C. Evidence and test matrix

### C1. Source identity and integration

| Item | Observation |
|---|---|
| Full source input | `sox_ng_P15_SRC_OPT_REBOUND_FULL_2026-10-17.tar.gz`; SHA-256 `3eea7cd75a5bc9f0799fc883041279906ff197bec329cf1814f18039120ad965`; 22,416 archived entries; extracted source about 680 MiB. |
| Corrective input | `sox_ng_P15_campaign_corrective_2026-10-17.tar(1).gz`; SHA-256 `4c4ee75b34d26a0663193bf513b2d054f7698ece5890c16b8f79b6c93728fb1c`; 14 entries. Its own `SHA256SUMS.txt` verified all listed overlay files. |
| Original corrective prerequisites | `p15_src_stagewise_continuum.py` exact expected SHA `4a5d5768849735f7e4e6e0e249cf4e026475ccf4e72b84ce3b0dcf8cc907d1e0`, matching full repo; campaign's expected SHA differed as described above. |
| C runtime source | Optimized `src/rate_poly_fir0.h`: `bd86a881e1e27718854e0e61451c118dc1f8f2cc7748974e8db0e00846de23b7`. Preserved frozen reference header: `928f005912f35ca0612a37c99a9a6343be8dea51e23cd41f5286b9f85fede6ff`. |
| Campaign dependencies | `p15_src_branch_bound.py`: `9553720939baeac7bcb86066b5d709798a4431ecb9da3f346546f9ffab13c4b1`; `p15_src_interval_recurrence.py`: `4e2b502f6cfa9d31874cb40f3f172280994aad18aeba9fadc09cc25e9be44879`. Both already matched the overlay's retained reference copies; no transplant was necessary. |
| Coefficient/operator rebind | Independently built the C test-only stage exporter, captured all 24 operators to a **fresh directory**, and compared every `stage-snapshot.json` against the archive's optimized-bound snapshot: **24/24 byte-identical**. All 72 SRC-active cells and 214,432 1-kHz alias families were enumerated by the actual matrix instrument; release was explicitly `BLOCKED`. |
| Corrected source patch | `P15_MINIMAL_INTEGRATION_CORRECTIVE.patch` (companion). Applied via `git apply --check` and `git apply` to a second pristine extraction of the original full source archive. All four resulting source/test/fixture files matched the reviewed, corrected working files byte-for-byte. |

### C2. Compiled runtime and performance (newly executed)

**Environment:** Linux x86_64, GCC 14.2.0, Python 3.13.5; GNU Autotools fresh out-of-tree builds, `-O2 -g -ffp-contract=off` both ways, opt-in defined with `-DLSX_RATE_ORDERED_OPT=1 -DLSX_RATE_ORDERED_OPT_FP_CONTRACT_OFF=1`. `--without-libltdl` and environment-available codecs were used. Default-off build omitted both opt-in defines.

| Executed check | Outcome | Qualification |
|---|---|---|
| `autoreconf -fi`; optimized configure and `make -j8 all` | **PASS** | Fresh real SoX-NG native binary/library build. |
| Default-off configure and `make -j8 all` | **PASS** | Separate fresh binary/library. |
| Compiled real `tests/dsd/test_src_optimization.c` against the optimized build, opt-on | **PASS** | 768,060 checks; 53,856 direct cases; 288 streaming cases; 50 API cases; 5,409,850 exact binary64 words; 4 rounding modes; `effective_ordered=1`. Includes frozen reference header and stage/FIFO comparisons. |
| Same C harness compiled opt-off | **PASS** | Same assertion/case/word counts; `effective_ordered=0`. |
| Independently compiled ASan/UBSan opt-on C harness | **PASS** | Same 768,060-check regression with `detect_leaks=0`; covers the included/instrumented C probe, but the separately linked SoX library was not sanitizer-instrumented in this run. Not a full-program sanitizer qualification. |
| `p15_src_opt_build_contract.py --makefile <optimized src/Makefile>` | **PASS** | Actual configured CFLAGS include both acknowledgement macros and terminal `-ffp-contract=off`. The C header compile intentionally **failed** without the acknowledgement define. This is build-flag screening, not machine-code formal verification. |
| Real SoX CLI: 176.4 -> 48 kHz, 2-channel f64, `rate -v -L -B 95` | **PASS** | Opt-on/off outputs both 768,000 binary64 words; byte-identical SHA `3a4f0730ea70c7949273b764bc1f5f8410a0151e6e57e17c347cbb337427b5fc`. Four trial median wall times: 0.087665 vs 0.088570 seconds. |
| Real SoX CLI: 88.2 -> 44.1 kHz, 2-channel f64, same rate options | **PASS** | Opt-on/off outputs both 1,411,200 words; byte-identical SHA `516e9542545fa6bfc60f4d775b553b9d3b921d271052f5d63e115694d01cc8d6`. Four trial median wall times: 0.061625 vs 0.062395 seconds. |
| Real FIFO microbenchmark, 15 cases x 17 rounds x 3 arms | **PASS, performance mixed** | 765 timed JSON rows, two warmups then 15 timing rounds per arm/case. On 4,096-frame calls, median ordered/original CPU ratios **0.432 to 0.646** across nine tested tap/ratio cases; zero-frame case ratio **1.028**; 1-/2-frame cases about **0.982/0.986**. These are local microbenchmarks, not physical DSD256 comparator data. |

The C phase-carry recurrence preserves positive quotient/remainder advancing via `carry = rem >= L - step.rem` and visits each original coefficient and input in the same order for each paired output. Its fast path handles `max_num_out > 2`; short calls retain the original loop. Source inspection found no new realistic overflow/buffer fault within the admitted bounded stage configuration, and the exact C/ASan/UBSan/streaming tests found none. This is evidence of supported-condition correctness, **not** proof for arbitrary out-of-contract stage mutations or all future compilers. The tiny-call cost and workload-dependent whole-CLI benefit are good reasons to keep the optimization opt-in.

**Representative reproduction (from extracted repository root):**

```sh
autoreconf -fi
mkdir -p ../buildopt
cd ../buildopt
CFLAGS='-O2 -g -ffp-contract=off -DLSX_RATE_ORDERED_OPT=1 -DLSX_RATE_ORDERED_OPT_FP_CONTRACT_OFF=1' ../sox_ng/configure --without-libltdl
make -j8 all
make -C test dsd_test_p15_src_stage_export
cd ../sox_ng
python3 tests/dsd/p15_src_opt_build_contract.py --makefile ../buildopt/src/Makefile
LD_LIBRARY_PATH=../buildopt/src/.libs PYTHONPATH=tests/dsd python3 tests/dsd/p15_src_capture_matrix.py --output /tmp/p15-new-capture --exporter ../buildopt/test/.libs/dsd_test_p15_src_stage_export
```

The source includes `docs/dsd/SRC_RUNTIME_OPTIMIZATION_REPRODUCE_2026-10-17.md` with additional full C harness and host-specific benchmark build recipes. The independently executed C harness commands and stdout JSON are retained in the companion evidence bundle.

### C3. Campaign, interval mathematics, source binding and historical replay

| Executed check | Outcome | Meaning |
|---|---|---|
| Original combined targeted Python campaign/rebinding/operator tests | 29 passed / 1 skipped after temporarily supplying the missing routing replay | The archive initially yielded 19/20 campaign tests with a missing schedule replay file. Its generator produced a fresh valid `SCHEDULE_REPLAY.json`; the same test then passed. The skip was the source-tree test's automatic test-only exporter location, separately built and run above. |
| Corrected targeted suite, unmodified out-of-box tree | **30 passed / 1 skipped** (31 discovered), 26.956 seconds | Nine corrected synthetic tests, 12 historical/routing/interval tests, three rebinding tests, seven executed source-operator tests plus one skipped exporter-location test. |
| Adversarial receipt check, before/after patch | **Reproduced / fixed** | Before patch, cross-mode `PASS` accepted and imported. After patch, cross-mode status, changed archive receipt bytes and missing archive receipts are refused. |
| Historical 43 nonterminating jobs' routing schedule | **43/43 COMPLETE-SCHEDULE, 73 exact splits** | Regenerated independently with real source-bound stages and the pinned historical summary. **Routing only**; no certification of FIR magnitudes or 43 spectral intervals. |
| Non-dyadic boundaries and endpoint coverage | **PASS targeted tests** | Exact rational branch crossings at 300, 600, 900 Hz; additional nontrivial L/M crossing at 500 Hz; stationary interiors compared with separate point-routing implementation; subintervals meet at exact endpoints. |
| One real source-bound campaign job with 0.03-second certificate deadline | **PASS behavior** | Atomically published `OPEN` with `interval_wall_clock_budget_exhausted`, never a PASS. Same output on restart with larger budget was unchanged/idempotent. A test-only mock bypassed only the expensive full-worklist summary, not operator binding, actual certificate deadline or receipt publication. |
| Directed interval recurrence cross-check | **PASS diagnostics** | 595 independently computed, 100-digit mpmath spectral point magnitudes (85 randomized coefficient sets, 7 frequencies each) fell inside the implemented interval enclosures. Targeted tests also compared the accelerated recurrence to the older independent direct-trigonometric interval implementation. This does **not** by itself prove the entire frequency continuum. |
| Full 72-cell exact frequency schedule | **PASS coverage construction** | 11,516 intervals, with canonical rational endpoints and no partition gaps, independently constructed from 72 active cells and confirmed by coverage tests. Coverage construction is not proof completion. |
| Actual historical receipt reuse across optimized source binding | **REFUSED AS INTENDED** | The 5,112 old archived receipts are tied to frozen `src/rate_poly_fir0.h` SHA `928f...fede6ff` and old capture-script SHA, rather than the current `bd86...00846de23b7` and current capture-script identity. They were neither rewritten nor relabeled. |
| P15 full-band certified replay | **NOT RUN/NOT VERIFIED** | Thousands of missing/OPEN spectral intervals; previous 43 stalls were routing-replayed, not numerically completed. No release PASS asserted. |

The independent algebra checks support the conservative construction: exact rational inverse-stage/phase splits; every enumerated source path is either explicitly bounded or included through a high-rate FIR L1 subtree majorant; upper contributions are summed coherently by absolute magnitude, never RMS or a magnitude cutoff. Adversarial behavior for non-dyadic splits, node budgets and `OPEN` dispositions passed. They do not substitute for a complete source-bound, continuous-frequency proof of all normative intervals.

**New commands executed, alongside those above:**

```sh
PYTHONPATH=tests/dsd python3 -m unittest -v test_p15_campaign_corrective_synthetic
PYTHONPATH=tests/dsd python3 tests/dsd/p15_boundary_schedule_replay.py --output /tmp/P15_REPLAY.json
PYTHONPATH=tests/dsd python3 -m unittest -v \
  test_p15_opt_source_rebind test_p15_src_bound_operator
```

An earlier exploratory aggregate supplied the replay test with a temporary path to a newly generated replay file; the **final corrected delivery tree instead includes that file at the preexisting test location**. The final 31-test aggregate was rerun, unmodified, from the clean delivery tree; the log is `integrated_out_of_box_tests.log` in the evidence archive. A larger, unselective P15 numerical suite exceeded an execution limit while scanning the whole worklist; it is **not** counted as a pass. The original defect reproducer mini-archive was not present, so its exact independent checksum could not be established.

## D. P15 qualification ledger

| Obligation from governing design/acceptance | State | Basis / next gate |
|---|---|---|
| Opt-in rational-FIR C execution, supported build, counts/FIFO/phase correctness | **Locally verified** | Real builds, binary64 exact reference tests, ASan/UBSan-focused check, CLI equivalence. Keep default off. |
| Deterministic source-bound coefficient/phase-stage identity for 24 SRC realizations / 72 matrix cells | **Locally verified as captured realized source operators** | Independently rebuilt exporter and 24/24 byte-matching snapshots; does not prove every arithmetic butterfly of the FFT stage. |
| Exact rational interval partition and all-stage branch enumeration | **Locally verified for covered cases** | Boundary and point-routing tests; 43 historical schedule-only replays with 73 exact splits. |
| Directed interval and complete hierarchical alias accounting | **Algorithm and bounded local tests pass; full certificate OPEN** | Independent point containment checks and targeted source-bound interval regressions passed. No full 11,516-job spectral acceptance replay; compiler/runtime mathematical correctness not elevated on sample tests. |
| Absolute composite passband ripple <= 0.0001 dB for **all** applicable effective passbands | **OPEN** | Existing local PASS receipts are not a full continuous-frequency coverage certificate. No weakening of 0.0001-dB requirement permitted. |
| Coherent unwanted folded aliases and stopband transfer <= -160 dB everywhere required | **OPEN** | Some real local stop/pass receipts, but large OPEN and absent coverage. All affected alias contributions must be bounded in final independent replay. |
| Independently bounded same-realized-operator numerical errors (including input-dependent FIR and SRC arithmetic) | **OPEN** | Frozen binary64 coefficient identity and execution agreement do not discharge `N_ops`, `B_coeff`, `B_other`, and arbitrary-input FFT4G butterfly/twiddle/overlap-save roundoff. |
| Ideal Kaiser-design-generator equivalence beyond *captured realized binary64 operator* | **Not a new acceptance obligation for the captured-W comparison** | The governing acceptance explicitly distinguishes ideal-design equivalence from independent same-realized-operator qualification. Do not add unnecessary proof. |
| Historical 5,112 partial receipts / 43 stalled intervals | **Historically evidenced / current-source reuse inadmissible; 43 routing schedules verified** | Pinned history is not current-source mathematical proof. 43 were not spectrally closed here; no historical PASS relabeling. |
| Prepared physical DSD256 P/S-matched >=2x comparator and other platform gates | **OPEN / historical review only** | Archived physical evidence checker passed its scoped archived-record tests. No eligible prepared-host experiment, new physical 2x CI or full matched spectral-comparator replay was conducted. Microbench/short CLI timing cannot substitute. |
| Promotion/default flip/P16 authorization | **BLOCKED** | Requires separate versioned release decision after all mandatory numerical, coverage and physical gates close. |

**History in the supplied archive:** the pinned partial campaign reports 11,516 total jobs, 5,112 receipts (392 local passband PASS, 3,989 local stop/source PASS, 731 OPEN), 6,361 never attempted, and 43 additional intervals observed as nonterminating. These are *historical self-reported records*, not independent completed spectral measurements during this review. Their count/summary hashes were checked, and their source binding differs from the current optimized source.

## E. Implementation disposition, artifact contract and reproducibility

The corrected implementation is **ready for opt-in repository integration but not P15 certification**. There is no demonstrated need to change `src/rate_poly_fir0.h`, modify SRC coefficient generation, lower numerical thresholds, alter FFT4G, or redesign the campaign architecture. The companion patch intentionally changes only:

```text
tests/dsd/p15_src_stagewise_continuum.py
tests/dsd/p15_full_band_campaign.py
tests/dsd/test_p15_campaign_corrective_synthetic.py  [new]
tests/dsd/results/P15_campaign_dispatch_corrective_2026-10-17/SCHEDULE_REPLAY.json  [new, schedule-only test fixture]
```

The first path contains the prior campaign correction unchanged. The next two contain the minimal independent integrity fixes. The fourth is the deterministic, nonqualifying 43-job routing replay fixture required by the existing integration test. Existing `p15_src_branch_bound.py` and `p15_src_interval_recurrence.py` are verified identical to the corrective's reference dependencies; they were not patched.

**Artifacts:**

1. `P15_INDEPENDENT_VALIDATION_REPORT.md` - this report.
2. `P15_MINIMAL_INTEGRATION_CORRECTIVE.patch` - directly applies to the supplied original *rebinding full archive* (not a guessed git commit).
3. `P15_SRC_INDEPENDENT_CORRECTED_FULL_2026-10-17.tar.gz` - complete corrected source tree and this report/patch/checksum ledger, built from a pristine extraction of the provided rebinding archive.
4. `P15_VALIDATION_EVIDENCE_2026-10-17.tar.gz` - bounded newly executed test logs, independent replay, benchmark rows and cross-check scripts.
5. `P15_DELIVERY_SHA256SUMS.txt` - downloadable final artifact checksums.

**Recommended next action:** Integrate this small patch with the existing opt-in build contract and run the ordinary repository CI on the integration host. Subsequent P15 work should target the specific **open numerical/continuous-frequency and physical comparator gates**, not speculative C/SRC rewrites or more receipt machinery. Do not claim completion of those gates from this report.

**Remaining limitations:** No original gap mini-archive for independent replay; no prepared physical DSD256 target; no full historical 5,112-receipt recomputation; no all-11,516 spectral continuum completion; no arbitrary-input FFT4G roundoff proof; no full application-wide ASan/UBSan-instrumented library; and short CLI timing is not a statistically controlled platform qualification. These limitations are **not** retroactively classified as code defects in an otherwise correct, still-opt-in implementation.
