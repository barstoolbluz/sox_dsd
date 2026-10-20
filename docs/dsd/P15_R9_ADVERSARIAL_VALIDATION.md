# P15 R9 adversarial and reproducibility record

Source: original archive SHA-256 `d058b3908817e01e937f49e0dfeee7194d847aae74f625043e881d8b8f0e9210`.

Executed (from the original source with R6/R7/R8/R9 additive proof overlays):

```
PYTHONPATH=tests/dsd python3 -m unittest -v test_p15_r9_uniform_math test_p15_r9_strong
PYTHONPATH=tests/dsd python3 tests/dsd/p15_r9_uniform_stop.py --verify tests/dsd/results/P15_R9_UNIFORM_STOP_2026-10-19/uniform_native_stop.json --out /tmp/r9-native.json
PYTHONPATH=tests/dsd python3 tests/dsd/p15_r9_src_strong.py --verify-stages --witness-dir tests/dsd/results/P15_R9_STRONG_SRC_2026-10-19
PYTHONPATH=tests/dsd python3 tests/dsd/p15_r9_src_strong.py --prove-all --witness-dir tests/dsd/results/P15_R9_STRONG_SRC_2026-10-19 --native-certificate tests/dsd/results/P15_R9_UNIFORM_STOP_2026-10-19/uniform_native_stop.json --out /tmp/r9-all-eight.json
```

- Native-domain candidate: 179 contiguous rational intervals, `0..88200`, with exact stop boundary `80000`.
- Native fresh independent replay: status PASS, 179/179; output byte-for-byte identical to saved initial verification output (`303c019d7d1fd664344075e54a0d453b551023f935b3a5fe6cbbfd4e36bdab1c`).
- Three new independent full-FIR proof witnesses: 165 + 66 + 99 leaves, strict global caps 1.01 / 1.10 / 1.01.
- Complete eight-cell second replay: PASS, **958/958 canonical source-stop jobs**, strict `<1e-8` in every cell.
- `test_p15_r9_uniform_math`: 12/12 PASS, including exact folded-frequency domain, 64-harmonic family coverage, missing-harmonic refusal, duplicate-stage refusal, coefficient/method pinning, and forged lower bound refusal.
- `test_p15_r9_strong`: 9/9 PASS, including bad coefficient hash, altered kernel hash, altered cap, omitted first leaf, missing final endpoint, OPEN witness, and noncanonical endpoint refusals.
- Production DSP C files untouched.

Additional tests and QA will be recorded in the release QA record when the combined artifact has been extraction-tested. A certificate is qualified only after the verifier returns PASS with current method/source identities, not because its embedded candidate status says CANDIDATE.
