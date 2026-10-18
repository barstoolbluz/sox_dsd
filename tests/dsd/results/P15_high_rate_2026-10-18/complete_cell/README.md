# Independent complete-cell receipt verification

This verifier addresses four explicitly reviewed DSD256 cells. It does not modify the frozen numerical prover, campaign dispatcher, production operator, or acceptance policy.

| Cell | Passband output range, Hz | Native source stop edge, Hz | Stop test output range, Hz | Canonical pass/stop intervals | Full paths / primitive native families |
|---|---:|---:|---:|---:|---:|
| `dsd256.mastering.pcm384000` | 0–40,000 | 80,000 | 0–192,000 | 40 / 192 | 9,408 / 9,408 |
| `dsd256.wideband.pcm384000` | 0–141,120 | 176,400 | 0–192,000 | 142 / 192 | 4,704 / 4,704 |
| `dsd256.mastering_v2.pcm384000` | 0–66,000 | 80,000 | 0–192,000 | 66 / 192 | 9,408 / 9,408 |
| `dsd256.wideband.pcm192000` | 0–91,200 | 176,400 | 0–96,000 | 92 / 96 | 9,408 / 4,704 |

These are expected obligations, not assertions that every campaign has completed. Only each cell's generated verification report states actual coverage. The wideband → 192-kHz effective passband follows the normative intersection with `0.475 * 192000`; it does not change the profile's declared 141,120-Hz P or 176,400-Hz S.

## What is checked

The script uses Python's standard library. It independently reconstructs the complete canonical schedule from the immutable v1/v2 worklists, the native coefficient manifests, and the band definitions in the SHA-pinned `docs/dsd/DSD_DESIGN.md`, sections 6.1 and 6.5. Its 11,516-job schedule must match the separately obtained canonical-plan digest:

`6f9a3d3721c5ccef8ee919c87087181a5d9deb93dc2375e7dae9d8d4468fcd5c`

The original mastering → 384-kHz target contains exactly 232 jobs, at canonical indices 5597–5828. Its 40 passband intervals exhaust the closed output-frequency range [0, 40,000] Hz. Its 192 native-stop-source intervals exhaust [0, 192,000] Hz in **output coordinates**, checking the transfer from all native-source harmonics with absolute source frequency at least 80,000 Hz. The stop interval is not a redefinition of the native-source stopband. The other three targets use the same independently reconstructed schedule, with the obligations shown above. The final wideband pass intervals are 120 Hz wide at 384-kHz output and 200 Hz wide at 192-kHz output; no rounded-up or shortened edge is accepted.

Each expected work item must have its exact canonical job digest as its receipt filename. Source/design maps, the captured stage snapshot, the operator binding, all 15 recorded prover modules, and the experiment harness must match fixed SHA-256 identities. The 35 pinned source dependencies are hashed directly. The verifier refuses changed profiles, frequencies, status/mode substitutions, missing certificate bounds, altered limits, nonfinite numbers, duplicate JSON keys, inconsistent tree counters, incorrect recorded native-alias path populations, and incomplete canonical coverage. The mastering → 384-kHz full inverse-path population is 9,408: 64 native inverse branches times 147 branches of the rational SRC stage. Wideband → 192 kHz has two full inverse paths per primitive native source family. An aggregation check based only on 4,704 unique family labels would fail to establish complete path accounting.

Three proof implementations are separately recognized by embedded 15-module hash maps: the first halfband-cap implementation; the second implementation with terminal saturation and exact coefficient-word cache identity; and the final corrected implementation with full directed threshold intervals serialized exactly. Their flat snapshots are `reference_high_rate_v1_code`, `reference_high_rate_v2_code`, and `reference_high_rate_final_code` under the high-rate evidence directory. The verifier checks these snapshots rather than substituting whichever implementation happens to be installed in `tests/dsd`. Unknown intermediate versions are refused. Each receipt must match its version's operation-counter schema.

Repeat `--receipts` to form an ordered union of campaign directories. The first independently validated PASS in the supplied directory order supplies that job's coverage. An earlier OPEN remains recorded when a later PASS fills the gap; another later PASS also remains a separate attempt. All attempts and their hashes are retained in the report. No receipt is overwritten or silently superseded, and an invalid or unrecognized target receipt makes the aggregation fail closed.

A complete local proof has a binary split tree, so its recorded counters must satisfy `nodes = 2*leaves - 1`, `exact_splits + numerical_subdivisions = leaves - 1`, and `path_enumerations = 1 + 2*exact_splits`. These are consistency checks, not reconstruction of the internal proof tree.

## Independently checked inequalities

The frozen numerical prover explicitly converts every accepted interval endpoint to an outward binary64 display bound using `math.nextafter`. The maximum displayed upper bounds and minimum displayed lower bounds therefore remain conservative. Inspection of mpmath 1.3.0's `ctx_iv.py` and `libmp/libmpf.py` confirms that conversion of a positive normal point endpoint truncates to 53 bits (`round_fast = round_down`); one outward `nextafter` is sufficient. The verifier requires the receipt's mpmath version to be 1.3.0. Correct arithmetic, binary64 conversion, JSON round trips, and the recorded environment are still numerical-library assumptions, not consequences of checking a receipt hash.

Every recorded display value is converted to an exact rational representing its parsed binary64 value. Alias and native-stop upper bounds must be strictly less than the exact rational `1/100000000`. Passband bounds must satisfy

