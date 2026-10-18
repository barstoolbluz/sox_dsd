# P15 high-rate certification — completed implementation and continuation

**Date:** October 18, 2026. **Disposition:** the selected high-rate implementation and certification assignment is complete; **P15 remains BLOCKED**. No v2 default promotion or P16 authorization is made.

This checkpoint describes actual completed evidence. All paths below are relative to `tests/dsd/results/P15_high_rate_2026-10-18/` unless a repository-root path is shown. Earlier checkpoints, failed experiments, timed-out receipts, and proof versions remain preserved. Continue from this document and the final manifests rather than from a partial campaign snapshot.

## 1. Completed spectral coverage

Four previously difficult DSD256 cells now have exhaustive canonical interval coverage:

| Cell | Closed guaranteed passband, Hz | Native source stop edge, Hz | Stop test output coordinates, Hz | Pass / stop intervals | Total |
|---|---:|---:|---:|---:|---:|
| `dsd256.mastering.pcm384000` | 0–40,000 | 80,000 | 0–192,000 | 40 / 192 | 232 |
| `dsd256.wideband.pcm384000` | 0–141,120 | 176,400 | 0–192,000 | 142 / 192 | 334 |
| `dsd256.mastering_v2.pcm384000` | 0–66,000 | 80,000 | 0–192,000 | 66 / 192 | 258 |
| `dsd256.wideband.pcm192000` | 0–91,200 | 176,400 | 0–96,000 | 92 / 96 | 188 |
| **Total** | | | | **340 / 672** | **1,012** |

The first three cells contain all **824** canonical DSD256 → 384-kHz obligations. The last wideband pass intervals are exactly 120 Hz at 384 kHz and 200 Hz at 192 kHz. The 91,200-Hz effective edge is the existing normative intersection with `0.475 * 192000`; the declared wideband profile P and S were not changed. Native-source stop certificates bound all applicable source aliases while sweeping the stated output-coordinate range. They do not redefine the native-source stopband.

The mastering → 384-kHz cover uses the frozen first high-rate proof implementation. Its retained outward scalar bounds independently satisfy the exact normative limits despite the inherited policy-threshold defect discussed below. The other three complete covers use the final corrected proof. Every version analyzes the same unchanged, source-bound captured coefficient operator. Do not describe all historical candidate receipts as executions of the final implementation.

Final accounting is in `coverage_final_01/` and the full structural census is in `census_final_01/`:

| Accounting population | Count |
|---|---:|
| Original canonical schedule | 11,516 intervals |
| Original 60-second PASS population | 6,835 |
| Explicit prior union: original + historical 600-second sample + four third-pass locals | 6,873 |
| Distinct canonical candidate PASS intervals in the selected current runs | 1,148 |
| Candidate PASS intervals originally OPEN | 1,082 |
| Candidate PASS intervals beyond all explicitly included prior evidence | 1,063 |
| Originally passing intervals also passed by a selected candidate | 66 |
| Original-plus-current union | 7,917 |
| Explicit-prior-plus-current union | 7,936 |
| Canonical intervals without a PASS in that explicit union | 3,580 |

All 1,148 selected candidate jobs eventually passed. There are zero candidate-OPEN jobs without another included candidate PASS; 10,368 canonical jobs have no selected candidate measurement. Those numbers describe this selection, not a complete rerun of the 11,516-job campaign. The 3,580 remaining coverage gaps are not established mathematical violations or current-prover timeouts. The explicitly included prior union is not an inventory of every historical proof in the repository.

All nine 384-kHz cells received candidate measurements. Beyond the three complete DSD256 cells, candidate coverage is 11/212 for DSD64 mastering, 10/228 for DSD64 wideband, 11/217 for DSD64 mastering_v2, 12/222 for DSD128 mastering, 12/263 for DSD128 wideband, and 13/240 for DSD128 mastering_v2. DSD256 mastering and mastering_v2 at 192 kHz have 12/136 and 12/162 candidate passes respectively. Selected high-population 96-kHz and cross-family 44.1-kHz cases are also retained. These partial cells must not be called complete.

`coverage_final_01/CELL_COVERAGE.json` is the exact per-cell matrix. `coverage_final_01/CLASSIFICATION.jsonl` records all canonical jobs, observed dispositions, reasons, and work hashes. The census adds source rate, profile, output rate, frequency location/width, exact routing and source-stop crossings, stage composition, path/family multiplicity, and a structural effort proxy. The proxy is not a wall-time prediction. `coverage_final_01/BOUNDARY_COVERAGE.json` separates planned coverage from actual candidate PASS neighborhoods at DC, band edges, Nyquist relabelings, rational routing boundaries, and source-stop membership crossings.

