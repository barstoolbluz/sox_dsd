# Independent verification checkpoint 03 — final

Date: 2026-10-18. This checkpoint supersedes the unfinished-work status in checkpoints 01 and 02 without altering them.

## Completed canonical cells

All four target cells have complete independent canonical aggregation and exact normative admission of the recorded outward certificate bounds. The reports collectively cover 1,012 distinct canonical jobs: 340 passband and 672 native-source stopband jobs.

| Cell | Passband jobs | Native-stop jobs | Total verified | Retained OPEN attempts |
|---|---:|---:|---:|---:|
| dsd256.mastering.pcm384000 | 40 | 192 | 232 | 0 |
| dsd256.wideband.pcm384000 | 142 | 192 | 334 | 0 |
| dsd256.mastering_v2.pcm384000 | 66 | 192 | 258 | 0 |
| dsd256.wideband.pcm192000 | 92 | 96 | 188 | 20 |

The mastering → 384-kHz cell uses the preserved v1 proof implementation and independent exact normative readjudication. The other three cell reports select only the final corrected proof implementation. Each report verifies exact canonical work identities, exhaustive closed frequency coverage, source/design/operator/coefficient snapshot and proof-code bindings, population and proof-tree metadata, and the recorded conservative scalar inequalities.

The wideband → 192-kHz report uses the ordered union of `campaign_final_strict_60s`, `diagnostics/wide256_192000_6000_7000_final_180s`, and `campaign_final_retry_180s`. It retains every one of the 20 earlier cell OPEN receipts. The 188 selected PASS receipts cover the closed passband [0, 91,200] Hz and the native-stop test output-coordinate range [0, 96,000] Hz, with the native-source stop edge at 176,400 Hz. The last passband interval is 200 Hz wide. All 9,408 paths are retained, including two paths per primitive native-source family. Larger configured retry budgets are reported as recorded; a retry elapsed time below 60 seconds is not evidence that more than 60 seconds was mathematically or computationally necessary.

These aggregators do not replay the numerical interval computations, and the receipts do not retain full per-leaf proof transcripts. Every report explicitly records `numerical_proof_replayed: false` and `internal_leaf_proof_transcripts_available: false`. The numerical proofs remain tied to the captured implementations, inputs, dependency assumptions, and independent numerical tests.

## Final scalar readjudication

`normative_readjudication_02` admits all 8,273 recognized PASS receipts in its frozen scan inventory: 6,835 original canonical, 36 historical 600-second, four third-pass local, and 1,398 current high-rate receipts. This is a count of receipt instances, not distinct newly certified intervals. All source and design pins match. Recorded operator identities match for 1,402 receipts; 6,871 historical receipts do not record those operator identities, which are therefore not invented by this checker. There are no insufficient-field, failed-inequality, invalid, or unparsed-input cases.

Each admission binds the original receipt SHA-256 to exact rational comparisons against the normative ripple and alias limits. The old threshold widening defect is bypassed for these admitted bounds; it is not retroactively declared a sound decision algorithm. Minimum positive conservative amplitude margins in this inventory are:

| Recorded bound | Minimum margin |
|---|---:|
| Coherent alias upper | 1.1393386744058241e-14 |
| Native-stop transfer upper | 2.0319624783930328e-13 |
| Total passband transfer upper | 5.650170406980919e-6 |
| Wanted passband transfer lower | 5.650432178661057e-6 |

The report stores exact rational margins and the responsible receipt hashes. The initial final scan took 3.592 seconds with 109,684 KiB peak RSS; an exact-inventory replay took 3.639 seconds with 120,008 KiB peak RSS, and every published top-level artifact remained byte-identical. Both used Python 3.12.14, CPU 8, nice level 15. Run commands and measured resource use are preserved in `FINAL_READJUDICATION_RUN.json` and `FINAL_READJUDICATION_REPLAY_RUN.json`.

## Reproduction and safe continuation

Run the independent scalar verifier from the repository root with the frozen inventory; a fresh unconstrained scan would also inspect later reporting JSON and would no longer describe precisely the same input inventory:

```sh
python tests/dsd/results/P15_high_rate_2026-10-18/complete_cell/readjudicate_displayed_bounds.py \
  --root . \
  --inventory tests/dsd/results/P15_high_rate_2026-10-18/complete_cell/normative_readjudication_02/scan_inventory.json \
  --output tests/dsd/results/P15_high_rate_2026-10-18/complete_cell/normative_readjudication_02
```

