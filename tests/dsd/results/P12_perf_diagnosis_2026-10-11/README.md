# P12 canary diagnosed: decoded-uop cache, and a candidate fix (2026-10-11)

**The cause is Zen 4's decoded-uop cache, not instruction memory, not data, and
not image layout in general.** Confirmed by hardware counters and then by
intervention. This replaces three earlier hypotheses of ours, all wrong.

Measured with `perf` 6.12.111 on the exact failing workload,
`sox_ng --buffer 32 dff-6-small.dff out.dff`, pinned to CPU 8, five repetitions.

## The counters

| Event | P11-closed | P12 | Change |
| --- | --- | --- | --- |
| instructions | 393,279,665 | 393,254,737 | -0.006% |
| cycles | 82,898,851 | 87,458,074 | **+5.50%** |
| IPC | 4.74 | 4.50 | -5.1% |
| branch-misses | 117,820 | 117,270 | none |
| cache-misses | 53,412 | 53,710 | none |
| L1-icache-load-misses | 5,599 | 5,368 | none |
| iTLB-load-misses | 2,960 | 2,950 | none |
| **op_cache_miss** | 1,296,842 | 4,403,301 | **+240%** |
| op_cache_hit | 55,646,219 | 52,592,751 | -3.05M |
| **stalled-cycles-frontend** | 4,535,071 | 7,259,198 | **+60%** |

Identical instruction count, identical branch and data-cache behaviour, and
identical L1 instruction cache and ITLB behaviour. About 3.1 million fetches
moved out of the decoded-uop cache into legacy decode, and front-end stalls rose
by 2.7 million cycles against a 4.6 million cycle regression. The work did not
change; its instruction delivery did.

## What moved

`sox_flow_effects` in `src/effects.c`, the per-buffer processing loop, runs on
every one of the millions of 32-sample buffers this workload uses. It sits at
0x39d30 in the P11-closed build and 0x39df0 in P12, a shift of 192 bytes.

That also explains why our earlier layout experiment found nothing. Dead padding
placed after the aligned reader reproduced the section signature exactly but left
`sox_flow_effects` at 0x39d30, and unexecuted code never occupies uop-cache
entries. We had perturbed address space without perturbing the hot path.

## Intervention confirms it

Giving `sox_flow_effects` 4096-byte alignment in the P12 tree, so its low address
bits no longer depend on upstream object sizes:

| Build | `sox_flow_effects` | op_cache_miss | elapsed |
| --- | --- | --- | --- |
| P11-closed | 0x39d30 | 1,280,852 | 0.021446 s |
| P12 | 0x39df0 | 4,699,471 | 0.023223 s |
| P12 + aligned loop | 0x3b000 | 1,505,167 | 0.021555 s |

And on the project's own gate, P11-closed against P12 with the aligned loop:

| Workload | P12 | P12 + aligned loop |
| --- | --- | --- |
| `dff-6ch-repack-small` | **+5.66%, fail** | **+0.23%** [+0.03%, +0.43%], pass |
| `dsf-6ch-repack-small` | +0.15% | +0.42% |
| `dff-6ch-repack-large` | -0.01% | +0.07% |

All sixteen workloads pass, worst noise 1.22%. One alignment attribute on one
function recovers the entire regression.

## Standing and limits

This is a diagnosis and a demonstrated remedy, not a delivered fix. The change
lives in a scratch build; it is not in the tree, and whether to adopt it, and in
what form, belongs to a round that owns the code. The P10 hotfix already uses
this attribute on `dff_read` and `dff_read_fragment`, so the pattern and its
guard are established, but a second instance invites the question of how many
hot functions want pinning and whether that is the right structural answer.

Measured on one AMD Ryzen Threadripper 7970X, Zen 4. The op cache is a
microarchitectural feature; the magnitude will differ elsewhere, and the
counters named here are AMD-specific. The effect is a property of this part as
much as of the code.

Counters required `kernel.perf_event_paranoid` lowered from 3 to 1, done by the
operator.