## 2. The final implementation

The smallest useful numerical changes were:

1. **A certified complete halfband-pair bound.** For the admitted exact captured halfband, `H(x)=1/2+Q(x)` with real Q and `Q(x+1/2)=-Q(x)`. Therefore `|H(x)|+|H(x+1/2)|=max(1,2|Q(x)|)`. A directed continuous enclosure over the entire closed quarter-cycle yields a reusable pair upper bound. Complete subtree bounds follow by induction, retaining every alias path and its original frequency mapping. Invalid patterns or topology fall back to the old bound.
2. **Earlier return when finalized terminal upper bounds require frequency subdivision.** A directed sum of finalized leaf upper endpoints detects that further population expansion cannot make that particular enclosure acceptable. The returned bound still includes the whole remaining frontier. This avoids wasted work before subdivision; it is neither a transfer lower bound nor a spectral-violation witness. The disabled-optimization reference remains available.
3. **Exact coefficient-word cache identity.** Validate finite binary64 inputs before cache lookup and key by signed index, `float.hex()` words, and precision. This prevents equal-valued non-floats or signed-zero equality from bypassing admission or conflating recorded identities.
4. **Correction of inherited policy-threshold rounding.** The old helper converted acceptance endpoints to outward binary64 diagnostics and thereby slightly widened the allowed band. Synthetic binary64 FIR counterexamples demonstrated false PASS decisions. The final helper serializes the complete directed threshold intervals exactly. PASS compares against their inward endpoints; generic FAIL compares against the outward endpoints; ambiguity remains OPEN. Normative tolerances are unchanged.

The halfband pair upper is approximately 1.0000000077254763. Five levels give approximately 1.0000000386273817, compared with 248.07333464780757 from the earlier complete-branch L1 product. This is a bound improvement, not a 248-fold runtime claim. The global proof used 55 nodes and 28 closed accepted intervals and took 0.062666953 seconds after stage loading.

The retained diagnostic for canonical job 596 demonstrates the terminal obstruction: a 19–19.2-kHz parent segment had one finalized path upper above the alias limit, while both narrower children passed. The new criterion avoided exhausting thousands of additional aliases on that parent. It did not exploit unproved phase cancellation. The wideband → 192-kHz cell retains 9,408 full paths for 4,704 primitive source families; all multiplicity is included. The two selected 96-kHz cases retain 18,816 full paths.

Construction, induction, admissibility, exact arithmetic, directed rounding, phase conventions, counterexamples, and limitations are specified in `P15_high_rate_methods_2026-10-18.md`. The source change is confined to proof/test/support files. The original bounded campaign dispatcher, production DSP code, filter coefficients, normative documents, and release policy are unchanged.

## 3. Completed numerical runs and performance

The final 60-second campaign in `campaign_final_strict_60s/` completed all **927** jobs: **905 PASS and 22 OPEN**, all OPEN reasons being `interval_wall_clock_budget_exhausted`. Seven workers used CPUs 0–6, with 60-second Python signal deadlines and independently enforced 85-second process deadlines, 128 maximum proof nodes, and 20,000 maximum paths. There were no execution failures or external kills.

All 22 final OPEN jobs subsequently passed using the same final proof implementation, with 180-second signal budgets and 205-second external process deadlines. Twenty were wideband → 192-kHz passband jobs; the other two were the selected 18,816-path 96-kHz passband jobs. The latter completed in 103.818284 and 76.137560 seconds. Some successful replays completed below 60 seconds, so the larger allowance is not proved necessary for every job. Retry CPU affinities differ from the main campaign and their times are not matched acceleration measurements.

Dedicated job 6673 is retained in `diagnostics/wide256_192000_6000_7000_final_180s/`. The other 21 receipts are in `campaign_final_retry_180s/`. `execution/FINAL_RETRY_180S_PLAN.json` is the exact union of five disjoint slice plans. Every original OPEN remains intact. `report_preparation/WIDE256_192_RETRY_AUDIT_2026-10-18.md` records the identity and determinism review; unrecorded CPU/cache/frequency history is not assigned an invented causal explanation.

