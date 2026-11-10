# SoX DSD 1.1.1 qualification and reproducibility

This page distinguishes executable regression checks from past qualification
receipts. The source, not the legacy phase handoffs, defines shipping behavior.
See [release notes](RELEASE_NOTES_1.1.1.md) for 1.1.1 defaults and limitations.

## Runnable checks

After `autoreconf -i`, `./configure` and `make` in a Git checkout:

```sh
make check
make check-rename
make check-sdm-guard-policy
make check-dsd-cli
make check-dsd-release-111
make check-dsd-loud-encode
make check-dsd-loud-guard
make check-dsd-optimization
make check-dsd
make check-dsd DSD_PHASE=P15
make check-dsd DSD_PHASE=P10
python3 tests/dsd/test_111_receipt_redaction.py
python3 tests/dsd/review_111_evidence.py --check-expected
```

For the independently reported numerical checks and other scripts, consult
[`tests/dsd/README.md`](../../tests/dsd/README.md) and the test entrypoints.
Test results can be written outside the source tree with `DSD_RESULTS=...` or
`--results ...`. `make dist` must produce a source release that builds and
passes its own checks without the separately published evidence archive.

With Nix available, `nix build .#default` produces the full build and
`nix build .#checked` runs the DSD check target on the builder's supported
CPU ISA tiers. A successful run on one CPU does not qualify unexercised ISAs.

## Qualification limits

A passing regression test verifies the scoped property it asserts, not every
hardware transport, third-party decoder, extended-duration stability envelope
or external recording. In the supplied 2026-11-09 1.1.1 host observations,
the independent-reader campaign completed 24 synthetic cases but reported
`INCOMPLETE` for 12 commercial-media tracks absent on that host. Its exit
status of 1 in that scenario is expected, not a passing full media gate.

The 800-row high-rate release receipt has a path-redacted reference fixture
under `tests/dsd/release_evidence/`, used by an executable determinism and
privacy check. This reference is **test data**, not a raw campaign directory.
Historical run receipts, phase decisions, provenance logs, manifests and
experimental measurements are in the standalone **SoX DSD 1.1.1 evidence
archive** published with the release. It includes a per-file SHA-256 ledger,
redaction counts and the original repository-relative file names. Do not
infer that those historical results were rerun as part of the repository
cleanup.
