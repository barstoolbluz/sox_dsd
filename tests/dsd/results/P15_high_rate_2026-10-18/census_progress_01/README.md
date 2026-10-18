# P15 high-rate canonical census

Release remains **BLOCKED**. This census checks all 11,516 historical canonical receipts against the current pinned source/design identity. Historical counts remain 6,835 local passes and 4,681 OPEN.

The matrix reports the original 60-second campaign. Explicit later observations remain separate in `intervals.jsonl` and `cells.json`. A timeout is not a spectral violation.

| Cell | P / S (Hz) | Pass total / OPEN | Stop total / OPEN | Paths / families | SRC stages |
|---|---:|---:|---:|---:|---:|
| dsd128.mastering.pcm384000 | 30000 / 60000 | 30 / 29 | 192 / 191 | 4704 / 4704 | 2 |
| dsd128.mastering_v2.pcm384000 | 48000 / 60000 | 48 / 48 | 192 / 192 | 4704 / 4704 | 2 |
| dsd128.wideband.pcm384000 | 70560 / 88200 | 71 / 71 | 192 / 192 | 4704 / 4704 | 2 |
| dsd256.mastering.pcm192000 | 40000 / 80000 | 40 / 40 | 96 / 96 | 9408 / 9408 | 2 |
| dsd256.mastering.pcm384000 | 40000 / 80000 | 40 / 40 | 192 / 192 | 9408 / 9408 | 2 |
| dsd256.mastering_v2.pcm192000 | 66000 / 80000 | 66 / 66 | 96 / 96 | 9408 / 9408 | 2 |
| dsd256.mastering_v2.pcm384000 | 66000 / 80000 | 66 / 65 | 192 / 192 | 9408 / 9408 | 2 |
| dsd256.wideband.pcm192000 | 91200 / 176400 | 92 / 92 | 96 / 96 | 9408 / 4704 | 2 |
| dsd256.wideband.pcm384000 | 141120 / 176400 | 142 / 141 | 192 / 141 | 4704 / 4704 | 2 |
| dsd64.mastering.pcm384000 | 20000 / 40000 | 20 / 20 | 192 / 192 | 4704 / 4704 | 3 |
| dsd64.mastering_v2.pcm384000 | 25000 / 40000 | 25 / 25 | 192 / 192 | 4704 / 4704 | 3 |
| dsd64.wideband.pcm384000 | 35280 / 44100 | 36 / 36 | 192 / 192 | 4704 / 4704 | 3 |

## What the census establishes

- All 2,151 historical OPEN intervals at 384 kHz were time-budget exhaustions. The old 774 operator-precondition outcomes occur in other cells; they are not evidence that 384 kHz is structurally unsupported.
- DSD256 mastering to 384 kHz is the smallest preferred complete difficult target: 40 passband intervals plus 192 native-source-stop intervals. Its 9,408 paths have no native-family collisions.
- DSD256 wideband to 192 kHz has 9,408 paths for 4,704 primitive families. Its 188 original OPEN outcomes came from the old single-path/count precondition; later code admits complete multiplicities. It is a useful structural-regression target.
- The rate-only transition census gives exact rational event locations for every canonical interval. These are distinct from native-stop-membership crossings at +S and -S modulo the primitive source spacing. Membership crossings can make whole-interval inclusion conservative; a numerical experiment is required before attributing an OPEN to that conservatism.

## Reproduce

From the repository root:

```sh
PYTHONPATH=tests/dsd OPENBLAS_NUM_THREADS=1 python tests/dsd/p15_high_rate_census.py --output NEW_DIRECTORY
```

Add `--measurement baseline=BASELINE_DIRECTORY --measurement candidate=CANDIDATE_DIRECTORY` to overlay new campaign-shaped receipts. Publication is exclusive and idempotent. Use a fresh output directory whenever inputs change.

`corpus.json` selects DC, interior, upper passband, output Nyquist, dense-routing and native-S-coordinate intervals across all nine 384 kHz cells and DSD256 192/44.1 kHz cells. Selection is reproducible and does not change normative acceptance bands.

## Exact topology argument and limits

Start with the output residue group containing only zero, spacing Fout. If a reverse-stage input group has spacing d modulo its output clock, the full M branches of an L/M stage generate the subgroup with spacing gcd(d, Fin) modulo Fin. All branch multiplicities are retained. Branch-window changes occur at L*Fin/2 modulo d; input-frequency wrapping changes at Fin/2 modulo gcd(d, Fin). Their union identifies the open regions on which every inverse-path affine argument remains fixed. Endpoints remain subject to the prover’s independent one-sided checks.

The final spacing is checked against the captured operator’s Fout/U. The complete path population is the product of stage denominators, and its ratio to native_hz/spacing records path multiplicity. The census does not combine transfer amplitudes, infer phase cancellation, or issue a spectral PASS.

The structural work proxy multiplies complete paths by stationary pieces. It is not a runtime estimate: FIR lengths, upper-bound looseness, cache reuse and subdivision can dominate actual work. Current causes remain unclassified until numerical measurements demonstrate them.
