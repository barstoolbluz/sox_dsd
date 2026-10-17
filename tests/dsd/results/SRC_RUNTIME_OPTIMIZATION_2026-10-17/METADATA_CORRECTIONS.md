# Interpretation of retained exploratory records

These corrections are explicit so historical filenames or labels cannot be
mistaken for the final evidence. Original measurements and captured hashes are
preserved.

1. **Profiler construction.** The first executable named `sox_dsd_profile`
   compiled the CLI with `-pg`, while every DSP/library object remained
   uninstrumented. Its bytes are retained as
   `build-baseline/sox_dsd_profile_cli_instrumented`. The corrected
   `sox_dsd_profile_linkonly` compiles both CLI and library normally and adds
   `-pg` only at link time. The final `src-profiles-linkonly` attribution uses
   that corrected binary. Earlier SRC and DSD profile screens must retain
   their CLI-instrumented label. Ordinary baseline/candidate CLI timing uses
   neither profiler.

2. **Output-format label.** The reused `profile_decode.host()` description says
   WAV output. That is correct for the existing DSD profile driver but was
   inherited incorrectly by early raw-PCM SRC screens/profiles. Their command
   arrays and output hashes describe the actual raw signed-32 PCM output.
   The final benchmark/profile runners override this descriptive field. No
   audio conversion or timing was changed to fix the label.

3. **Operator graph versus execution.** Earlier operator-identity reports used
   the counter name `pairs_executing_changed_family`. The exporter initializes
   and serializes stages; it does not process audio. The corrected final
   `operator-identity-final-reviewed` report calls this
   `pairs_with_rational_fir_stage`: twelve of 24 graphs contain that family.
   Real filter execution is covered separately by exact C tests and timing.

4. **Threshold experiment completeness.** The temporary comparison captured
   861 of 867 expected rows despite a zero process exit. Its first sixteen
   cases have fifteen measured rounds; the final case has thirteen. The
   metadata records the discrepancy and that final case was excluded from
   the threshold decision. No missing values were synthesized. The final
   real-FIFO measurement contains all 765 expected rows and is controlling.
   The final tiny-call slowdown is disclosed, even though the temporary
   threshold experiment looked more favorable.

5. **Sanitizers.** LeakSanitizer explicitly failed because it cannot inspect
   this ptrace environment. Leak checking is UNRUN. The later successful
   address/undefined-behavior run disables only leak detection and instruments
   all 216 library objects. It does not convert a leak check into a pass.

6. **Early P14 invocation.** An initial direct P14 probe call omitted its
   required arguments and returned its usage exit. The corrected invocation
   uses the existing numerical Python driver and passes on both baseline and
   final candidate. The initial log is preserved as a harness-use error.

7. **Default-off source identity.** Identical emitted `.text` does not preserve
   a changed source header's SHA-256. Existing P15 source-bound receipts keep
   their original identities, and no old source pins or thresholds were edited.
   Restoring the frozen reference header recovers the original production
   source for archival verification. The 24-conversion default-off replay
   belongs to the earlier guard1 record; the final guard2 control separately
   verifies emitted-code identity.


## Final primary receipt persistence gap

The original primary runner printed PASS, but the saved JSON remained RUNNING
with 1,761 of 1,764 expected rows. The cause was not established. The original
bytes remain unchanged. A hash-pinned extraction independently verifies every
complete case and all stored arm and paired-ratio statistics, selecting 48 cases
and 1,728 rows. Stored bootstrap intervals remain verbatim. All 33 captured rows
of the incomplete final case are excluded from the accepted summary; a full new
36-row run uses the identical case and fixture. Recovery verification confirms
that the combined case set is the original 49-case corpus.

The benchmark runner now fsyncs its final receipt and writes a separate
completion record containing its hash, after all child timings end. The exact
previous harness text is preserved as
`work-evidence/bench_src_optimization_before_receipt_seal.py`; its SHA-256 matches
the original primary receipt. This support-only finalization change does not
alter either production executable. An old completion message is never used as
a substitute for the saved raw records.

## Original small-buffer control failure

The original 21-case control run stops with FAIL on the frozen baseline's
32-byte stereo 48→44.1 kHz preflight: 2,220 output frames instead of 441,000.
A direct diagnostic reproduces identical truncated bytes in the candidate.
Both builds also truncate at 64 bytes (2,234 frames). Both have the expected
length and matching baseline/candidate hashes at 128 and 256 bytes, although
the two buffer settings produce different hashes in both builds.

The revised corpus replaces only that reverse 32-byte control with 128 bytes.
The successful 32-byte forward case is retained. The original failed receipt,
case list, direct diagnostic and revision rationale are all preserved.
Truncated outputs and the aborted run are outside accepted throughput totals;
no expected-length or output-equality check was weakened. Exact CLI identity
means matching settings across builds, not arbitrary cross-buffer invariance.

## Causal attribution wording

The same-executable stage comparisons reduce unrelated whole-binary layout
confounds. They still include function layout, setup and register-allocation
differences. They do not provide an exact additive attribution of benefit to
pairing alone. The final one/two-input latency regressions demonstrate that
limitation. The final integrated report and corrected new assessment use this
narrower wording; original independent snapshots remain historical evidence.