This command was actually replayed successfully against the published output. It is idempotent only for exactly matching bytes. Use a new output directory when changing any input or verifier implementation.

To verify the fourth cell again without writing evidence:

```sh
python tests/dsd/results/P15_high_rate_2026-10-18/complete_cell/verify_complete_cell.py \
  --root . \
  --cell dsd256.wideband.pcm192000 \
  --receipts tests/dsd/results/P15_high_rate_2026-10-18/campaign_final_strict_60s \
  --receipts tests/dsd/results/P15_high_rate_2026-10-18/diagnostics/wide256_192000_6000_7000_final_180s \
  --receipts tests/dsd/results/P15_high_rate_2026-10-18/campaign_final_retry_180s
```

Each complete-cell output contains its own `verifier_snapshot.py`. Use that preserved version when reproducing an older report byte-for-byte; the earlier mastering report predates the final proof-registry addition in the current verifier. New registries belong in new report directories. The scalar verifier and complete-cell aggregator require only Python's standard library; numerical proof replay needs the pinned dependencies described in the integration README.

The final inherited-file audit is complete: all 16,711 pinned files and all 33,487 broader inherited files remain byte-identical to the baseline. The audit output is byte-identical to the initial audit. Its run evidence is preserved in `../authority/final_integrity_2026-10-18/`. The four modified and twelve new source/test files, integration patch, numerical proof implementations, and historical receipts have not been changed by this final verification.

All final verification evidence is now frozen. The parent task owns final coverage aggregation, continuation, and packaging. P15 remains BLOCKED. Physical comparator adjudication, absent historical replay payloads, and arbitrary-input FFT4G execution-roundoff obligations are separate and remain open; these spectral results do not promote v2 or authorize P16.

## Artifact identities

### dsd256.mastering.pcm384000

Directory: `master256_384000_v1_complete`.

- `verification.json`: `fbf18769ee4944fff5ac29e194b67645e9b33d230a8512e97ff3bb2ff76d4424`
- `SHA256SUMS`: `0d89a2b6ad9e254d99f5a305e5bb09487a2bfd4ee2257904301d13b6f4840789`
- `receipt_sha256.txt`: `d48cb753c1eeb39ed3b6d6d90f8124ae5d52f0e33a287603c1040c096f2ad24d`

### dsd256.wideband.pcm384000

Directory: `wide256_384000_final_complete`.

- `verification.json`: `139784a69ee08ca6c2afe45fd821e5af09a7dfa4bf9b2a2344cc2d1f6a6f7942`
- `SHA256SUMS`: `fe14072bd3826bd36084ad631e24fc2c750dcb1d5b8c5f0c884f602f7da7fb63`
- `receipt_sha256.txt`: `4a347d034cea713c8fcf3c4ce58e5ad3910773d05c0f21bc1b71d1f378e356e3`

### dsd256.mastering_v2.pcm384000

Directory: `mastering_v2_256_384000_final_complete`.

- `verification.json`: `13d8e29821ca01e73738ec51caccbebcc11af5eb506b5e1f7d96b41540cd90ff`
- `SHA256SUMS`: `64ccb9139623ab89298ec8417b85e77672ac6107eedc76560c0364f0d210da9c`
- `receipt_sha256.txt`: `99e9015046e917fbec449ec5c3af1d62406874fb4bddccef072e3f5ae9096b9b`

### dsd256.wideband.pcm192000

Directory: `wide256_192000_final_complete`.

- `verification.json`: `808f0df78a9a85452c468636e8ce01381d96135df18bf11e8be922898d59cfb7`
- `SHA256SUMS`: `a599320535ff96cce569afcc14e6d6277528d1673dad8900268aa410f037134d`
- `receipt_sha256.txt`: `11834c878db2ff58e872eaed8996bb66079d2a431682383867b1d11f07fcf80a`

### Final scalar readjudication

- `verification.json`: `c05f47b16e5f33831187ec38a3da5924dbc0a8c0047b6d48a4bd25df75fc763c`
- `SHA256SUMS`: `675e189d0380abc1b0298de64f00ac66c7e244cf50e8cbb0a34dcd3486dde603`
- `EXACT_NORMATIVE_RECEIPTS.sha256`: `cbf41de0201832e2818c9cfea89943b7a7feffbb86d7bbb8c7c7d9fded596556`
- `scan_inventory.json`: `963aee5ac0be59174e415b56dd0e414d5ad13a7fbc7b30512e89e2eb8412a740`
