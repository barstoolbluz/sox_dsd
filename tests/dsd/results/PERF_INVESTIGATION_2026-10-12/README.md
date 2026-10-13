# Performance investigation evidence

Final decision report, relative to the source root:
`docs/dsd/PERFORMANCE_INVESTIGATION_2026-10-12.md`.

Use these final measurements:
- `controlled/kernels/kernel-timing.json`: 11 explicit workloads, 5 tiers,
  15 observations each; process CPU time measured inside the C benchmark.
- `controlled-final/decode-88200/attribution.json`: all five forced FIR tiers,
  normal wall/child CPU observations and link-only sampling profiles.
- `controlled-final/decode-44100/attribution.json`: SSE2 final-SRC control.
- `controlled-final/decode-with-report/attribution.json`: SSE2 reporting control.
- `controlled/encode-e2e/forced-cli-timing.json`: unchanged existing runner;
  176400-Hz decode and encoder controls, 15 observations per family/tier.

`controlled/decode-*` and `profile-initial/` are exploratory, not the final
wall-timing basis. `exploratory/README.md` documents the investigation runner's
corrected timeout-polling issue and preserves its prior source. Their raw CPU
and gprof samples are retained for audit, not silently reclassified as final.
The initial shell profile was restarted after a directory-creation mistake;
those exploratory logs are not a qualification gate.

`regression-p14/` and `make-check-dsd-p14.log` retain the inherited explicit P14
regression. `make-check.log` retains the configured generic suite, including
its named format skips and VOID cases. `measurement-tests-final.log` records
13 new tooling tests. `validation-summary.json` summarizes completed checks.
`production-source-identity.json` verifies all 258 original production C/header
files. `source-and-arithmetic-audit.json` records the historical evidence gaps,
source matches and corrected arithmetic.

`binaries/` retains exact local audit executables, not portable releases.
To re-read a retained profile from the source root:

```sh
e=tests/dsd/results/PERF_INVESTIGATION_2026-10-12
gprof -Q -b "$e/binaries/sox_dsd_profile" \
  "$e"/controlled-final/decode-88200/profile/sse2/*/gmon.out
```

Receipts intentionally retain commands and absolute paths as actually run.
The former `/mnt/data/perf_investigation/evidence/` maps to this directory;
the former `/mnt/data/perf_investigation/work/sox_ng/` maps to the source root.
Input fixtures and raw gmon files are retained at their relative recorded
locations. New runs must use fresh result directories rather than overwrite
these receipts. Source/executable/gmon/input digests were checked at packaging.

No new physical-machine qualification, default activation or P15 completion
is asserted by a PASS status in this investigation.
