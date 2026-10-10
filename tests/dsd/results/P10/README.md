# P10 evidence: qualification FAILED, profiles unpromoted

Start with `numeric/qualification.json`, `soak/soak.json`, `reference/p10_profiles.json` (under tests/dsd), and `docs/dsd/handoffs/P10.md` (from the source root).

`run.json` is the inherited 36-case floor, not qualification. `implementation.json` is the six-group P10 implementation result. `cli/p09-control/cli.json` adds two baseline comparisons to the default 63-case CLI suite. `performance/summary.json` includes read/repack and unchanged normal-kernel controls and is INCONCLUSIVE. `sanitizers/summary.json` separates a passing P10 core from the inherited blockers in broader CLI coverage.

`certificate-input.json` is an immutable snapshot used by the negative-certificate generator. `training/training.json` is immutable calibration evidence. `numeric/qualification.json` is the current aggregation and can be recomputed without changing render rows. Superseded reports retain their own names and identities; they must not be merged or cherry-picked as a new pass.

A retained failed 30-minute attempt is not a completed 30-minute soak. Initial failure reports, replay reports and saved state files all remain under `soak/`. Candidate access is limited to an uninstalled test binary; no production experimental switch enables it.
