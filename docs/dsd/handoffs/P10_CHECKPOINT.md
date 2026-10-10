# P10 continuation checkpoint

Task date: 2026-10-09. Status: **QUALIFICATION FAILED; UNPROMOTED**.

This is the authoritative source continuation, not an in-progress build tree. Read `docs/dsd/handoffs/P10.md` and `tests/dsd/results/P10/README.md` first. Implementation, regression tests, negative certificates, numeric comparisons, original failed soaks, replay states and noisy performance measurements are retained.

No mastering profile is qualified. The next work is P10 qualification continuation; do not advance automatically to P11 or activate a default. Preserve the original coefficient bits, analysis-v1, frozen training/guard identities and failed evidence. New scientific experiments require separate versioned result IDs.

Resume by rebuilding the source, checking the negative certificates, and inspecting the current and superseded results before running a new experiment. Soak continuation uses deterministic prefix replay and verifies saved states. A mismatched state is a failure, not permission to replace prior evidence. Full numeric evaluation rejects changed source/corpus/guard identities; training cannot silently overwrite its frozen evidence.
