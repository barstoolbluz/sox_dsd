# P15 high-rate continuation — checkpoint 05

Captured 2026-10-18T21:01:00.664984+00:00. This archive is a verified incremental overlay for the supplied third-pass source. Counts are calculated from the exact archived bytes.

## Three complete DSD256 to 384 kHz cells

| Profile | Passband intervals | Native-source stop intervals | Total |
|---|---:|---:|---:|
| mastering | 40, closed [0, 40,000] Hz | 192, output coordinates [0, 192,000] Hz | **232 / 232** |
| wideband | 142, closed [0, 141,120] Hz | 192, output coordinates [0, 192,000] Hz | **334 / 334** |
| mastering_v2 | 66, closed [0, 66,000] Hz | 192, output coordinates [0, 192,000] Hz | **258 / 258** |

All **824 canonical obligations** have source-bound continuous-frequency PASS receipts and independent exact worklist/coverage/scalar-envelope verification. The independent aggregation does not rerun the internal numerical proof trees. Its reports explicitly retain `numerical_proof_replayed: false` and `internal_leaf_proof_transcripts_available: false`.

The mastering cell uses frozen high-rate v1 receipts plus exact normative readjudication. Wideband and mastering_v2 use the final corrected proof. Their complete-cell reports are under `complete_cell/master256_384000_v1_complete/`, `complete_cell/wide256_384000_final_complete/`, and `complete_cell/mastering_v2_256_384000_final_complete/`. The latter verification SHA-256 is `13d8e29821ca01e73738ec51caccbebcc11af5eb506b5e1f7d96b41540cd90ff`.

## Current campaign and remaining work

The final 927-job campaign is still running. This checkpoint contains **630** of its receipts: `{"OPEN": 2, "PASS-LOCAL-BAND": 244, "PASS-LOCAL-STOP-SOURCE": 384}`. Recorded main-campaign OPEN indices: `[6673, 6678]`. These receipt-instance counts are not a deduplicated historical coverage union.

DSD256 wideband to 192 kHz is the fourth complete-cell target, with 92 passband and 96 native-source stop jobs. Its 6–7 kHz interval (canonical 6673) exhausted 60 seconds. A separate same-proof replay with 180 seconds allowed and 205 seconds external supervision **passed in 53.463893 seconds**, with alias upper 8.857247788022856e-9. The original timeout used 59.882869 CPU seconds; the replay used 51.965266 CPU seconds. This proves replay feasibility and observed timing sensitivity; it does not show that more than 60 seconds is intrinsically required. The successful replay is preserved in `diagnostics/wide256_192000_6000_7000_final_180s/`.

Other OPEN intervals must remain recorded. After all 927 main jobs finish, run a fresh bounded retry plan for remaining selected gaps if useful. Do not reinterpret a timeout as a mathematical violation. Use a new output directory and record the final proof, exact jobs and resource limits. The prepared draft aggregation configuration 02 will add successful retry evidence; original configuration 01 and its input manifest remain unchanged.

## Best implementation and completed validation

The best source is the final candidate3 proof: exact complementary-halfband complete-subtree bound, terminal upper saturation, exact binary64-word cache identity, and exact serialization of full directed normative threshold intervals. The preceding finite-difference kernel is unchanged. No production DSP code, filter coefficient, normative tolerance or release-policy file changed.

The 137-test numerical regression passed with 3 expected source-only skips. Supplemental independent population checks, reporting checks, and exact-rational policy tests are retained. The integration patch changes 4 inherited files and adds 12 files; GNU patch application and all 16 postimage hashes are verified. Patch SHA-256: `0d0e5b7663b411ff3931f0af26bc820dff6f4e70edc6f872944077e4514007d7`.

The fresh final-policy matched run is complete: baseline 5 PASS/3 OPEN, candidate 8 PASS/0 OPEN. Common-pass wall sums 64.825→35.532 seconds. The broader 26-pair v2b run has 22→26 passes and 342.244→219.087 common-pass wall seconds. Methods and performance reports are complete; raw controls, per-process RSS, counters and timing qualifications are retained.

The final inherited-integrity rerun again verified all 16,711 previously pinned files and 33,487 broader inherited files unchanged. The independent physical measurements exist and exceed the recorded 2× threshold but remain unadjudicated; full historical payload replay is incomplete. Arbitrary-input FFT4G execution roundoff remains unproved. **P15 remains BLOCKED**, with no v2 default promotion or P16 authorization.

## Exact resume

1. Verify the original source archive SHA-256 `d0bd8a65a149f4267a4d33bb8763aa56faa937ae78009a9796a9b31bcd2e04c4`. Extract it, overlay this checkpoint's `sox_ng/`, and run `sha256sum -c P15_CHECKPOINT_05_SHA256SUMS` from that repository root.
2. Use Python 3.12.14, NumPy 2.3.5, SciPy 1.17.0 and mpmath 1.3.0. Follow `integration/README.md` for isolated source reconstruction and actual-import checking. The final 15-module proof map is in `reference_high_rate_final_code/IDENTITY.json`.
3. Resume `execution/CAMPAIGN_FINAL_STRICT_PLAN.json` using `execution/run_experiments.py`, the final proof source, output `campaign_final_strict_60s`, 7 workers on CPUs 0–6, 60-second signal and 85-second external limits. Preserve the source/resource identity; changed identities require a new directory.
4. Complete necessary bounded retries; aggregate the fourth cell from all applicable final-proof receipt directories, preserving its OPEN attempts. The independent verifier supports repeated `--receipts` arguments.
5. After all selected jobs and retries are frozen, publish `complete_cell/normative_readjudication_02/verification.json`. Finish configuration 02 and invoke `aggregate_final.py --config ...` into new `census_final_01` and `coverage_final_01` directories. Every contributing PASS must occur with its exact hash in the refreshed scalar-admission manifest.
6. Finalize the persistent continuation. The prepared `package_final.py --aggregation-config ...` checks report/source/config identities, independently verified complete-cell manifests, exact patch applicability and the entire source inventory; it then creates and re-reads full and compact archives. Final archives have not yet been generated in this checkpoint.

The original history and every earlier checkpoint remain preserved. Durable upload is blocked by the reported storage limit; this local checkpoint is downloadable.
