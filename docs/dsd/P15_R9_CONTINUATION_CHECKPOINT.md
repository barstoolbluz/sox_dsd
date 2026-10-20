# R9 checkpoint (2026-10-19) — independently complete eight-cell v2 DSD256 source-stop mathematics

## Immutable source and proof identity

- Original `sox_ng-P15-adjudicate-cc399928.tar.gz`: SHA-256 `d058b3908817e01e937f49e0dfeee7194d847aae74f625043e881d8b8f0e9210`.
- R6/R7 combined addon and R8 high-rate addon are prior prerequisites for the thin R9-only addon. Alternatively use the complete cumulative R6–R9 addon.
- Original R9 native witness: `tests/dsd/results/P15_R9_UNIFORM_STOP_2026-10-19/uniform_native_stop.json`.
- The independent native replay: 179/179 accepted; output SHA-256 `303c019d7d1fd664344075e54a0d453b551023f935b3a5fe6cbbfd4e36bdab1c`.
- Three exact whole-stage witnesses in `tests/dsd/results/P15_R9_STRONG_SRC_2026-10-19/`.
- Final eight-cell independent result: `tests/dsd/results/P15_R9_ALL_V2_DSD256_STOP_VERIFIED.json` (source/method binding inside).
- DO NOT modify any version-locked proof implementation without intentionally invalidating/reproving affected witness receipts. Method SHA changes are deliberately checked.

## Reproduction

From `sox_ng/` after applying cumulative proof addon to the pristine original source:

```
PYTHONPATH=tests/dsd python3 -m unittest -q test_p15_r9_uniform_math test_p15_r9_strong
PYTHONPATH=tests/dsd python3 tests/dsd/p15_r9_src_strong.py --prove-all --witness-dir tests/dsd/results/P15_R9_STRONG_SRC_2026-10-19 --native-certificate tests/dsd/results/P15_R9_UNIFORM_STOP_2026-10-19/uniform_native_stop.json --out /tmp/r9_reverified.json
```

A true complete replay recomputes all 179 native leaves and all 330 strengthened SRC stage leaves, then checks each rate's exact factors and acceptance inequality. It need not trust the producer's PASS fields.

## Scope and remaining obligations

- Eight v2 DSD256 SRC-active cells' source-stop half: **958/958 PASS**.
- Unique R7 + R8 + R9 independently qualified: **1023/11516**, with **10493 remaining**.
- Other eight native-profile families and wanted/passband certificates are **not automatically qualified** by this theorem. Their native filter coefficients/stop edge differ.
- A reusable norm factorization for source-stop is now implemented. Prefer adapting it *per distinct native profile*, reusing independently qualified SRC stage graph bounds by rate-pair. Do not repeatedly regenerate each of the historical source-stop frequency intervals.
- FFT4G arbitrary-input actual ELF roundoff and final build correspondence remain separate P15 obligations.

## Engineering constraints

No production DSP modifications, no changed spectral thresholds, no historical certificate overwrites, no invented run-provenance. All archives must remain under 140 MB. Run adversarial mutations and fresh-extraction smoke tests for future changes. Report OPEN rather than treating unproved cases as PASS.
