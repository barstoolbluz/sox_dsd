# P13 Intel vendor coverage: correctness closed, performance still open

Run on an Intel Xeon Platinum 8488C (Sapphire Rapids) reporting avx512f,
avx512dq, avx512bw, avx512vl, avx2 and fma, by `tests/dsd/check_intel_avx512.sh`
at commit 1772e5ae.  Operator-executed on a cloud instance; the host report and
logs here are as returned.

## What this closes

The SOW does not permit inferring vendor coverage across vendors, and the
qualification host is AMD Zen 4.  This run supplies the Intel arm:

- `make check` 0, `make check-dsd` 0 at 36 pass / 0 fail.
- The P13 unit's four groups pass, including AVX-512F executable qualification
  on silicon that genuinely carries the ISA rather than under emulation.
- `check_p13_isa`, `check_p12_isa`, `test_p11_numeric`, `test_p11_integration`
  and `test_p12_channels` all pass, so tier isolation and the per-object flag
  discipline hold when compiled and run on Intel.
- Forced-tier output is bit-identical to the AMD record for all ten
  tier-and-family combinations.  See `cross-vendor-comparison.txt`.

The last item is the substantive finding and is stronger than the script was
written to check.  Internal agreement on Intel would show only that the tiers
match each other there.  Matching Zen 4 as well establishes the kernels are
bit-exact across vendors on this stimulus.

## What this does not close

- **Performance qualification remains OPEN on physical silicon.**  This run
  collects no throughput data by design: a cloud instance has no governor or
  boost control and shares cores, so a number from it is not admissible under
  `tests/dsd/BENCHMARKING.md`.  Nothing here may be read as throughput
  evidence, and P13's own disposition is unchanged by it.
- Bit-exactness is established on the stimulus the script uses, a 3-second
  997 Hz tone at 88200 Hz and its DSD64 re-encode.  It is not a claim about
  every input.
- The comparison is over 80-bit hash prefixes, because the Intel run did not
  record full hashes.  The script now writes
  `kernel-output-sha256.txt`; a future run can make this a whole-hash
  comparison.
- No profile is promoted and no default changes.  P15 governs activation.

## Our reading, which you should check

We believe this discharges the Intel half of P13's correctness and dispatch
coverage, and that the cross-vendor bit-exactness is the load-bearing evidence.
That is our interpretation of runs we did not execute ourselves and of a log
supplied to us; the determination is not ours to issue.
