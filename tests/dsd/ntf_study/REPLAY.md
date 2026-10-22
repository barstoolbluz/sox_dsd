# DSD512 NTF study: deterministic replay

Run only in a *separate, disposable* source checkout. The complete archive already contains the unchanged P20 source and all numeric receipts. It does not ship 1-bit packed outputs or generated test stimuli (regenerate them; their SHA-256 digests are in the receipts). The study's `instrument_candidates.py` **changes only the disposable checkout** and does not install any production profile.

Requires Linux x86_64 and SoX build dependencies (`autoreconf`, compiler, libtool/configure, `make`) plus Python3 NumPy and SciPy. All actual measurements below were made with `LSX_DSD_SDM_KERNEL=scalar`. Use the same compiler flags and environment for byte-for-byte bitstream comparison; floating-point builds on other toolchains may not reproduce all bit hashes.

From the extracted `sox_dsd` directory:

```sh
sha256sum -c --quiet P20_BUNDLE_SHA256SUMS.txt
sha256sum -c --quiet P20_RESIDUAL_ASYMMETRY_SHA256SUMS.txt
sha256sum -c --quiet tests/dsd/ntf_study/NTF_STUDY_SHA256SUMS.txt
python3 -m unittest discover -s tests/dsd/ntf_study -p test_ntf_study.py -v
```

To render in a private scratch tree (change `/tmp/ntf512` to any fresh directory):

```sh
STUDY="$PWD/tests/dsd/ntf_study"
mkdir -p /tmp/ntf512
cp -a "$PWD" /tmp/ntf512/native
cd /tmp/ntf512/native
autoreconf -fi && ./configure --disable-shared && make -j4 && make -C test dsd_test_p10
python3 "$STUDY/instrument_candidates.py" \
  --source "$PWD" --designs "$STUDY/designs-sweep.json" \
  --registry /tmp/ntf512/registry.json
make -j4 && make -C test dsd_test_p10
```

Generate the exact primary binary64 stimulus using the frozen original P10 stimulus definition:

```sh
cd /tmp/ntf512/native
python3 - <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, 'tests/dsd')
from diagnose_residual_asymmetry import reference_source
_, _, _, exact = reference_source()
Path('/tmp/ntf512/tone-997-prequantization.f64le').write_bytes(exact)
PY
python3 "$STUDY/render_experiments.py" \
  --checkout "$PWD" --registry /tmp/ntf512/registry.json \
  --stimulus /tmp/ntf512/tone-997-prequantization.f64le \
  --directory /tmp/ntf512/rendered \
  --only P20-CLANS7-baseline order7-pareto-g3p0
python3 "$STUDY/analyze_renders.py" \
  --input-dir /tmp/ntf512/rendered --output-dir /tmp/ntf512/spectra \
  --source-root "$PWD"
```

The baseline digest must equal the frozen F64 baseline digest in `evidence/renders/P20-CLANS7-baseline.receipt.json`; the g x3 digest must equal its receipt. The primary spectral result for g x3 is approximately -200.93 / -162.20 / -127.80 dBFS on 0–40 / 40–100 / 100–150 kHz; expect very small processor/library differences in sub-noise-floor digits. To reproduce all eight optimized designs, create a second disposable checkout and instrument it using `designs.json` instead of `designs-sweep.json`.

To regenerate additional stimuli, run `python3 "$STUDY/generate_holdouts.py"` and `python3 "$STUDY/generate_stress.py"` from any working directory. Generated inputs go into `tests/dsd/ntf_study/replay-holdouts/` and should match the source hashes in `evidence/holdouts/`. Reuse `render_experiments.py --stimulus ... --directory <unique-output-dir> --only <candidate-names>` to run the same real P10 renderer. Do not overwrite differing immutable receipts. The 32-second continuity test has no special runtime dependency; it is an ordinary `--render` call with the single generated stress32 source file. Avoid treating it as P20's full one-hour soak.

**Resume:** inspect `NTF_STUDY_CHECKPOINT_2026-10-22.json` and the linked report. Frozen P20 state snapshots, qualification status, high-rate enablement, and historical omissions are unchanged. A future agent should not rerun the complete coefficient search unless it is deliberately proposing a different NTF objective; the exact candidates already exist in the two JSON files.
