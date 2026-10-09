# P06 read hotfix checkpoint (P07 not yet introduced)

2026-10-09. Input SHA-256: a0bc9bfd334809617f9719954d9bcc884db91db8540c100609d2bf30da8ef0d4.
Single candidate source modification: src/dsdiff.c, special six-channel partial-cluster
expansion into contiguous interleaved PCM samples; original byte state and all
other read paths retained. Historical benchmark and P00-P06 evidence unchanged.
P05 at 149ea582 is not part of the input archive; do not represent a measurement
using P06-before/after as P05 gate qualification. Next: finish isolated tests,
record equivalence/performance and decide whether this targeted optimization
is credible, before P07 edits.