The final configuration selects **1,450 receipt instances across 12 labels**, containing 1,391 PASS and 59 retained OPEN attempts, for 1,148 distinct canonical jobs. Repeated attempts are not extra unique coverage. The final scalar inventory includes seven additional exploratory current PASS receipts outside this reporting selection.

Matched third-pass comparisons are separate from campaign throughput. In the 26-case terminal-saturation comparison, baseline/candidate outcomes were 22/26 PASS and the common 22 successful jobs took 342.244/219.087 seconds, a 1.562× ratio of sums. In the eight-case final corrected comparison, baseline/candidate outcomes were 5/8 PASS; the common five successful jobs took 64.825/35.532 seconds, a 1.824× ratio of sums. Deadline-censored pairs are excluded from those acceleration ratios. The inexpensive final 44.1-kHz DSD64 case was 0.910/0.885 seconds. Earlier candidate regressions are preserved, including a 9.94% slowdown on DSD256 → 44.1 kHz in the first high-rate comparison.

`P15_high_rate_benchmarks_2026-10-18.md` and the `performance/` JSON contain the measured memory, CPU, wall time, throughput, FIR/finite-difference counters, alias operations, proof nodes, exact splits, and subdivisions. Raw per-job receipts preserve actual imported module paths/hashes. Missing baseline instrumentation is null rather than fabricated. `report_preparation/P15_final_campaign_report_2026-10-18.md` and the retained accounting JSON report the completed final campaign and retries without mixing their resource arrangements into matched timing ratios. The corrected report supersedes the earlier addendum's CPU-assignment sentence: thirteen retries ran in single-worker CPU-7 invocations; the final nine ran with eight workers on CPUs 0–7. All earlier report bytes and numerical values are retained. The 949 attempts consumed 16,619.818 prover CPU-seconds, including unsuccessful first attempts, for 927 distinct certificates: 200.80 certificates per prover CPU-hour. Peak single-process RSS was 209,544 KiB; this is not the concurrent aggregate memory peak.

The recorded environment is Python 3.12.14, NumPy 2.3.5, SciPy 1.17.0, and mpmath 1.3.0 on an AMD EPYC 9V74 host, with an eight-CPU quota and 8-GiB memory limit. The experiments set OpenBLAS to one thread and record process affinity. These version records do not identify package binary hashes or establish interval-library correctness.

## 4. Independent verification and its exact limits

`complete_cell/` contains four exhaustive canonical covers, each with every selected work/receipt hash and captured dependencies. The verifiers independently rebuild the canonical schedule from pinned authority and worklists, check the source/operator/proof identities and counters, and compare the outward scalar summaries to exact rational enclosures of the unchanged normative limits.

The final `normative_readjudication_02/` inventory contains **8,273 PASS receipt instances**: 6,835 original, 36 historical 600-second, four third-pass local, and 1,398 current. All passed exact normative scalar checks, with no invalid, insufficient, or unparsed cases. All source/design pins match. Of these receipts, 1,402 record matching operator identities; 6,871 historical receipts do not contain that per-receipt metadata. Missing provenance was not synthesized. The final coverage union uses 8,266 of those PASS instances.

The rational threshold construction is independent of mpmath transcendental calls. The minimum independently bounded coherent-alias margin is 1.1393386744058241e-14 in amplitude. A second scan using the frozen inventory reproduced every top-level output byte-identically. Its verification digest is `c05f47b16e5f33831187ec38a3da5924dbc0a8c0047b6d48a4bd25df75fc763c`.

These are independent coverage, identity, and scalar-inequality checks. **The retained receipts do not contain complete internal per-leaf proof transcripts, and the aggregation did not numerically replay every interval.** Reports explicitly set `numerical_proof_replayed: false` and `internal_leaf_proof_transcripts_available: false`. Numerical replay requires the frozen proof code and source/operator inputs. Correct interval arithmetic, including the inherited mpmath trigonometric anchors, remains an explicit library assumption.

The final broad regression examined 137 tests: 134 passed and three executable-dependent tests were skipped in this source-only environment; wall time was 59.020533 seconds and peak RSS 272,520 KiB. All 169 frozen Python-source hashes remained unchanged. A subsequent strengthened eight-test population suite explicitly disabled early return for its exhaustive reference, required every edge to be evaluated, and compared with exact rational sums of independent complex upper products. All eight passed. Census/report tests and stdlib-only complete-cell/readjudication tests are preserved separately. Earlier failed test constructions and corrected expectations remain in the evidence.

## 5. Source and integration integrity

