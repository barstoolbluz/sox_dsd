# P15 R7 — durable checkpoint / continuation

**Date:** 2026-10-19. **Production source:** cc399928, original SHA-256 `d058b3908817e01e937f49e0dfeee7194d847aae74f625043e881d8b8f0e9210`.

## Accomplished; do not redo

1. Source-verified original R6 proof overlay preserved unchanged. New exact-integer/ball R7 mathematical kernel, production-composite subclass, bounded receipt producer, fleet driver, adversarial tests, and evidence sealer are implemented and packaged.
2. 40/40 Python tests PASS. Six of six intentionally corrupted *real* R7 certificates refused.
3. **87/87 current-source-bound R7 certificates independently replayed and sealed**. Two canonical cell sets CLOSED: `dsd64.mastering.pcm44100` (43/43) and `dsd256.mastering_v2.pcm44100` (44/44). All output-certificate hashes, source identifiers, stage snapshots, exact method module SHA-256 values, individual reported bounds, and source archive verification in `P15_R7_CC399928_REPLAYED_EVIDENCE.json`.
4. The 11,516 historical original certificates remain byte-for-byte unchanged. Production `src/rate.c`, `src/fft4g.c`, native FIR kernels and other audio DSP files remain unchanged. No numerical tolerance was changed.

## Global unfinished gate

**11,429 canonical spectral jobs remain to receive independently justified mathematical checks** (not falsely considered failures). R7 can resume via `p15_r7_campaign.py`, selecting exact canonical cell/mode/index ranges, retaining `*.open.json` atomic checkpoints. `*.r7.json` is a published PASS only after independent verifier replay. If bound source or mathematical method hashes change, previous `*.r7.json` become REFUSED and must be requalified, using old geometry as hints via `p15_r7_regenerate_hints.py`; do not edit or re-sign historical bounds.

A bounded `dsd256.mastering_v2.pcm384000` `[0,1000]` current-method attempt remains OPEN. Rational-FIR/high-alias expensive leaf work is the bottleneck; improve exact mathematical work/branch-and-bound *without* changing source DSP or using sampled tests as acceptance. A valid, bounded global majorant or structurally tighter stage cap should be proved before optimization, and unsafe shortcuts disabled.

## Continue immediately

```bash
# In the exact original cc399928 source with the combined R6+R7 overlay:
PYTHONPATH=tests/dsd python3 -m unittest -q \
  test_p15_r7_fast_fir test_p15_r7_fast_math test_p15_r6_exact_composite
PYTHONPATH=tests/dsd python3 tests/dsd/p15_r7_campaign.py \
  --cell dsd256.mastering_v2.pcm384000 --mode pass --start 0 --max-jobs 1 \
  --run-seconds 60 --job-seconds 55 --leaf-seconds 5 \
  --output tests/dsd/results/P15_R7_REQUALIFIED_2026-10-19
PYTHONPATH=tests/dsd python3 tests/dsd/p15_r7_seal_evidence.py \
  --proofs tests/dsd/results/P15_R7_REQUALIFIED_2026-10-19 \
  --workers 4 --out /tmp/P15_R7_EVIDENCE_REPLAY.json
```

**P15 seven gates:** spectral inventory PASS; independent ideal-operator spectral mathematics CONDITIONAL; source/execution provenance CONDITIONAL; arbitrary-input FFT4G roundoff CONDITIONAL; end-to-end same-operator numerical acceptance CONDITIONAL; DSD256 physical 2x release gate CONDITIONAL (historical measured threshold PASS); overall P15 OPEN.

## Distribution and no-clobber installation

The combined R6+R7 addon is **new files only** against the verified original cc399928 archive, with a SHA256SUMS manifest and versioned mathematical source filenames. Verify original archive SHA-256 before extracting. The separate proof-source distribution includes all minimum test dependencies, source-bound operator capture and historical spectral receipt inventory but is not the 368 MB complete SoX-NG production repository. Verify manifests and rerun tests after extracting.
