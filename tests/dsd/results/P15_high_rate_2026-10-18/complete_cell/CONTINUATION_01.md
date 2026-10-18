# Complete-cell and exact-normative verification checkpoint 01

Date: 2026-10-18. This checkpoint precedes completion of the final corrected campaign. It records completed work, not planned coverage.

## Completed and immutable

- `master256_384000_v1_complete/verification.json` verifies all 232 canonical jobs of `dsd256.mastering.pcm384000`: 40 passband intervals cover [0, 40000] Hz, and 192 native-stop test intervals cover output coordinates [0, 192000] Hz. Every summary passes independent exact normative comparisons. The report SHA-256 is `fbf18769ee4944fff5ac29e194b67645e9b33d230a8512e97ff3bb2ff76d4424`.
- `normative_readjudication_01/verification.json` checks all 7,316 preserved PASS summaries in its frozen input inventory: 6,835 original, 36 larger-budget, 4 third-pass local, and 441 current high-rate receipts. All satisfy the strict exact normative scalar comparisons. Report SHA-256: `1bf0b4e97c30bc4cf1601141697829d98f79666df925df73d8b88dc0e365ea56`. Its exact receipt admission list SHA-256 is `354715013a400176cb3edd3373cc653bd4f256a1cd7fa9043bf1a6598176d878`.
- The current `verify_complete_cell.py` supports the four explicitly reviewed cells in README.md and recognizes the frozen v1, v2b, and final corrected 15-module proof snapshots. Its SHA-256 is `822bee04cb5c1b58f00d842a2b8eb1ce3f813364e103ccef6c5e2a3e52e34824`.
- The independent scalar scanner SHA-256 is `7688080d67d2200f2e7cdcfc5334620a5ab6b0ffa383a138eb54a537ba2c31f9`. It never imports `db_band` or the numerical prover.
- The final registry test run contains 18 successful aggregation and scalar-admission tests, with 0 failures/errors and 0 skips. `TEST_FINAL_REGISTRY_LOG.txt` and `TEST_FINAL_REGISTRY_RUN.json` retain source hashes, Python version, CPU 8 affinity, nice 15, timing, and peak memory. No test changed a source file.
- Earlier verifier versions and test logs remain under `pre_union_verifier` and the existing immutable reports. Each report keeps its precise verifier snapshot. Replaying an earlier report with a newer identity registry can legitimately change report bytes; use its own snapshot for byte-identical reproduction.

## Mathematical and evidentiary scope

The exact scalar checks deliberately avoid the inherited outward-binary64 policy-threshold defect. They convert displayed binary64 bounds to exact rationals and compare them with separately proved rational enclosures of the exact normative limits. A failed admission is an insufficient certificate summary, not a production-filter violation.

Each complete-cell aggregation reconstructs the canonical plan, validates source/operator/proof/harness identities and every required job, checks recorded tree and population consistency, verifies exact scalar inequalities, and proves closed canonical interval coverage. The original receipts do not contain their internal per-leaf proof trees. These independent reports therefore state `numerical_proof_replayed: false` and `internal_leaf_proof_transcripts_available: false`. Full interval arithmetic and internal transition proofs remain the responsibility of the pinned, replayable numerical prover.

The broader inherited audit and secondary-obligation review are in `../authority`. All 16,711 previously pinned files and 33,487 inherited files in the broader inventory were unchanged. P15 remains BLOCKED; the physical measurements exist but are unadjudicated, numerical metrology payloads are incomplete, and arbitrary-input FFT4G execution remains unproved. See `../report_preparation/SECONDARY_OBLIGATIONS_REVIEW.md` for final-report prose.

## Resume after the final campaign freezes

The final corrected campaign directory is `../campaign_final_strict_60s`. The parent process also runs final matched experiments. Wait until those immutable receipts are complete before producing the final scan, so the coverage report has one stable admission inventory.

From the repository root, run the stdlib-only scanner into a **new** output directory:

```sh
python tests/dsd/results/P15_high_rate_2026-10-18/complete_cell/readjudicate_displayed_bounds.py \
  --root . \
  --output tests/dsd/results/P15_high_rate_2026-10-18/complete_cell/normative_readjudication_02
```

To reproduce that exact scan while new unrelated files are added, use the scanner snapshot in its output directory with `--inventory` pointing to its `scan_inventory.json`. The scanner checks the frozen file hashes. It preserves missing historical per-receipt operator/prover hashes as missing; it does not invent them.

Run each additional complete cell against the explicitly ordered campaign union. For example:

```sh
python tests/dsd/results/P15_high_rate_2026-10-18/complete_cell/verify_complete_cell.py \
  --root . \
  --cell dsd256.wideband.pcm384000 \
  --receipts tests/dsd/results/P15_high_rate_2026-10-18/campaign_candidate_60s \
  --receipts tests/dsd/results/P15_high_rate_2026-10-18/campaign_final_strict_60s \
  --output tests/dsd/results/P15_high_rate_2026-10-18/complete_cell/wideband256_384000_final_union
```

The other reviewed targets are `dsd256.mastering_v2.pcm384000` and `dsd256.wideband.pcm192000`. Use a distinct new output directory for each. Expected canonical counts are 334, 258, and 188 respectively. Those are obligations, not current completion claims. A missing/OPEN job or invalid target receipt must keep the aggregate OPEN; no count may be inferred from a nearby job. A later valid PASS can fill a prior OPEN while preserving both attempt hashes.

The final coverage agent will admit selected witnesses only when their exact receipt SHA appears in `normative_readjudication_02/EXACT_NORMATIVE_RECEIPTS.sha256`, and separately validate source/operator identities. It will not silently upgrade historical statuses. Do not overwrite an old report, immutable raw receipt, or proof snapshot when resuming.