The submitted baseline archive has SHA-256:

```text
d0bd8a65a149f4267a4d33bb8763aa56faa937ae78009a9796a9b31bcd2e04c4
```

The final inherited audit reverified **16,711 previously pinned files** and **33,487 broader inherited files** byte-identical, including all 35 operator source pins, all 276 original `src/` files, all 149 original `docs/dsd/` files, and all 33,050 original historical result files. The original sorted 16,711-file inventory digest was reproduced despite different archive member order.

`integration/P15_high_rate.patch` changes exactly four original files and adds twelve Python files. Its SHA-256 is:

```text
0d0e5b7663b411ff3931f0af26bc820dff6f4e70edc6f872944077e4514007d7
```

An actual GNU patch 2.7.6 application with `-p1 --fuzz=0 --batch --forward` succeeded on isolated exact preimages. All sixteen postimages match the best repository; no rejected hunks, additional source paths, or baseline mutations occurred. Follow `integration/README.md`, preimage/postimage manifests, and `applicability/RESULT.json`. Copy the evidence into a previously absent directory after applying the source patch.

The final proof snapshot is `reference_high_rate_final_code/IDENTITY.json`. In particular:

| File | SHA-256 |
|---|---|
| `p15_src_continuum_bounds.py` | `2656e0fafac58a6d4cffd19002f6ff22d5a851f4e730afd9ab6e70c684f7f1b5` |
| `p15_src_branch_bound.py` | `7a298cf8356b732de8a16f10dd824677694478f20c436438c971ae8e477dd583` |
| `p15_src_stagewise_continuum.py` | `def3efee896a27008f5dbef2e8bfb8a6fab98d8a167d6ad9cd9e9a78ee6ce83d` |
| `p15_src_halfband_majorant.py` | `e3fda2f3e7a53bc1cd574949909ec574d37ebd4bd1dbb5f969251b2a91b1d580` |
| `p15_high_rate_experiment.py` | `1dbaf498e8127facf0bab4a72916a1bba5f7d3785f8d1babb028e071a68bcd57` |

The complete delivery archive preserves every unchanged original tar payload and link directly from the submitted archive; only the four validated source preimages may be replaced. The packager rereads both archives and verifies all payload hashes, completed report identities, integration applicability, and the absence of source/evidence changes during packaging. The accompanying delivery validation and SHA-256 files give actual output archive hashes. Neither an archive filename nor this checkpoint substitutes for that validation.

The first packaging attempt stopped correctly on an unsubmitted temporary WAV in an old negative-selftest directory. It was an exact 4,718,592-byte prefix of the intact 5,644,880-byte submitted waveform, present in all extracted/frozen trees but absent from the archive and historical receipt map. Its generating process is unconfirmed. Only the extra work-tree pathname was moved into `packaging/preexisting_residue/`, preserving its bytes and metadata; the intact original and every original receipt remain unchanged. `packaging/RESIDUE_PROVENANCE.json` records the prefix check. The first partial archive is explicitly invalid and is not a final deliverable.

## 6. Reproduce without overwriting evidence

Run from the extracted repository root with the versions in `integration/requirements-proof.txt` installed. This session additionally used `/workspace/scratch/47ef0cb747fa/deps` on `PYTHONPATH`; that workspace-specific path is not required elsewhere.

### Validate the exact final reporting inputs

```sh
sha256sum -c tests/dsd/results/P15_high_rate_2026-10-18/execution/FINAL_AGGREGATION_INPUTS_02.sha256

PYTHONPATH=tests/dsd OPENBLAS_NUM_THREADS=1 python3 tests/dsd/results/P15_high_rate_2026-10-18/execution/aggregate_final.py \
  --config tests/dsd/results/P15_high_rate_2026-10-18/execution/FINAL_AGGREGATION_CONFIG_02.json \
  --readjudication tests/dsd/results/P15_high_rate_2026-10-18/complete_cell/normative_readjudication_02/verification.json \
  --check-only
```

Configuration 02 is mandatory; the script default remains configuration 01. To publish a new copy, use the same arguments with fresh `--census-output` and `--report-output` directories, following `execution/FINAL_AGGREGATION_RECIPE_02.md`.

### Replay the independent scalar checks

```sh
python3 tests/dsd/results/P15_high_rate_2026-10-18/complete_cell/readjudicate_displayed_bounds.py \
  --root . \
  --inventory tests/dsd/results/P15_high_rate_2026-10-18/complete_cell/normative_readjudication_02/scan_inventory.json \
  --output /absolute/path/to/new-scalar-verification
```

