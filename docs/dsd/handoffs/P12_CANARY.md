# P12 canary adjudication and corrected-source handoff (2026-10-11)

## Authority and outcome

Input: `sox_ng-P12canary-a0f9a11a.tar.gz`, SHA-256
`100e25b6afa61b7c46def75c103bff17fb8ab63663fd61920deac969bf19ce14`.
The tree is a `git archive` snapshot with no `.git`. `docs/dsd/sows/P12.md`
and `docs/dsd/DSD_DESIGN.md` are authoritative. Section 10.7 permits at most
5% median slowdown on an unchanged native repack workload **if measured noise
is less than 2%**. The verdict follows the confidence interval.

**Ruling: the original P12 read/repack performance gate genuinely failed on
the recorded, prepared Threadripper 7970X host; the operator did not
misread it. A narrowly scoped source correction is adopted.** The same
alignment-only intervention had already cleared that gate on the qualified
physical host in the retained scratch experiment. This continuation does not
pretend to have repeated the physical-host measurement: this environment
provides a virtualized AMD EPYC host, not the qualified Threadripper.

## Independent examination of retained raw evidence

The original unmodified JSON is retained in the source tree. Examination of
`P12_throughput_prepared_host_2026-10-11/bench-read.json` found:

- `dff-6ch-repack-small`: P11-closed median 0.021680 s, original P12 median
  0.022908 s; regression **+5.6619%**, 95% interval **[+5.4815%, +5.9095%]**;
  measured noise **0.4142%**; output SHA-256 hashes identical.
- All other 15 workloads: `pass`. The reversal JSON corroborates the
  absolute medians and reports **-5.4789%** in the other direction.
- `P12_perf_diagnosis_2026-10-11/bench-read-aligned-loop.json`:
  the scratch P12 aligned-loop binary against P11-closed reports **+0.2258%**,
  95% interval **[+0.0299%, +0.4336%]**, noise **0.4613%**, hashes identical.
  All **16** workloads pass; the unmodified raw JSON preserves the detailed
  CPU timings and output hashes.

The perf-counter values in the original diagnosis README are an operator
record, not raw counter files that this round independently replayed. The
correlation between decoded-uop-cache misses and extra front-end cycles, and
the aligned-loop intervention, support a placement-sensitive front end on the
measured Zen 4 part. They do **not** prove the precise cache-set conflict or
predict outcomes for other x86 microarchitectures.

## Production change and proportionality

Only `src/effects.c` changes production behavior at compile/link time.
`sox_flow_effects` now has the same `__attribute__((aligned(4096)))` guard
already established for `dff_read` and `dff_read_fragment`: GCC or Clang on
x86-64 only. The non-x86 and other-compiler definition leaves the function
unchanged. No hot-loop arithmetic, read/write routine, coefficient, profile,
ISA implementation, dispatcher setting, CLI, ABI or fallback is changed.

Independent builds with `-O2 -g` placed `sox_flow_effects` at `0x39e30` in
original P12 and `0x3b000` in corrected P12, a 4 KiB alignment in the final
x86-64 executable. The linked text grew by exactly **4,096 bytes**, while
linked data and BSS sizes were unchanged. A single page of additional code
footprint is an acceptable bounded cost for a demonstrated real-world 5%
regression gate. This correction is **not** a general policy to align other
functions, nor an invitation to redesign the effects loop.

`docs/dsd/OPTIMIZATION_BACKLOG.md` contains a dated disposition addendum.
The prior evidence files, original P12 handoff and historical source manifests
remain byte-for-byte as received; previous measured failures are not erased.

## Commands actually executed and results

Environment: Linux x86-64, GCC, virtualized AMD EPYC 9V74 with 5 vCPUs.
The original and corrected build copies were distinct and used matching flags.

- Both builds: `autoreconf -fi`: **exit 0**.
- Both builds: `./configure --disable-shared --without-libltdl CFLAGS='-O2 -g'`:
  **exit 0**.
- Both builds: `make -j2`: **exit 0**. The corrected build's first command
  was interrupted by the execution-tool timeout while linking; rerunning
  `make -j2` to completion exited 0. The interrupted attempt is not a pass.
- Corrected build: `make -j2 check`: **exit 0** (generic regression suite).
- Corrected build: `make check-dsd DSD_PHASE=P12
  DSD_RESULTS=tests/dsd/results/P12_canary_fix_complete`: **exit 0**.
  This completed the existing P00-P12 DSD gates, including the P12 SIMD
  kernel unit tests, **2,512** protected-page FIR comparisons, **32**
  multichannel forced-tier runs, **9/9** cross-ISA comparisons, and assembly
  ISA isolation checks. An earlier foreground attempt timed out; the complete
  rerun, not that partial output, supports this result.
- Paired original-P12 vs corrected-P12 native repack on pinned VM CPU 0:
  `bench_read_p02.py`, **40** randomized pairs, **3** warmups per arm, input
  sizes 1,048,576 and 2,097,152 frames, 8 workloads, repack only:
  **688 commands, zero subprocess errors and identical output hashes**.
  The harness process exited **0**, but its JSON status was **`incomplete`**
  because the VM's measurement noise exceeded 2% for 7 of 8 workloads.
  On `dff-6ch-repack-small`, the corrected binary was nominally **5.86%**
  faster, but noise was **3.72%**: **not** a qualified gate pass. The
  path-independent numerical summary is preserved in
  `tests/dsd/results/P12_canary_fix_2026-10-11/local-benchmark-summary.json`.

**Open verification limitation:** A new prepared physical-Threadripper replay
of the exact delivered source against P11-closed was not possible here.
The retained physical scratch experiment directly tests the same one-function
alignment remedy, and the fresh source and functional build tests corroborate
that implementation. The physical-host gate is supported by existing
measurement, not misrepresented as newly executed on these delivered bytes.

## Delivery contract

Deliver the complete source-only continuation, no `.git`, binaries, generated
build files, machine-specific paths in new results, or copy of the dispatch
brief. Preserve all earlier-phase raw evidence unchanged. The historical P12
source inventory predates the P12 canary's later updated backlog and evidence
and is intentionally left as historical evidence, not rewritten; see the new
source inventory for the delivered bytes.

This is a localized P12 canary correction; the P12 kernel and dispatch
qualification already completed in the original handoff is not reopened.
P13 remains the next permitted phase, subject to any required release-host
replay by the operator.
