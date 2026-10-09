# P06 DFF small-buffer reader hotfix: isolated handoff

Date: 2026-10-09. This is the **P06-only** correction, completed and tested
before P07 was introduced. Its measurements must not be combined with those
from P07. Input archive SHA-256:
`a0bc9bfd334809617f9719954d9bcc884db91db8540c100609d2bf30da8ef0d4`.

## Scope, source and correctness

- `src/dsdiff.c`: specialize *only* six-channel reads of partially consumed
  eight-bit DFF clusters. Emit the interleaved output frame in destination
  address order, using the existing cached cluster and chronological bit
  offset. The aligned full-cluster path, other channel counts, DFF headers,
  native bit values, and seek semantics are unchanged.
- `tests/dsd/bench_p06_hotfix.py`: paired, alternate-order, 40-pair
  byte-verified microbenchmark. Its control identity is explicit; it must not
  be called a P05 comparison unless a genuine P05 source/binary is supplied.
- Evidence: `tests/dsd/results/P06/hotfix-isolated/runner/run.json` and
  `tests/dsd/results/P06/hotfix-isolated/dff-6ch-repack-small.json`.
  Historical results in `tests/dsd/results/P00/` through `P06/` are retained
  unchanged, except for the requested regenerated P00 manifest.

Built the original supplied P06 tree and the single-file P06 candidate using
identical Autotools configurations (`--disable-shared --without-libltdl`,
`CFLAGS='-O2 -g'`). Before P07 edits, the candidate passed:

| Gate | Result |
| --- | --- |
| Build (`make -j2`) | exit 0 |
| Generic regression (`make check`) | exit 0 |
| DSD regression (`make check-dsd`, phase P06) | exit 0 |
| Isolated `run.py --phase P06` | 36 pass; 0 fail; 0 xfail; exit 0 |
| P06 certified scalar/coefficients | existing P06 tests remain passing |
| Identical native DFF output bytes between A/B arms | true; SHA-256 matches |

## Performance: **not certified**

Historical failure on a prepared host: `dff-6ch-repack-small` with
`--buffer 32` regressed **+5.65%**, 95% CI **[+5.50%, +5.89%]** against
P05 at `149ea582` (historical record provided in the brief). That is a
*failure*, not superseded by a development-host measurement.

The source for P05 commit `149ea582` is absent from the supplied archive;
there is no `.git` directory, and no independent P05 control was available
in this session. We therefore compared **original P06 versus P06 plus only
this hotfix** as a development check, *not* as P05 gate certification.

40 paired runs, three warmups, 1,048,576 frames/channel, six-channel DFF,
`--buffer 32`: candidate median CPU 0.0383505 s; original P06 median
0.043671 s; median ratio 0.87817 (**12.18% faster**). Paired bootstrap 95%
ratio CI [0.80829, 1.02855]. Recorded timing noise was **25.84%**, above
the design's 2% admissibility threshold; thus the result is **inconclusive**
regardless of median. The environment's `benchprep.sh` rejected requested
CPU 8 as nonexistent. These timings do not justify a definitive performance
claim. Run the prescribed 40-pair P05-control comparison on a prepared
low-noise host with a *genuine* `149ea582` control, checking the whole CI
lies below +5% and verifying output byte hashes on every run.

The source-only isolated checkpoint was created before any P07 edits; this
final combined tree is its continuation, not its timing baseline. The next
phase may not reclassify P06 as a passing throughput gate without the
prescribed P05 comparison.

## Replay

Using separately built P06 control and isolated P06-hotfix candidate:

```sh
python3 tests/dsd/bench_p06_hotfix.py \
  --control CONTROL_P06_BINARY \
  --candidate ISOLATED_P06_HOTFIX_BINARY \
  --pairs 40 --warmups 3 --frames 1048576 \
  --out tests/dsd/results/P06/hotfix-isolated/dff-6ch-repack-small.json
```

For *certification*, replace the control with the verified P05 `149ea582`
binary and prove its provenance. Keep the resulting record separate from the
P07 native-path and explicit decode performance records.
