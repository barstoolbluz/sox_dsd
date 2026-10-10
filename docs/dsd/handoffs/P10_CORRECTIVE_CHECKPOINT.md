# P10 corrective: resumable final checkpoint

Original attached source archive SHA-256:
`027b0872cfe9e21910424f9307afebfb3e5f273c0530e7d92dc70e4ca88db649`.

## Decisions and completed work

Reviewer's fixture-classification guidance independently supported. Private
actual-signal-path stage observer proves DC unity SRC/pre-FIR/native SRC and
one-half reference scale. Direct noise distributions prove filter-induced
overshoot; original 0.7 noise remains an explicit overload regression. Nominal
fixture v2 changes only that segment to peak 0.45 and is separately recorded.

The three continuous 30-minute nominal soaks completed with exact 5.08032,
10.16064, 20.32128 billion native frames respectively, no failures and all
snapshot hashes verified. Original overload reproduced at exact prior frames;
183/183 inherited bitstream render hashes matched. `make check` and the full
DSD regressions passed. Adversarial evidence-accounting suite passed.

Full release state remains `INCOMPLETE`: representative one-hour per-rate/ISA
hardware soaks and independent real-world corpus are **UNRUN**. Production
profiles remain unqualified and unpromoted. No P11 transition.

## Portable continuation steps

Extract the definitive source-only archive (the P00 index binds all its member
files). Build with P10's documented Autotools commands. Start with
`docs/dsd/handoffs/P10_CORRECTIVE.md`,
`tests/dsd/reference/p10_profiles_corrective.json`, and
`tests/dsd/results/P10_corrective/qualification.json`.

A newly rebuilt debug executable may hash differently due to embedded source
paths; do not use `--unit` against previous receipts without rerunning the
bitstream evidence in a new versioned result directory.

To resume qualification, use new versioned result directories for missing
hardware/ISA and independent-source tests. Leave historical P00–P10 evidence
and frozen analysis-v1 intact. Run `python3
 tests/dsd/test_p10_corrective_qualification.py` and `python3
 tests/dsd/qualify_p10_corrective.py`; the latter exits 2 until every release
requirement passes. Regenerate only the updated, versioned negative certificate
if its inputs change; do not rewrite the original P10 certificate or implicit
promotion flags. Update the P00 SHA-256 index and verify the resulting archive
before distributing another continuation.
