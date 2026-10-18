# Final high-rate report assembly outline

**This is a plan and accounting specification, not a coverage snapshot.** No running-campaign counts are frozen here. The final report must be generated only from immutable receipts, recognized complete proof snapshots, and strict readjudication of their stored numerical bounds.

## 1. Lead with actual certification coverage

Report the exact number of newly covered canonical jobs, the verified complete cells, and every remaining OPEN. A complete cell requires one valid PASS witness for every canonical interval, plus exact shared-endpoint coverage of passband [0, effective P] and native-source-stop output range [0, Fout/2]. State that these are ideal-coefficient spectral results and that P15 remains BLOCKED.

## 2. Distinguish the three evidence unions

- Original reported campaign: 6,835 local PASS and 4,681 OPEN, permanently historical.
- Prior evidence included by this census: the original campaign, the historical 600-second sample, and four third-pass final local receipts. This is not a claim to inventory every historical proof in the archive.
- Current selected experiments: unique canonical PASS jobs from explicitly labeled baseline and candidate runs. Report candidate-only progress separately from baseline measurements, and deduplicate jobs across proof versions and budgets.

Every PASS receipt contributing to a final union must have strict normative bound readjudication by exact receipt SHA. The inherited dB-to-amplitude threshold conversion defect must be described, and the readjudication must be explicitly distinguished from replay of the numerical proof. Preserve the original reported disposition regardless of readjudication.

## 3. All nine 384-kHz cells and all three DSD256 192-kHz profiles

The union of the four named plans below selects 1,148 distinct canonical jobs. The following counts are planned scope only. They are not PASS counts.

| Cell | Effective P (Hz) | Native S (Hz) | Canonical pass + stop | Original OPEN | Selected jobs |
|---|---:|---:|---:|---:|---:|
| dsd128.mastering.pcm384000 | 30000 | 60000 | 30 + 192 | 220 | 12 |
| dsd128.mastering_v2.pcm384000 | 48000 | 60000 | 48 + 192 | 240 | 13 |
| dsd128.wideband.pcm384000 | 70560 | 88200 | 71 + 192 | 263 | 12 |
| dsd256.mastering.pcm192000 | 40000 | 80000 | 40 + 96 | 136 | 12 |
| dsd256.mastering.pcm384000 | 40000 | 80000 | 40 + 192 | 232 | 232 |
| dsd256.mastering_v2.pcm192000 | 66000 | 80000 | 66 + 96 | 162 | 12 |
| dsd256.mastering_v2.pcm384000 | 66000 | 80000 | 66 + 192 | 257 | 258 |
| dsd256.wideband.pcm192000 | 91200 | 176400 | 92 + 96 | 188 | 188 |
| dsd256.wideband.pcm384000 | 141120 | 176400 | 142 + 192 | 282 | 334 |
| dsd64.mastering.pcm384000 | 20000 | 40000 | 20 + 192 | 212 | 11 |
| dsd64.mastering_v2.pcm384000 | 25000 | 40000 | 25 + 192 | 217 | 11 |
| dsd64.wideband.pcm384000 | 35280 | 44100 | 36 + 192 | 228 | 10 |

The four intended complete cells have 232, 334, 258, and 188 canonical intervals respectively. The 232 master256→384 intervals belong to the first high-rate proof implementation campaign; the other complete targets are scheduled for the final corrected prover. Their unchanged captured operators allow individually valid receipts from recognized proof versions to coexist.

## 4. Use explicit proof-version names

- Third-pass baseline: untouched initial prover, retained in `reference_third_pass_code/`.
- First high-rate candidate: subtree/halfband population work, retained in `reference_high_rate_v1_code/`.
- Second high-rate candidate: terminal saturation and exact coefficient-word cache identity, retained in `reference_high_rate_v2_code/`.
- Final corrected candidate: exact inward acceptance thresholds and exact bound endpoint serialization, to be identified by its actual frozen snapshot and receipt module map.

These are proof implementation versions. They are independent of the `mastering_v2` decode profile and the old v1/v2 profile matrices. No decode-profile default, production filter, release policy, or P16 authorization changes are implied.

## 5. Boundary coverage and limitations

