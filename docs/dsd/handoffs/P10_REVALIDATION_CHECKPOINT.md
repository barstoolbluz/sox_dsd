# P10 revalidation: final continuation checkpoint

Input archive SHA-256:
`4b182e38fd94ace650faa6a18494cc40c8013151bd9bd621d9915553183fe0b8`.

The revalidation is complete after confined harness and documentation fixes.
Read `P10_REVALIDATION.md` first. The nominal runner now writes its fixture
identity and respects the selected executable. The collector rechecks raw
stage evidence, distinct native-rate coverage and audited soak measurements.
The source-sample identity overstatement is corrected and measured.

Fresh checks: build and both generic/DSD suites; 36 inherited regressions;
105,474 core assertions; 63 CLI cases; 14 original accounting tests; three replay
tests; 16 corrective collector tests; four live short receipt tests and a full
1,800-second DSD64 runner roundtrip; all 183 bitstream comparisons; all 18 stage
probes. The fresh DSD64 run reproduced all 31 archived continuation states.
No runtime source, fixture, coefficient, bound or activation flag changed.

The authoritative bundle includes all historical evidence unchanged, separate
new observations under `tests/dsd/results/P10_revalidation/`, and a regenerated
P00 archive-member hash index. Rebuilt debug executables can have a different
SHA-256 because of their build path; rerun into a new result directory rather
than rewriting a binary-pinned receipt.

P10 release qualification is still INCOMPLETE. Representative-hardware/ISA
one-hour runs and an independent real-world corpus remain unrun. There is no
P11 handoff or profile/default promotion. The next permitted work is completion
of those outstanding qualification gates with separate versioned evidence.
