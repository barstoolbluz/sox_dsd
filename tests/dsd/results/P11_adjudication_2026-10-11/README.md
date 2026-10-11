# Independent P11 adjudication receipts (2026-10-11)

Authority: `docs/dsd/DSD_DESIGN.md` section 8; completion and risk list:
`docs/dsd/sows/P11.md`. Detailed disposition and exact command list:
`docs/dsd/handoffs/P11.md` (adjudication addendum).

Result: no reproduced runtime defect; build, generic/DSD regression, forced
CLI integration, numerical acceptance, ISA audit and independent prefix
replays pass. P11 compatibility qualification remains INCOMPLETE specifically
because QEMU cannot be rerun here and the furnished QEMU receipts do not
execute normal SDM in the AVX-without-AVX2 model. The new opt-in QEMU replay
script addresses precisely that narrow gate without changing runtime code.

Files: `receipt-consistency.json` contains 212 independent consistency checks
of the three supplemental evidence sets, including 16 independently
recalculated throughput bootstrap intervals. `soak-first-minute-replay.json`
records nine successful SHA-256 matches to archived first-minute snapshots.
`isa-isolation.json`, `phase-run.json`, `phase-measure.json`, `phase-bench.json`
and `forced-isa-cli.json` preserve independently generated raw output.
`commands.tsv` and `exits.tsv` include two exploratory setup errors, a
P10-regression invocation without its required separate baseline executable,
and long-command interruptions; see the handoff for correct classification.
`logs/` contains corresponding successful command outputs.

`qemu-status.json` is explicitly UNRUN: `qemu-x86_64` is absent, not a failed
ISA execution. Historical QEMU receipts in
`P11_avx1_no_avx2_2026-10-11/` remain unmodified.

Nine full-hour soak reports were internally checked, but the original archive
omits 540 intermediate snapshot state files listed by their manifests. The
nine first-minute hashes independently reproduced; the full one-hour runs
were not repeated in this adjudication. No full-hour reproduction is claimed.

`sanitization-manifest.json` tracks each path-only substitution in the new
adjudication receipts; numerical values, exit codes, existing evidence and
stored SHA-256 of the source run are untouched. The working host's benchmark
results are developmental, not prepared-host or physical older-AVX results.
