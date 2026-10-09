# P00 corrective pass: the automake `check-am` collision

A P00 harness correction, not P01. Tree: `sox_ng-P00a-5b931b6f.tar.gz`,
SHA-256 `e56b1bf2ea3115ecef14e052f0e186ec038d8d347c482ecf57426606a80524d2`,
no `.git`. Governing documents are in `docs/dsd/`.

P00 registered its test probe as `check_PROGRAMS = dsd_test_io` in
`test/Makefile.am`, which collides with the `check-am` rule the baseline
already defines in that file. Make resolves it by position, so `make check`
currently does the right thing by luck rather than by construction.

**Outcome wanted:** the probe is registered such that nothing generates a
competing `check-am`, the warnings are gone, and `make check` and
`make check-dsd` behave exactly as they do now — same tallies, same
classifications, legacy programs still built, `check.sh` still run. Production
sources unchanged. The frozen expected failures stay frozen; this is not
authorization to repair them. Return a complete tree with the regenerated
`tests/dsd/results/P00/P00_SHA256SUMS.txt` and a deviation note appended to
`docs/dsd/handoffs/P00.md`.

Observations from our own look, offered as hints and quite possibly wrong or
incomplete — trust your own reading over them:

- `noinst_PROGRAMS` appeared to work cleanly for us.
- `test/Makefile.am` already sets `EXTRA_PROGRAMS = wav_size_state_test`, so
  reusing that variable without `+=` seemed to silence the warning while
  breaking `wav_size_state_test`. Worth checking whichever route you take.
- Two earlier repository-side edits are ours, not P00 defects:
  `P00_SHA256SUMS.txt` was moved to `tests/dsd/results/P00/`, and
  `docs/dsd/DSD_HANDOFF.md` went from mode 100755 to 100644.

Please leave previously recorded evidence as delivered rather than rewriting
it to match the new state, and flag anything here you find to be mistaken.
