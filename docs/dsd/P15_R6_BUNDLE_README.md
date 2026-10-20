# P15 R6 exact-integer spectral proof overlays

**Base source SHA-256:** `d058b3908817e01e937f49e0dfeee7194d847aae74f625043e881d8b8f0e9210` for `sox_ng-P15-adjudicate-cc399928.tar.gz`.

Artifacts:

- **Proof addon:** new files only; untar at the parent directory of a verified extracted original `sox_ng/` snapshot. Use a no-clobber extraction option (`tar -k`) rather than overwriting user changes.
- **Complete proof-source distribution:** includes the exact bound checker, proof records, the entire historical canonical receipt inventory and all pinned C/native/test source dependencies. It is *not* a replacement for the full original 49,323-member source tree or a production build source package.

Neither archive changes production DSP. No release gate is promoted on installation. The original campaign receipts remain reported historical data; only two individually named original jobs have new independent certificates.

Verify the original archive and install the addon safely:

```sh
sha256sum sox_ng-P15-adjudicate-cc399928.tar.gz
# Compare to the digest above; do not continue if it differs.
tar -xzf sox_ng-P15-adjudicate-cc399928.tar.gz -C /path/to/parent
# -k means refuse overwriting any existing file (both GNU and BSD tar).
tar -xzkf P15_R6_CC399928_EXACT_INTEGER_PROOF_ADDON.tar.gz -C /path/to/parent
cd /path/to/parent/sox_ng
sha256sum -c docs/dsd/P15_R6_ADDON_SHA256SUMS.txt
```

The full proof-source distribution is a smaller, independently runnable test source tree, not a full SoX-NG checkout. Extract it into a *new empty directory*; after extraction, run `sha256sum -c docs/dsd/P15_R6_PROOF_SOURCE_SHA256SUMS.txt` from its `sox_ng/` root. All distribution file hashes were verified on extraction in a second location.

Self-test:

```sh
cd sox_ng
PYTHONPATH=tests/dsd python3 -m unittest -q test_p15_r6_exact_composite
PYTHONPATH=tests/dsd python3 tests/dsd/p15_r6_witness.py --verify tests/dsd/results/P15_R6_EXACT_COMPOSITE_2026-10-19/MASTER64_44100_PASS_0000_1000.json
PYTHONPATH=tests/dsd python3 tests/dsd/p15_r6_witness.py --verify tests/dsd/results/P15_R6_EXACT_COMPOSITE_2026-10-19/MASTER64_44100_STOP_0000_1000.json
PYTHONPATH=tests/dsd python3 tests/dsd/p15_r6_adversarial_replay.py
```

For full mathematical derivation, read `docs/dsd/P15_R6_MATHEMATICAL_PROOF.md`. For scope, read `P15_R6_GATE_ADJUDICATION.md`. For continuation, read `P15_R6_CONTINUATION_CHECKPOINT.md`.
