# P10 hotfix read/repack throughput gate, prepared host (2026-10-11)

**Verdict: PASS, and the regression is more than recovered.** All 16 workloads
gate with 0 errors. The workload that failed the previous round,
`dff-6ch-repack-small`, now measures **-4.43%** [-4.63%, -4.24%] at 0.49% noise
against the pre-hotfix baseline, so it is faster than the tree the regression was
introduced into, not merely restored. `dsf-6ch-repack-small` moves -3.44%.

| Workload | Regression | 95% CI | Noise | Status |
| --- | --- | --- | --- | --- |
| `dff-6ch-repack-small` | -4.43% | [-4.63%, -4.24%] | 0.49% | pass |
| `dsf-6ch-repack-small` | -3.44% | [-3.64%, -3.24%] | 0.72% | pass |

Baseline is `e2501084`, the tree carrying the +6.81% regression, against the
hotfix. Both built from their own sources in the same session with `-O2 -g`, 40
randomised AB/BA pairs per workload after 3 discarded warmups, pinned to CPU
8, tmpfs, host prepared with a 0.0% noise probe beforehand. Worst noise across
the matrix was 0.91%.

## The fix

Two changes. `src/pcmdsd.c` drops the 192-byte buffer and the `snprintf`/`strcpy`
pair, formatting each branch directly in its own `lsx_fail` call, so the improved
lower-bound wording survives with no buffer or formatting work added to the
object. `src/dsdiff.c` gives `dff_read` and `dff_read_fragment` 4096-byte
function alignment behind a GCC/Clang x86-64 guard, which is a non-ABI hint and
changes no read, bit or sample operation.

Alignment is present in the linked image: `dff_read_fragment` at 0x6f000 and
`dff_read` at 0x70000, both page-aligned.

## Residual layout sensitivity, measured

The stated rationale is that page alignment pins the L1-I cache set mapping
independently of preceding object sizes. We tested that by growing an unrelated
object: 40 used, non-inlined functions added to `src/pcmdsd.c`, which is the same
translation unit whose growth displaced this code before, with no other change.

Both functions moved by exactly one page, to 0x70000 and 0x71000, and **both
stayed page-aligned**. Since the L1-I set index is taken from address bits below
4096, whole-page displacement preserves set mapping, so the structural claim
holds as stated.

Throughput, however, is not independent of layout. The perturbed build measures
-2.70% [-2.93%, -2.50%] at 0.43% noise on `dff-6ch-repack-small` against the
delivered hotfix, with identical source for every read path.
`dsf-6ch-repack-small` moves +0.07%. So an unrelated object's size still shifts
this workload, by 2.70% here rather than the 6.81% seen before alignment: a
reduction of roughly 2.5 times, not elimination. The movement happened to be
favourable in this instance, which is not something to rely on.

The honest reading is that alignment substantially reduces the sensitivity this
file has documented for five phases and is enough to recover the gate, but the
underlying fragility is still there and a future unrelated change can still move
this workload by a few percent in either direction. See
`docs/dsd/OPTIMIZATION_BACKLOG.md`.

Figures are from one AMD Ryzen Threadripper 7970X and are not a property of the
code alone.
