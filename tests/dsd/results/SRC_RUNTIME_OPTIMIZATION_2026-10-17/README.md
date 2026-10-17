# Production SRC optimization evidence — 2026-10-17

The controlling production header is `src/rate_poly_fir0.h`, SHA-256
`c1626c26f7ba8d64f2b69752906948b527923745313d13c41f78c47046552591`.
The measured final candidate CLI has SHA-256
`750ea8d25c563ee5f12ebb587b4613f8669c441a3f7b8c8057ef92ce76774f42`;
the frozen baseline CLI has SHA-256
`fad06a388cbf112945a1e66a8f4fd6213a156f9a5f8919a66efe7ed1dd94a004`.
These are local virtual-host engineering results, not a P15 release certificate
or a prepared physical-host performance gate.

## Controlling results

| Evidence | Location |
| --- | --- |
| Consolidated CLI timings, throughput, memory and intervals | `benchmark-summary.json` |
| Readable complete benchmark tables | `BENCHMARK_TABLES.md` |
| Primary 49-case corpus and accepted observations | `work-evidence/final-cases.json`, `work-evidence/primary-completed/measurements.json`, `work-evidence/primary-last-case/measurements.json` |
| Twenty-one buffer/quality/ISA and DSD256 continuity controls | `work-evidence/controls-cases-validated.json`, `work-evidence/final-controls-validated/measurements.json` |
| Diagnostic repeat selection and any resulting repeated measurements | `work-evidence/repeat-policy.json`, `work-evidence/repeat-selection.json`, `work-evidence/diagnostic-repeats/` |
| Preserved incomplete primary and failed original controls | `work-evidence/final-paired/measurements.json`, `work-evidence/final-controls/measurements.json` |
| Inherited small-buffer truncation and corpus revision | `work-evidence/small-buffer-diagnosis/diagnosis.json`, `work-evidence/controls-corpus-revision.json` |
| Final same-executable real-FIFO kernel timings | `agent_dsd/real-fifo-final/` |
| Final exact-output and fully instrumented sanitizer checks | `agent_build/final-build-validation-summary.json` |
| GCC O2/O3 focused translation-unit tests and x87 fallback | `agent_dsd/correctness-final/results.json` |
| Final initialized operator/coefficient identity | `work-evidence/operator-identity-final-reviewed/identity.json` |
| Original file preservation and source delta | `work-evidence/frozen-archive-audit.json`, `work-evidence/production-patch-verification.json` |
| Final generated code and code-size observations | `work-evidence/final-rate-disassembly.txt`, `work-evidence/code-size.json` |

The engineering report in `docs/dsd/SRC_RUNTIME_OPTIMIZATION_2026-10-17.md`
is the final integration decision. Its results take precedence over prospective
wording in earlier independent review snapshots. The separate proof and P15
assessment describe the exact recurrence, operation ordering, source-binding
requirements and qualification limits. Reproduction commands are in
`docs/dsd/SRC_RUNTIME_OPTIMIZATION_REPRODUCE_2026-10-17.md`.

The original and repeated observations are both retained. A diagnostic repeat
does not replace an unfavorable primary observation. Bootstrap intervals are
per-case descriptions of run variation, without a multiple-comparison correction.

## Historical experiments and path mapping

`agent_src/` retains isolated header prototypes. `screen-variants/` retains
the measured alternative CLIs, build commands and changed source headers.
`work-evidence/screen-independent/` and `screen-pair2/` hold exploratory
production comparisons. Those runs have fewer repetitions and earlier source
identities; they are selection evidence, not the final candidate's performance
receipt. `agent_dsd/threshold/` explicitly retains an incomplete final experimental
case; it is not substituted for the complete final kernel or CLI results.

The raw JSON files are copied without rewriting their original command paths.
For archived evidence, replace the prefix `/workspace/scratch/4dd8292178b8/`
with this evidence directory for `agent_build/`, `agent_dsd/`, `agent_src/`,
`work-evidence/`, `screen-variants/`, and the retained `build-*` directories.
The longer prefix ending in `/sox_ng/` instead maps to the extracted repository
root. Per-agent indexes document their selected binaries and omitted files.
Historical guard1 paths must resolve to the corresponding preserved guard1
directory and hash, not the final executable at a reused workspace pathname.

Generated PCM/DSF/WAV stimulus and output payloads, compiler object files and
complete static libraries are omitted from new evidence where deterministic
regeneration or rebuilding is sufficient. Their generation rules, input/output
hashes, build flags, and measured executable identities are retained. This
omission concerns new measurement intermediates; all files in the original
attached repository remain in the complete source bundle.

See `METADATA_CORRECTIONS.md` for corrections that leave historical raw evidence
intact, and `BUILD_EVIDENCE.md` for the build and sanitizer details.

## Receipt completion and inherited buffer behavior

The original primary JSON remains `RUNNING` with 1,761 of 1,764 expected rows,
despite the runner's completion message. A complete-case extraction verifies
48 cases / 1,728 rows and retains its parent hash and original log paths. All
33 captured rows of the incomplete last case are excluded from the accepted
summary; the entire final short case was rerun separately with 36 rows and a
verified completion hash. No missing observations were reconstructed.

The original controls JSON remains `FAIL` after a baseline preflight produced
truncated output for the 32-byte 48→44.1 kHz case. Direct checks show both builds
share the truncation at 32 and 64 bytes, while 128 and 256 bytes have the expected
length and identical baseline/candidate output at each setting. Cross-buffer
hashes differ in both builds. The revised reverse control uses 128 bytes. These
failed/truncated observations are retained outside accepted throughput totals.
The benchmark runner now seals its final JSON with fsync and a separate hash
record; that support change does not alter either measured production binary.
