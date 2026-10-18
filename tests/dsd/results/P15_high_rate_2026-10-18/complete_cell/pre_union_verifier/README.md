# Independent complete-cell receipt verification

This verifier addresses **`dsd256.mastering.pcm384000`** only. It does not modify the frozen numerical prover, campaign dispatcher, production operator, or acceptance policy.

## What is checked

The script uses Python's standard library. It independently reconstructs the complete canonical schedule from the immutable v1/v2 worklists, the native coefficient manifests, and the band definitions in the SHA-pinned `docs/dsd/DSD_DESIGN.md`, sections 6.1 and 6.5. Its 11,516-job schedule must match the separately obtained canonical-plan digest:

`6f9a3d3721c5ccef8ee919c87087181a5d9deb93dc2375e7dae9d8d4468fcd5c`

The selected cell contains exactly 232 jobs, at canonical indices 5597–5828. Its 40 passband intervals exhaust the closed output-frequency range [0, 40,000] Hz. Its 192 native-stop-source intervals exhaust [0, 192,000] Hz in **output coordinates**, checking the transfer from all native-source harmonics with absolute source frequency at least 80,000 Hz. The stop interval is not a redefinition of the native-source stopband.

Each expected 1,000-Hz work item must have its exact canonical job digest as its receipt filename. Source/design maps, the captured stage snapshot, the operator binding, all 15 recorded prover modules, and the experiment harness must match fixed SHA-256 identities. The 35 pinned source dependencies are hashed directly. The verifier refuses changed profiles, frequencies, status/mode substitutions, missing certificate bounds, altered limits, nonfinite numbers, duplicate JSON keys, inconsistent tree counters, omitted native alias paths, and incomplete canonical coverage. The expected full inverse-path population for this operator is 9,408: 64 native inverse branches times 147 branches of the rational SRC stage.

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

All these calculations use exact rational arithmetic. The identity `log(10) = 3*log(2) + log(5/4)` gives a rapidly converging enclosure using 40 terms for each logarithm. The near-unity gain values use eight terms. To ensure that rounding or insufficient series accuracy cannot create a false acceptance, the lower gain is tested against the **upper** enclosure of the negative logarithmic threshold, and the upper gain against the **lower** enclosure of its positive threshold. Failure establishes only that the displayed bound is inadequate; it is not a spectral-violation witness.

## Endpoint scope and limitations

Closed canonical intervals include DC, the 40-kHz guaranteed passband edge, and the 192-kHz PCM Nyquist endpoint. In the numerical prover, exact rational inverse-stage transitions partition each interval. Both adjacent analytic FIR limits cover a shared branch-relabeling endpoint by continuity. Native-source stop membership conservatively includes a harmonic for the entire subinterval whenever either endpoint touches or exceeds 80 kHz. All signed native aliases are represented on a half-open source Nyquist interval; the opposite Nyquist label is the same sampled-frequency family. The native Nyquist frequency is 5,644,800 Hz.

The receipts retain aggregate inequality bounds and operation counts, **not the complete per-leaf proof transcript**. This independent script verifies the canonical union and displayed aggregate inequalities. It does not independently enumerate every internal rational transition or rerun every FIR interval enclosure. Correct per-leaf arithmetic, exact alias partitioning, and their endpoint arguments remain inherited from the SHA-pinned numerical prover and its independent tests. The report sets `numerical_proof_replayed: false` and `internal_leaf_proof_transcripts_available: false` explicitly. Reproducing a numerical certificate requires running the captured numerical proof implementation on the same canonical job; this aggregation script alone is not such a replay.

The source snapshot preserves the exact recorded source/operator/prover/harness dependencies. It does not reconstruct the exporter binary, prove nonlinear coefficient generation, or identify the numerical package binaries used by each original process. The experiment records numerical-library versions; those version records are not package-byte hashes. The stationary captured-coefficient certificate does not discharge arbitrary-input FFT4G execution-roundoff, finite-stream metrology, physical comparator adjudication, or the remaining P15 cells. **P15 remains BLOCKED.**

## Reproduction

From the repository root:

```sh
python tests/dsd/results/P15_high_rate_2026-10-18/complete_cell/test_verify_complete_cell.py

python tests/dsd/results/P15_high_rate_2026-10-18/complete_cell/verify_complete_cell.py \
  --root . \
  --receipts tests/dsd/results/P15_high_rate_2026-10-18/campaign_candidate_60s
```

Without `--output`, verification is read-only. Add `--output` pointing to a **new** directory to publish the report, all expected canonical jobs, receipt SHA-256 manifest, and a copy of every pinned dependency. Publication is idempotent for byte-identical results and refuses conflicting overwrites. A complete result has status `COMPLETE_CANONICAL_RECEIPT_COVERAGE_VERIFIED`; missing, invalid, or OPEN jobs produce OPEN and exit status 2. The release disposition is always separate and BLOCKED.

The focused aggregation test uses temporary synthetic receipts to exercise false-completion attacks, including a single missing stop interval, an OPEN interval among PASS intervals, invented work, endpoint substitutions, changed proof/source/operator identities, missing fields, malformed counters, acceptance-boundary values, and nonfinite JSON. Synthetic receipts are not published as spectral evidence. A separate Decimal calculation at 120-digit precision checks the rational logarithm enclosure empirically; the remainder argument above supplies its mathematical justification.