All nine 384-kHz cells, all three DSD256→192 profiles, and both maximum-population DSD256→96 cells have selected pass/stop DC intervals, upper passband edge intervals, output Nyquist intervals, and exact interior routing transitions. A closed interval starting at DC covers all frequencies arbitrarily close to zero; no sampled-frequency substitute is needed.

The complete native source family lattice is half-open [−Fnative/2, Fnative/2). Its Nyquist family relabels at output f congruent to −Fnative/2 modulo primitive spacing. The additional five jobs in `EXTENDED_BOUNDARY_PLAN.json` put the 1,200-Hz relabeling strictly inside 1,000–2,000 Hz for sparse selections that previously covered only one side. The final machine-readable boundary audit must distinguish planned intervals from actual PASS intervals and record point, left-neighborhood, and right-neighborhood coverage.

Native-source-stop membership crossings at f congruent to ±S modulo primitive spacing are separate from routing transitions. Stop certificates use output coordinates while bounding the complete applicable native-source population. Do not describe an output job near numerical S as a direct source-frequency sweep, and do not invent an acceptance band inside the native transition region.

The two DSD256→96 maximum-population cells have 18,816 complete paths, 9,408 primitive native source families, and multiplicity two. The selected 44.1-kHz conversions add rational upper endpoints and different rational stage compositions. The corpus is not an exhaustive search for the largest numerical cancellation; cancellation, near-zero transfer, exact phase retention, and malformed populations are covered by independent adversarial tests appropriate to the implemented magnitude methods.

## 6. Classify only demonstrated obstructions

Keep UNMEASURED distinct from current OPEN. Report third-pass baseline PASS within observed budgets, current candidate PASS of original OPEN, originally structural cases now certified, and same-proof 60-second OPEN with a larger-budget PASS. Credit larger budgets only when proof-code hashes, max-nodes, max-paths, and profiling mode agree; do not credit a simultaneous code improvement to the budget.

Repeated numerical work, population expansion, loose bounds, structural support, and actual violations require supporting profiles or witnesses. A timeout alone does not distinguish these causes. Keep exact OPEN reasons and attempt references in the matrix. An operator-path cap is a resource limit unless the code demonstrates structural non-support.

## 7. Performance and correctness evidence

Use complete-prover paired runs only when source/operator identities, budgets, harness, affinity, Python, and numerical-library versions match. Separate censored timeouts from PASS/PASS speedups, and retain regressions. Report counters absent from baseline instrumentation as null. Distinguish profiling runs from ordinary timing runs, and bind every result to its actual proof snapshot.

Explain the normative threshold correction separately from population-performance improvements. Require independently checked exact bound readjudication for older receipts, and retain slower arithmetic references and complete branch-population tests. Python SIGALRM is not an enforceable process termination boundary; cite the external runner limits separately.

## 8. Final artifact relationships

`COVERAGE_REPORT.md`, `CELL_COVERAGE.json`, `CLASSIFICATION.jsonl`, `COMPLETE_CELL_WITNESSES.json`, `BOUNDARY_COVERAGE.json`, and `MATCHED_BENCHMARKS.json` will be generated together with a SHA-256 manifest from one frozen census. The final continuation checkpoint must name these artifacts, all proof snapshots, exact restart commands, and unresolved obligations. Historical and intermediate snapshots stay unchanged.

## Plans bound by this outline

| Plan | SHA-256 |
|---|---|
| `execution/CAMPAIGN_PLAN.json` | `a253ed57294bb5a433298260acd3cfef18314831137dd99a8758f2066876d8d3` |
| `execution/CAMPAIGN_FINAL_MAXPOP_PLAN.json` | `db8cf23cc829d7147980edb6ef699b55a4b2f53bcd87b3f6c0a4fdde98943b8f` |
| `execution/MATCHED_FINAL_PLAN.json` | `1976b73efbd79a6c0b3ad0bf44c3ae0cee846b758d173d76d6c84d12d0a8c0f9` |
| `execution/EXTENDED_BOUNDARY_PLAN.json` | `8ddad23e7b3d5f90831ab57b0cf2a9368fe47a8723ab0f5a2bb0339ea9fd8951` |

The final extended execution plan may combine these sets; it must be a new immutable file and preserve all referenced plan files.
