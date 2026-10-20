# SoX-NG P15 R9 — final clean-room QA

Date: 2026-10-19.

## Inputs and identities

- Original immutable source archive: `sox_ng-P15-adjudicate-cc399928.tar.gz`.
- Original SHA-256: `d058b3908817e01e937f49e0dfeee7194d847aae74f625043e881d8b8f0e9210`.
- Original archive members: **49,323** file entries.
- Cumulative R6+R7+R8+R9 proof addon: entirely additive. Pre-install filename comparison found **0 file collisions** with the original source.
- No production DSP source file was modified or packaged as an override.

## Independent reproducibility checks

1. Extracted the original cc399928 archive into a NEW clean directory, then applied only the cumulative proof addon.
2. Verified **145/145 addon SHA-256 records** from the distributed `docs/dsd/P15_R9_ADDON_SHA256SUMS.txt` (prior to adding this QA document).
3. Executed both new R9 adversarial test modules from that fresh extraction: **21 tests, 21 PASS**.
4. Replayed all three additional exact whole-SRC-stage envelopes separately from the clean extraction: **99, 165, and 66 proof leaves PASS**. This reconstructs the FIR bounds, checking exact source coefficients, complete continuous frequency coverage, and every acceptance inequality.
5. Executed `p15_r9_src_strong.py --prove-all` from the clean extraction. This independently repeated all **179 native-domain leaves** and all **330 strengthened SRC-stage leaves**, as well as source/operator bindings and original stage-majorant proofs for all eight output rates.
6. The clean-room replay returned `native_status=PASS`, `total_source_stop_jobs_proven=958`, `cells=8` and three independently verified stage proofs. Its output was **byte-for-byte identical** to the accepted production-tree replay:

   `4d73a7edbc304bb154ac5fb66cf739e777e0cc5a37a95b49472d6cdd23c6d003` (SHA-256).

7. R7 qualification inventory was checked for duplicate accounting: exactly 87 R7 certificate files across two complete source/rate cells. Of their 46 source-stop jobs, 23 (v2 DSD256 at 44.1 kHz) overlap the R9 family. R8 adds one non-overlapping v2 DSD256 / 384 kHz passband interval. Thus **1023 unique** previously or newly independently checked canonical intervals, not 1046.

## Reproduction commands

From the directory containing the two source/addon tarballs:

```
sha256sum sox_ng-P15-adjudicate-cc399928.tar.gz
mkdir -p verify_r9
# Source archive and proof addon are additive, both rooted in sox_ng/.
tar -xzf sox_ng-P15-adjudicate-cc399928.tar.gz -C verify_r9
tar -xzf P15_R9_CC399928_CUMULATIVE_EXACT_PROOF_ADDON_2026-10-19.tar.gz -C verify_r9
(cd verify_r9 && sha256sum -c sox_ng/docs/dsd/P15_R9_ADDON_SHA256SUMS.txt)
cd verify_r9/sox_ng
PYTHONPATH=tests/dsd python3 -m unittest -q test_p15_r9_uniform_math test_p15_r9_strong
PYTHONPATH=tests/dsd python3 tests/dsd/p15_r9_src_strong.py \
  --prove-all \
  --witness-dir tests/dsd/results/P15_R9_STRONG_SRC_2026-10-19 \
  --native-certificate tests/dsd/results/P15_R9_UNIFORM_STOP_2026-10-19/uniform_native_stop.json \
  --out /tmp/r9-source-stop-independent-replay.json
sha256sum /tmp/r9-source-stop-independent-replay.json
```

Compare the final replay SHA-256 to the value above; any method/source identity changes require intentional mathematical recertification, never automatic inheritance.

## Disposition and limitations

**PASS: exactly 958 canonical source-stop jobs of all eight DSD256 mastering-v2 SRC-active cells**, source-bound and independently repeatable, original limit `1e-8` unchanged.

**CONDITIONAL: global ideal-operator P15 mathematics.** Other native profiles and most passband jobs have not been independently proven by this R9 family theorem. The separate arbitrary-input FFT4G / final ELF execution obligations remain CONDITIONAL; overall P15 release gate OPEN.

This is not a release authorization. The milestone is a verified, reusable mathematical compression of hundreds of independent source-stop obligations into a small number of continuous-domain lemmas and bounded witness sets.
