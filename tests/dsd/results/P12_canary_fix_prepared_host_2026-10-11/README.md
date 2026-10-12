# P12 canary fix verified on the qualified host (2026-10-11)

**Verdict: PASS. The gate is recovered.** `dff-6ch-repack-small` measures
-0.05% [-0.42%, +0.29%] at 0.71% noise against the P11-closed
baseline, where unmodified P12 measured +5.66%. All 16 workloads pass with
0 errors and worst noise 1.06%. Repack output hashes agree between arms.

The adjudicating round could not run this measurement: it had a virtualized AMD
EPYC host, not the prepared Threadripper 7970X on which the regression was
recorded and the alignment experiment performed. It said so rather than
inferring a result, and left the physical-host confirmation to us. This is that
confirmation.

| Workload | unmodified P12 | corrected |
| --- | --- | --- |
| `dff-6ch-repack-small` | +5.66%, fail | -0.05%, pass |
| `dsf-6ch-repack-small` | +0.15% | +0.06% |
| `dff-6ch-repack-large` | -0.01% | +0.04% |

Built from the corrected tree with `-O2 -g`, 40 randomised AB/BA pairs per
workload after 3 discarded warmups, pinned to CPU 8, tmpfs, with a 0.0%
host noise probe beforehand. `sox_flow_effects` links at 0x3b000 here, page
aligned as intended.

## Functional gates on the same tree

`make check` and `make check-dsd` both exit 0, the floor holds at 36 pass / 0
fail, and `check_p12_isa`, `test_p12_channels`, `check_p11_isa`,
`test_p11_integration` and `test_p11_numeric` all pass. The change is a
placement hint behind the same GCC or Clang x86-64 guard already used for
`dff_read` and `dff_read_fragment`; no arithmetic, routine, coefficient,
profile, dispatcher setting, CLI or ABI changes.

## What this does not establish

The measurement is one Zen 4 part. The adjudicating round was explicit that the
correlation between decoded-uop-cache misses and front-end cycles, plus the
alignment intervention, support a placement-sensitive front end on this
microarchitecture without proving the precise cache-set conflict or predicting
other x86 parts. We agree, and our own perf figures are an operator record that
round did not independently replay.

Cost: the linked text grows by one 4 KiB page, with data and BSS unchanged.
