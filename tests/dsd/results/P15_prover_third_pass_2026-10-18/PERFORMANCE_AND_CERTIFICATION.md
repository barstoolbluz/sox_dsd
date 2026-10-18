# P15 third pass — actual measured outcomes

October 18, 2026. Everything here is **local ideal-coefficient continuous-frequency certification**, not a 72-cell release adjudication.

## Matched, isolated same-host proof

DSD128 mastering to 384 kHz PCM; entire 0–1,000 Hz passband, 40-second budget, same captured source/operator and unchanged normative envelope. Runs in separate fresh Python processes. Both returned `PASS-LOCAL-BAND`:

| Variant | Wall seconds | Peak RSS KiB | Stage interval evaluations | Cheap difference upper uses | Tree nodes |
|---|---:|---:|---:|---:|---:|
| Second pass (exact isolated source) | 25.387 | 171,440 | 835 | 0 | 3 |
| Third pass (frozen code) | 13.233 | 171,440 | 978 | 192 | 3 |

**Measured complete-prover speedup: 1.918x.** The newer evaluation count includes the 192 cheap global difference bounds; it is not a count of equally expensive Taylor evaluations. This is not a generic machine-independent speed claim.

On the identical 20-second budget the second-pass implementation returned `OPEN` (budget exhausted after 20.004 s), while the frozen third-pass implementation returned `PASS-LOCAL-BAND` after 12.790 s. The same stopband cell's 150–151 kHz native-source interval likewise changed from 20.004-second `OPEN` to rigorous `PASS-LOCAL-STOP-SOURCE` at 14.372 s.

## Other source-bound final local passes

All four intervals below have newly published, replayable, verifier-code-hash-bound receipts in `final_local_certificates/`. They were ALL `OPEN` from the ORIGINAL 60-second canonical campaign; this does not mean all were still OPEN under the SECOND-pass code.

| Source profile → PCM | Kind | Full local interval | Final result | Conservative unwanted/source-stop upper |
|---|---|---|---|---:|
| DSD128 mastering → 384 kHz | Pass | 0–1,000 Hz | `PASS-LOCAL-BAND` | 9.934e-9 |
| DSD256 mastering → 384 kHz | Pass | 0–1,000 Hz | `PASS-LOCAL-BAND` | 9.959e-9 |
| DSD256 mastering → 44.1 kHz | Pass | 0–1,000 Hz | `PASS-LOCAL-BAND` | 9.777e-9 |
| DSD128 mastering → 384 kHz | Native-source stop | 150–151 kHz | `PASS-LOCAL-STOP-SOURCE` | 9.952e-9 |

The DSD256 mastering → 44.1 kHz interval was also shown to pass using the isolated SECOND-pass prover (8.295 seconds, 20-second budget); it is **not** claimed as a gain attributable to the finite-difference change. It is newly certified relative to the original historical campaign. The two 384 kHz DSD128 local band passes above have clear second-pass/third-pass matched-budget evidence.

## Arithmetic-only representative cost

On the actual 4,160-tap SRC FIR at a source-bound normalized image frequency of `2/5`, nine warm same-process evaluations had median 59.793 ms using the retained full rigorous Taylor evaluator and 0.295 ms using the rigorous finite-difference upper: **about 203x cheaper for that stage upper**. These two enclosures are not equally tight; the short-cut is used only when the global upper is already small enough. This result is NOT a production audio speedup or a full-prover speedup. Original raw cost data: `FIR_WARM_EXACT_DIFFERENCE.json`.

## Test and preservation status

- 68 regression-test executions: 65 passed, 3 expected skips, **zero failures**. The pre-existing deadline test's race in its own busy-loop checking was fixed without changing production deadline implementation.
- Original pinned source and historical receipt comparison: 16,711 files byte-identical. `ORIGINAL_SOURCE_INTEGRITY.json` records categories and original archive hash.
- One final 44.1 kHz source-bound local receipt was recomputed with identical SHA-256, proving idempotent exclusive publication for that identity.
- The temporary adaptive Taylor trial was **discarded** after end-to-end measurements and is explicitly segregated under `exploratory_adaptive_trials/`. One contaminated baseline measurement is retained only under `quarantined_invalid_baseline/` and is never used in the comparisons.
- The overall optimized 11,516-interval campaign was NOT re-executed; no extrapolation from these selected hard cases is made.

**Release:** BLOCKED. Full mathematical coverage and independent FFT4G and DSD256 physical-comparator obligations remain outstanding. Historical statuses remain historical, not overwritten.