\[
L > 10^{-1/200000},\qquad U < 10^{1/200000}.
\]

The verifier checks these gain inequalities without mpmath or ordinary floating-point logarithms. For positive rational \(x\), put \(z=(x-1)/(x+1)\). The finite series

\[
2\sum_{k=0}^{n-1}\frac{z^{2k+1}}{2k+1}
\]

encloses \(\log x\) after adding a one-sided remainder of the same sign as \(z\), with absolute bound

\[
\frac{2|z|^{2n+1}}{(2n+1)(1-z^2)}.
\]

All these calculations use exact rational arithmetic. The identity `log(10) = 3*log(2) + log(5/4)` gives a rapidly converging enclosure using 40 terms for each logarithm. The verifier then precomputes exact rational enclosures of the two gain thresholds. For each positive argument \(t=\log(10)/200000\), use the first 12 exponential-series terms. If the first omitted term is \(a_{12}=t^{12}/12!\), its complete positive tail is at most \(a_{12}/(1-t/13)\). Apply this construction to both rational endpoints enclosing \(t\), and take interval reciprocals to obtain the negative-exponent threshold. Each receipt's lower gain must exceed the **upper** enclosure of `10**(-1/200000)`; its upper gain must be below the **lower** enclosure of `10**(1/200000)`. These stringent directions make insufficient enclosure accuracy fail closed. A separate eight-term rational log comparison remains covered by the focused test. Failure establishes only that the displayed bound is inadequate; it is not a spectral-violation witness.

During this pass, review found that the inherited `db_band` helper first converted tolerance endpoints to outward binary64 values and then used those widened values as decision thresholds. That allowed a very small enlargement of the normative acceptance region. The preserved receipt fields themselves already contain outward enclosures of the measured mathematical bounds. Their independent exact-threshold comparisons here therefore provide a valid scalar readjudication when all inequalities pass. This does **not** assert that the old decision algorithm was globally sound, and it does not silently change an old receipt. The corrected production proof helper is handled separately; this evidence script never uses `db_band`.

## Endpoint scope and limitations

Closed canonical intervals include DC, each effective guaranteed passband edge, and the applicable PCM Nyquist endpoint. In the numerical prover, exact rational inverse-stage transitions partition each interval. Both adjacent analytic FIR limits cover a shared branch-relabeling endpoint by continuity. Native-source stop membership conservatively includes a harmonic for the entire subinterval whenever either endpoint touches or exceeds the selected profile's S. All signed native aliases are represented on a half-open source Nyquist interval; the opposite Nyquist label is the same sampled-frequency family. The native Nyquist frequency is 5,644,800 Hz.

The receipts retain aggregate inequality bounds and operation counts, **not the complete per-leaf proof transcript**. This independent script verifies the canonical union and displayed aggregate inequalities. It does not independently enumerate every internal rational transition or rerun every FIR interval enclosure. Correct per-leaf arithmetic, exact alias partitioning, and their endpoint arguments remain inherited from the SHA-pinned numerical prover and its independent tests. The report sets `numerical_proof_replayed: false` and `internal_leaf_proof_transcripts_available: false` explicitly. Reproducing a numerical certificate requires running the captured numerical proof implementation on the same canonical job; this aggregation script alone is not such a replay.

The source snapshot preserves the exact recorded source/operator/prover/harness dependencies. It does not reconstruct the exporter binary, prove nonlinear coefficient generation, or identify the numerical package binaries used by each original process. The experiment records numerical-library versions; those version records are not package-byte hashes. The stationary captured-coefficient certificate does not discharge arbitrary-input FFT4G execution-roundoff, finite-stream metrology, physical comparator adjudication, or the remaining P15 cells. **P15 remains BLOCKED.**

## Reproduction

From the repository root:

```sh
python tests/dsd/results/P15_high_rate_2026-10-18/complete_cell/test_verify_complete_cell.py

python tests/dsd/results/P15_high_rate_2026-10-18/complete_cell/verify_complete_cell.py \
  --root . \
  --cell dsd256.mastering.pcm384000 \
  --receipts tests/dsd/results/P15_high_rate_2026-10-18/campaign_candidate_60s
```

Without `--output`, verification is read-only. Add `--output` pointing to a **new** directory to publish the report, all expected canonical jobs, receipt SHA-256 manifest, and a copy of every pinned dependency. Publication is idempotent for byte-identical results and refuses conflicting overwrites. A complete result has status `COMPLETE_CANONICAL_RECEIPT_COVERAGE_VERIFIED`; missing, invalid, or OPEN jobs produce OPEN and exit status 2. The release disposition is always separate and BLOCKED.

The focused aggregation test uses temporary synthetic receipts to exercise false-completion attacks, including a single missing stop interval, an OPEN interval among PASS intervals, invented work, endpoint substitutions, changed proof/source/operator identities, missing fields, malformed counters, acceptance-boundary values, and nonfinite JSON. It also checks all four normative endpoint schedules, all recognized proof versions, the two-path source-family multiplicity, and union behavior with retained prior OPEN/PASS attempts. Synthetic receipts are not published as spectral evidence. A separate Decimal calculation at 120-digit precision checks the rational logarithm enclosure empirically; the remainder argument above supplies its mathematical justification. The preparatory single-cell verifier and its 10-test result are preserved under `pre_union_verifier`; the final generalized verifier has 12 focused tests.