Use the captured inventory so later report JSON cannot change the scan population. For byte-identical complete-cell report reproduction, use each directory's `verifier_snapshot.py`; the original mastering report predates later additions to the verifier registry. For example, a read-only verification of the final wideband → 192-kHz union is:

```sh
python3 tests/dsd/results/P15_high_rate_2026-10-18/complete_cell/wide256_192000_final_complete/verifier_snapshot.py \
  --root . --cell dsd256.wideband.pcm192000 \
  --receipts tests/dsd/results/P15_high_rate_2026-10-18/campaign_final_strict_60s \
  --receipts tests/dsd/results/P15_high_rate_2026-10-18/diagnostics/wide256_192000_6000_7000_final_180s \
  --receipts tests/dsd/results/P15_high_rate_2026-10-18/campaign_final_retry_180s
```

### Numerically replay a hard interval

```sh
PYTHONPATH=tests/dsd OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
timeout --signal=KILL 205s python3 tests/dsd/p15_high_rate_experiment.py \
  --source-root . --job-index 5195 --label independent-final-replay \
  --seconds 180 --max-nodes 128 --max-paths 20000 \
  --output /absolute/path/to/new-numerical-receipts
```

This is DSD256 mastering → 96 kHz, 39–40 kHz passband, with 18,816 complete paths. Match CPU affinity and the saved environment when comparing timing. The internal Python signal is a soft computation deadline; the external command terminates the process. A killed or unfinished run yields no spectral certificate.

To rerun a whole selected plan with process-group termination, use `execution/run_experiments.py` with the saved plan, `--source-root`, fresh `--output`, and the recorded `--workers`, `--cpu-start`, `--seconds`, and `--external-seconds`. It preserves idempotent per-work publication. Historical performance replay requires separate complete source trees overlaid with their corresponding flat proof snapshots; the harness checks actual imports. Do not import a flat snapshot as if it were a complete repository or mutate a proof tree while a process is running.

## 7. What remains unproved, and how to continue

The six partially covered DSD64/DSD128 → 384-kHz cells and the remaining DSD256 mastering/mastering_v2 → 192-kHz intervals are the most direct spectral continuation. Select missing canonical work from the final matrices, check the explicitly included prior receipts, and run bounded batches before changing mathematics again. The complete-cell successes show that conservative coherent magnitude summation suffices for those four operators; they do not establish sufficiency for every remaining cell.

Use new evidence directories and a new frozen plan for additional runs. Preserve the same exact source/operator and work identities. A budget change, proof change, or source change requires distinct attempt evidence. Retain all prior OPEN/PASS receipts, and refresh scalar readjudication and aggregation inventories when new PASS evidence is admitted. Avoid rerunning the whole 11,516-job schedule merely to replace historical dispositions. Source-stop membership crossings and routing transitions are distinct; profile the exact remaining cases before adding a new subdivision rule or phase-aware method.

Separate release obligations remain:

- **Arbitrary-input FFT4G execution roundoff is OPEN.** Exact captured-coefficient spectral bounds do not prove runtime transform, multiply/accumulate, finite-boundary, subnormal, or nonstandard arithmetic error bounds.
- **The physical DSD256 comparator measurements exist.** The October 16 P/S-matched experiment recorded eight comparisons, all lower 95% bootstrap endpoints above 2; the minimum was 3.6289395223087637. Statistics were independently recomputed. The recorded status is `MEASURED_PHYSICAL_UNADJUDICATED`, not release qualification. Its eight recorded source pins match, but the binding excludes a later opt-in SRC header change; exact historical binaries and twelve audio payloads are unavailable here. Formal scope/adjudication and missing replay material are distinct from missing measurements.
- **The early one-cell v2 metrology gap is stale.** The later retained matrix has 27 scalar cells, 108 forced-ISA jobs, and 48 detailed comparisons with matching recorded source pins and available graph payloads. Its 135 omitted numeric arrays limit independent numerical replay. Observation completeness does not supply arithmetic or spectral qualification, and no new release policy was created.

`authority/AUTHORITY_FINDINGS.md`, `authority/SECONDARY_OBLIGATIONS.json`, and the final inherited integrity reports preserve the full evidence and qualifications. No source-bound production spectral violation was established by this work. The synthetic threshold counterexamples are verifier defects, not violations by a production filter. **P15 remains BLOCKED.**
