# DSD512 g×3 NTF: qualification blocker and soak-harness handoff

**Date:** 2026-10-22. **Disposition: FAIL candidate P10 admission; NO frozen guard; NO 3,600-second qualification.** The earlier short-window ultrasonic improvements are independently reproducible, but this seventh-order candidate is not robust under the required full-scale DC training cases. Do not promote it, retune guard ceilings, or spend an hour generating a misleading soak receipt.

## What was reproduced

Original `sox_dsd` NTF study source, P20 bundle and study SHA manifests passed. A disposable copy was instrumented with the unmodified `tests/dsd/ntf_study/instrument_candidates.py` using exact binary64 coefficients from `designs-sweep.json`. The private P10 executable builds, and its native `--unit` tests pass **105,489 assertions**.

The isolated new runner executed the frozen P17/P20 **training configurations** through the existing P10 `--render ... training` operation, with `LSX_DSD_SDM_KERNEL=scalar` and **no state guards**. Sixteen case receipts are supplied; the 60-second sustained-training case was not completed within this environment's run budget. No guard row was created because two other required cases already fail:

| Frozen training input | P20 CLANS-7 | Experimental g×3 |
|---|---|---|
| +1.0 source DC (0.5 modulator full scale) | complete, finite, longest run 6 | NONFINITE at native frame 10,129,308; longest run 445; min28=0, max28=28; 2,897,296 excursions |
| −1.0 source DC | complete, finite, longest run 6 | same NONFINITE failure at native frame 10,129,308; same excursions |

The g×3 failure occurs around **0.4486 seconds**, after the source's 100-ms taper reaches its steady full-scale plateau. `failure=3` (modulator state nonfinite), `status=7`, `nonfinite_states=1`. These are not source interpolation overloads. The original P20 CLANS-7 reference passes both frozen training cases in the original archived receipts.

A separate regression used the **original, unmodified P10 test source**, linked against the same experimental SDM instrumented source. It reproduced the exact first failure frame, monitor statistics and failed packed-bitstream SHA-256 `a3711b41d500f0db8d5a89b8d1e6c1207a2fc90438568020867690895440d35a`. The private P10 test-source extension therefore did not cause this failure.

## Adversarial gain and input-amplitude screen

All seven previously studied resonator multipliers **g×1.25, 1.5, 1.75, 2.0, 2.25, 2.5 and 3.0** fail both full-scale DC training inputs. Their first failure frames vary, but each exhibits a severe constant-bit run (445–688 bits) followed by nonfinite state. See `evidence/dc-variants.json` for each exact failure.

At 1.6 seconds of constant positive DC (with the unchanged P10 taper), g×3 completes at input amplitude **0.95**, but fails at **0.98, 0.99 and 1.0**. The P20 CLANS-7 reference completes all tested amplitude levels 0.70–1.00. See `evidence/dc-amplitude.json`. The previously recorded g×3 longest-run value of 9 over the 32-second mixed-signal screen is not a worst-case value; the full-scale test reaches **445**.

The spectrum improvements on previously admitted tones remain real. However, 40–100-kHz noise reduction cannot justify a one-bit modulator that violates the existing numerical-finiteness and 28-bit-population requirements.

## Minimal experimental soak implementation

`g3-soak-test-p10.patch` changes **only the private** `tests/dsd/test_p10.c`, not production encoder files or historic P20 sources. It adds:

- `--render-candidate`: guarded experimental render with **explicit eight bounds**, instead of unintentionally inheriting CLANS-7's bounds.
- `--soak-candidate` and `--soak-candidate-nominal`: select an explicit test-only `encode.experimental.ntf.*.dsd512` SDM profile, accept eight explicit bounds and reuse the original P10 continuous composite, intermediate state snapshots, replay comparison, guard monitor and final result logic. Existing soak flags remain intact.

`qualify_g3.py` is a fail-closed private driver. It uses the original 17-case P10/P17 training split, P10 guard formula `2**ceil(log2(16*max(1, coordinate training maximum)))`, immutable receipts, **independent holdout**, and a candidate-specific frozen guard file:

`tests/dsd/reference/ntf_order7_pareto_g3p0_guard.json` **(intentionally absent)**.

A future *admissible* candidate's runner binds receipts to:

- `profile`: the selected experimental profile ID, not `encode.mastering.v2.dsd512`.
- `candidate_sha256`: `src/ntf_experiment_candidates.h`, not `src/sdm_p20_candidates.h`.
- `frozen_guard_sha256`: the candidate's own training-provenance JSON, never `p20_dsd512_v2_guard.json`.
- `source_sha256`: hashes of the actual `test_p10.c`, instrumented `sdm.c`, coefficient definitions, P10 corpus, split definitions and runner.
- `executable_sha256`, input/bitstream and intermediate/final state snapshot SHA-256, host and ISA information, exit status and mode.

The runner **refuses** any citable soak without a frozen candidate-specific guard. The 3,600-second qualification **was neither attempted nor satisfied**, because freezing one now would contradict the training evidence. The P20 CLANS-7 guard, source and historical certificates were not changed.

The extension passed six private soak-interface tests, including candidate selection, failed-state bound, unrecognized profile, nonfinite bound, nominal smoke with explicit artificial test bounds, and unchanged P20 baseline soak. The original native P10 unit suite still passes **105,489 assertions**. Short smoke with artificial bounds is **not qualification evidence**.

## Reproduce on an independent host

Start with the original `sox_dsd-dsd512-ntf-design-study-2026-10-22.tar.zst` and apply this overlay at its `sox_dsd/` root, preserving unchanged production files. **Use a disposable checkout.** The overlay's failed training receipts are under `tests/dsd/ntf_study/evidence/training`, separate from runtime result paths so a new host does not silently reuse binary-specific evidence.

```sh
cd /path/to/disposable/sox_dsd
autoreconf -fi
./configure --disable-shared
make -j4
make -C test dsd_test_p10
python3 tests/dsd/ntf_study/instrument_candidates.py \
  --source "$PWD" \
  --designs tests/dsd/ntf_study/designs-sweep.json \
  --registry /tmp/ntf-candidate-registry.json
patch -p1 < tests/dsd/ntf_study/g3-soak-test-p10.patch
make -j4
make -C test dsd_test_p10
python3 -m unittest discover -s tests/dsd/ntf_study -p 'test_g3_candidate_soak.py' -v
python3 tests/dsd/ntf_study/qualify_g3.py training --jobs 2 --kernel scalar
```

The `freeze` operation will reject any nonadmitted training case and will **not** create a guard. Do not run the full 3600-second `soak` with this candidate. After a stable successor is designed, adapt the source-bound driver to its exact profile and binary64 coefficient words, rerun the entire training and holdout from scratch, freeze its own guard and only then run nominal and adverse one-instance 3,600-second soaks.

## Next engineering action

**Return to NTF design, not soak plumbing.** Make sustained full-scale positive and negative DC, near-full-scale tones, bit-population and nonlinear state stability part of the candidate-screening constraint **before** optimizing 40–150 kHz residuals. Retain CLANS-7 as the working comparator and current unqualified g×3 as spectral research evidence only. A validated successor must pass the entire unchanged P10/P17 training corpus; do not silently exclude source material or waive numeric failures to produce a guard row.

No code outside an experimental test checkout was modified, and no high-rate production capability was enabled.
