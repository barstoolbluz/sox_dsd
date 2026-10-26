# Register-resident SDM: verification on the operator host

Independent check of the register-resident vector SDM kernels against the
original scalar build at cb0f61b31. Host: AMD Ryzen Threadripper 7970X,
boost on, one pinned core per measurement. Figures compare builds; they are
not absolute throughput.

## Bit-exactness

`bitexact.sh` encodes with `pcmdsd` through the original build (forced
scalar) and the patched build (`auto` and each forced tier), and compares
whole-file SHA-256. DSD64 to DSD1024, 1/2/6 channels, five signals, 88.2 and
176.4 kHz input.

- 540 of 540 runnable cases identical; `bitexact.log`.
- The 60 cases the original build refuses with interpolation overload
  ("hot" and "noise") were rerun on both builds: 120 of 120 refusals
  identical in message and exit status.
- No FMA instructions in any vector kernel object.

## Speed

`bench_p11.py --modes sdm`, 7 repetitions, CPU ns per native output bit:

| tier | before | after |
|---|---|---|
| scalar | 16.49 | 16.46 |
| sse2 | 14.63 | 9.88 |
| avx1 | 15.67 | 9.18 |
| avx2 | 14.41 | 9.17 |
| avx512 | 15.71 | 9.49 |

Complete conversion, 30 s stereo sweep at 88.2 kHz, CPU seconds, 3 runs:
DSD64 3.96 to 2.55 and DSD256 15.48 to 9.88, about 36% less, identical
output hashes.

## Gates

`check-dsd` and `make check` pass on the patched tree.

The handoff states that automatic dispatch is unchanged. Against
cb0f61b31 it is not: SDM `auto` moves from scalar to AVX2 (DSD64-256) and
AVX-512 (DSD512/1024). That was permitted on condition of bit-exactness,
which the results above show.
