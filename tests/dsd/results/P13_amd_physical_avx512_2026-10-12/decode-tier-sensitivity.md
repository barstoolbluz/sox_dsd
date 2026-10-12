# Follow-up: decode is nearly insensitive to the FIR kernel tier

Prompted by a reviewer asking why decode landed at 0.996-1.002x across all six
configurations when `fir-block` measures 1.93x faster under AVX-512F. A 0.6%
spread centred on 1.000 is what you would see if the tier were not exercised at
all, so it was worth checking rather than explaining away.

## The tier is genuinely forced

`tests/dsd/bench_p11_e2e.py:104-105` sets `SOX_DSD_KERNEL_FIR` to the tier for
decode families and to a deliberately invalid name for encode families, and
vice versa for `SOX_DSD_KERNEL_SDM`. Independently, a `--dsd-report` run with
`SOX_DSD_KERNEL_FIR=avx512` records `fir_kernel_actual: avx512`. Forcing works.

## Decode wall time barely moves across the whole tier matrix

Same source, 7 runs each, pinned to CPU 8, warm:

| forced FIR tier | median | vs scalar |
|---|---|---|
| scalar | 0.7070s | 1.000x |
| sse2 | 0.7028s | 1.006x |
| avx1 | 0.7031s | 1.005x |
| avx2 | 0.7084s | 0.998x |
| avx512 | 0.7142s | 0.990x |

The entire five-tier span is 1.6%, and AVX-512F is the slowest of the five.

## Why: the FIR is a small part of decode

| component | time | share |
|---|---|---|
| read only, `-t null`, I/O and container | 0.0268s | 3.8% |
| everything above I/O | 0.6755s | 96.2% |
| scalar-vs-default FIR delta | 0.0047s | 0.7% of the non-I/O work |

Decode wall time is dominated by work outside the ISA-dispatched kernels,
chiefly the multistage rate conversion, which is generic PCM code and carries no
tier. We did not profile to attribute the remainder precisely and do not claim
a full breakdown; the bound above is what the measurements support.

## What this corrects, and what survives

The parent README said the block-FIR win "does not reach the conversion graph"
and presented the decode column as evidence about break-even. That was true but
weaker than stated. **The decode column is not a measurement of AVX-512F
efficacy.** It is a measurement of how little the FIR tier matters to decode,
and it would read about the same for any tier pair.

The conclusion is unchanged and the reasoning is now firmer:

- **Decode: nothing to gain.** No FIR tier, scalar through AVX-512F, moves
  decode by more than about 1%.
- **Encode: a real loss.** SDM dominates encode, AVX-512F SDM is 8% slower in
  the kernel benchmark, and encode measures 2.4% to 5.7% slower across all six
  configurations with tiny dispersion.

So promoting AVX-512F would gain nothing on decode and cost a few percent on
encode. Separately worth recording: the 1.93x `fir-block` kernel speedup is real
but measures a kernel that is not load-bearing in the actual conversion graph,
which bears on how much any vector FIR work is worth pursuing.

It also follows that the default SSE2 FIR choice is worth only about 0.6% over
scalar on this path. That is an observation about this host and this stimulus,
not a recommendation to change a default.
