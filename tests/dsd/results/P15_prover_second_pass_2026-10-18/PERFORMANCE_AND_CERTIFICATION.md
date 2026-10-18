# Second-pass P15 numerical performance and actual local certification

Measured on 2026-10-18, using the delivered source and first-pass code preserved as exact historical copies. This report concerns **only the ideal captured-coefficient local continuum spectral prover**; P15 remains BLOCKED.

## Same-host paired end-to-end result

| Parameter | First-pass prover | Second-pass prover |
| --- | --- | --- |
| Source profile, conversion | DSD128 mastering -> 384k PCM | Same |
| Continuous output-frequency band | 0-1000 Hz | Same |
| Per-interval wall-clock budget | 40 s | 40 s |
| Numerical result | `PASS-LOCAL-BAND` | `PASS-LOCAL-BAND` |
| Actual measured runtime | 36.369 s | 25.158 s |
| Number of FIR interval evaluations | 835 | 835 |
| Actual speedup | - | 1.446x |

The runs are separate fresh Python processes, with identical benchmark code, the same source/operator identity and `OPENBLAS_NUM_THREADS=1`. The measured times are not deterministic runtime guarantees and are not cross-machine predictions. Both variants certified the actual continuous interval with identical normative limits. The raw result files contain source hash, module hash, per-job budget and process memory high-water.

## Warm exact FIR evaluation benchmarks

| FIR taps | First pass, median | Second pass, median | Speedup |
| ---: | ---: | ---: | ---: |
| 57 | 1.039 ms | 0.657 ms | 1.58x |
| 153 | 3.772 ms | 2.506 ms | 1.51x |
| 720 | 17.536 ms | 10.138 ms | 1.73x |
| 1,005 | 23.506 ms | 15.572 ms | 1.51x |
| 1,845 | 44.403 ms | 26.840 ms | 1.65x |
| 4,160 | 100.403 ms | 64.421 ms | 1.56x |

Three warm repetitions per exact source stage and per process; medians shown. Both engines compute outward rigorous enclosures, not approximate FFTs. These are arithmetic-only measurements and cannot be equated to production DSP runtime.

## Removal of structural proof refusal

| Profile and conversion | Primitive families | Complete reverse paths | First-pass status | Second-pass local band |
| --- | ---: | ---: | --- | --- |
| DSD64 mastering -> 48k PCM | 4,704 | 9,408 | `OPEN`, structural (0.795 s) | 0-1 Hz `PASS-LOCAL-BAND`, 19.452 s |
| DSD128 mastering -> 96k PCM | 4,704 | 9,408 | Same inherited proof restriction | 0-1 Hz `PASS-LOCAL-BAND`, 18.687 s |
| DSD256 mastering -> 96k PCM | 9,408 | 18,816 | Same inherited proof restriction | 0-1 Hz `PASS-LOCAL-BAND`, 19.244 s |

All three local results have separate source-bound, pinned-operator-hash, stage-snapshot-hash, normative-design-hash receipts in `new_certificates/`, with no mutation to the historical campaign. All include every stage path and impose the original strict ripple and alias limits. The DSD256 case was OPEN when first interrupted at 3 seconds and PASS in a separate 20-second-budget replay: the OPEN is not evidence of a mathematical failure.

The final DSD256 local receipt reports min desired transfer > 0.9999999903, max combined transfer < 1.0000000103, and coherent-alias upper < 9.975e-9. These are outward scalar presentations of interval comparison endpoints and do NOT justify extrapolation to all 40 kHz of its governing passband.

## Regression, provenance and remaining work

65 unit tests executed (62 passed; 3 expected skips), including independent complex interval references, exact rational lattice enumeration, cancellation and Nyquist cases, source/operator checks, complete alias populations, and signal re-delivery. An independent archive comparison reverified **16,711** original pinned source and historical evidence files byte-for-byte. The existing first-pass result for DSD128 mastering -> 384k also reproduced at 34.601 seconds with a 60-second cap; the 40-second matched pair above is the primary speedup evidence.

Not performed: full second-pass 11,516-interval campaign; independent arbitrary-input FFT4G execution-roundoff proof; closure of the DSD256 physical P/S comparator; final release adjudication. The old 11,516-interval historical campaign remains 6,835 local PASS and 4,681 OPEN. No newly certified 0-1 Hz interval is relabeled as complete band. Strict budgets may need external process supervision because Python SIGALRM cannot kill a native call that does not return to Python.

See `RESULTS_SUMMARY.json` for machine-readable measurements and certificate SHA-256 identifiers; `benchmarks/*.json` for all actual outcomes, including interrupted OPEN observations; `MATHEMATICAL_METHODS.md` for rigorous enclosure arguments.
