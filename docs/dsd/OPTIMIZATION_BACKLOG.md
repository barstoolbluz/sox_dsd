# Optimization backlog

Work deliberately deferred rather than forgotten. Nothing here blocks a phase
gate; each item is something a later phase, or a dedicated optimization pass,
should pick up with the evidence already gathered.

## `dff-6ch-repack-small`: the DSD path most sensitive to code changes

Six-channel DFF repack with `--buffer 32`. It has been the worst workload in
every throughput gate since P06 and has required two hotfixes. Worth revisiting
as a deliberate optimization target rather than one regression at a time.

### Measured history

Every figure from the committed evidence under `tests/dsd/results/`, prepared
host, interval from a paired bootstrap.

| Boundary | Regression | 95% CI | Noise | Outcome |
| --- | --- | --- | --- | --- |
| P01 to P02 | +136% | — | 0.92% | not comparable: P02 repaired a short read, so the arms do different work |
| P02 to P03 | -0.64% | [-0.85%, -0.00%] | 0.67% | pass |
| P03 to P04 | -0.38% | [-0.71%, +0.82%] | 0.95% | pass |
| P04 to P05 | +0.17% | [-0.36%, +0.51%] | 0.77% | pass |
| P05 to P06 | **+5.65%** | [+5.50%, +5.89%] | 0.43% | **fail**, hotfixed |
| P05 to P06+hotfix | -2.39% | [-2.70%, -2.03%] | 0.70% | pass |
| P06+hotfix to P07 | +3.06% | [+2.79%, +3.54%] | 0.63% | pass |
| P07 to P08 | +2.59% | [+2.39%, +2.90%] | 0.50% | pass |
| P08 to P09 | -3.69% | [-3.90%, -3.51%] | 0.50% | pass, unexplained speedup |
| P09 to P10 | +1.02% | [+0.82%, +1.43%] | 0.50% | pass |
| P10 to P10 corrective | -0.15% | [-0.34%, +0.06%] | 0.34% | pass |

Cumulative, as the product of the recorded median ratios: **+3.20%** from P05
through P08, then **-0.60%** once P09 is included, **+0.42%** through P10 and
**+0.26%** through the P10 corrective round. Each phase passed its own 5%
gate. The design gates per phase and not the accumulation, so this total is
tracked here rather than by any gate.

The P09 leg is worth treating with suspicion rather than relief. P09 changes
only `src/sdm.c` and `src/sdm.h`, touching no read path, yet this workload
became 3.69% faster with a tight interval at 0.50% noise. That is the same
unattributed behavior P06 showed in the other direction, and it means the
running total is partly tracking something other than deliberate work. An
optimization pass should establish why this workload moves when unrelated
object files change before trusting any cumulative figure, including this one.

### What the two hotfixes found

Both were write-pattern problems in the same place, not algorithmic cost, which
is the reason to treat this path as a target rather than a recurring accident.

The P02 hotfix split an aligned eight-frame fast path, which needs no retained
state, from a `dff_read_fragment` that keeps state only for partial clusters.
P02's streaming rewrite had put per-cluster bookkeeping in the hot loop for
every read; the split restored P01's throughput on the aligned path while
keeping the small-capacity repairs. See
`docs/dsd/handoffs/P02_DFF_READ_HOTFIX.md`.

The P06 hotfix then specialized six-channel sub-byte reads inside that fragment
path to write interleaved destination frames in address order rather than
striding `buf[i + j * nc]` per channel. Strided writes across six channels
defeat the write combiner at `--buffer 32`. Bit selection was unchanged, so the
output stayed byte-identical. See `docs/dsd/handoffs/P06_READ_HOTFIX.md`.

### Why it keeps surfacing here

`--buffer 32` with six channels means five complete frames per call, so almost
every read lands in the partial-cluster path and the per-call overhead is
amortised over very little work. That makes this the most sensitive workload in
the matrix to anything added near the read loop, and the first place a cost
shows up. It is a useful canary for that reason, and a poor one to leave
un-optimized.

### What has not been done

No profiling. Both hotfixes were reasoned from the diff and confirmed by
measurement, and the speedups P06 showed elsewhere on untouched paths, 11.16%
on `dff-6ch-null-large` and 5.69% on `dff-6ch-repack-large`, were never
attributed either; linker layout or instruction-cache effects are the plausible
explanation but nobody has looked. A `perf` profile of this workload against
P01 would likely settle both the residual cost and those speedups, and would
tell a later optimization pass where the movement actually sits, in either
direction.

### How to measure it

```sh
sudo tests/dsd/benchprep.sh prepare --cpu 8
tests/dsd/benchprep.sh noise --cpu 8
python3 tests/dsd/bench_read_p02.py \
  --baseline-sox <older build>/src/sox_ng --sox <newer build>/src/sox_ng \
  --results <dir> --pairs 40 --warmups 3 --cpu 8 \
  --small-frames 1048576 --large-frames 2097152
sudo tests/dsd/benchprep.sh restore
```

Forty pairs with larger fixtures matter: this workload read +3.28% at fifteen
pairs with default fixtures and +5.65% at forty with larger ones, because short
runs dilute a per-sample cost. See `tests/dsd/BENCHMARKING.md`.

## `src/dsdiff.c` indentation

99 code lines use spaces where the file indents with tabs: 68 at four-space in
`dff_read` and `dff_read_fragment`, 21 at two-space in `dff_seek`, and ten
scattered. It grows whenever the DFF read path is touched, having been 89 lines
before the P06 hotfix. Offered as surplus to P06, P07 and P08 and declined each
time, which is reasonable; it is cosmetic. Note that some of those lines are
continuation alignment the file keeps in spaces deliberately, including the
top-level signature continuations in `dff_write_bits` and `dff_read_fragment`,
so a blind sweep would make the file worse rather than better.
