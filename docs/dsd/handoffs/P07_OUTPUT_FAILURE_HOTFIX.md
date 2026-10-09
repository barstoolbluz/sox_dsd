# P07 output-write and finalization-failure correction

Date: 2026-10-09. Corrects the P07 continuation archive
`sox_ng-P06hotfix-P07-complete-2026-10-09.tar.gz`. This handoff supersedes
**only** the output-error and `/dev/full` qualification in the historical
`docs/dsd/handoffs/P07.md`; it does not rewrite prior test or benchmark evidence.
The P06 reader hotfix and the P07 performance baselines remain separate.

## Defects reproduced before correction

1. **Short `sox_write()` reported success.** An independently generated mono
   2,822,400-Hz DSF with 262,144 native frames and deterministic non-silent
   random bit chronology was decoded to 88,200-Hz WAV. Under
   `RLIMIT_FSIZE` (with `SIGXFSZ` ignored in the subprocess), the unmodified
   P07 binary exited **0** and retained a truncated regular WAV at **each** of
   512, 1,000, 4,096, 5,000, 16,000, and 20,000 bytes. Its output effect
   returned ordinary `SOX_EOF` on a short write, so the effects engine did not
   distinguish it from normal termination.
2. **Buffered close failures and unsafe cleanup.** The P07 finalization path
   unlinked every `lsx_io_file` output pathname on close failure, even when
   the target was a character device. WAV stopwrite ignored a padding write
   result and the final seek result. Generic format close could overwrite a
   previous failure with a later successful header rewrite or seek, and only
   attempted a dedicated flush for stdout in one branch.

## Changes, limited to output error handling

- `src/sox_ng.c`: a short output write now reports an explicit diagnostic and
  returns `LSX_EFF_FATAL` without depending on `ft->sox_errno`. The main loop
  inspects the fatal status **before** the exhausted-input condition, including
  the final block. A single `close_output_checked()` closes once, clears the
  handle, propagates failure, and removes only a partial **regular file**,
  following the existing `cleanup()` policy; it never unlinks character
  devices, FIFOs, or other non-regular destinations. Normal EOF, trim, and
  user-directed effect termination continue to use their existing statuses.
- `src/formats.c`: preserve errors from sparse-byte completion, header rewrite
  and final seek restoration. A single end-of-writer `fflush()` detects late
  buffered errors, without adding per-sample flushes or changing buffering;
  its failed status remains latched even when subsequent close succeeds.
- `src/wav.c`: return failed padding and final header-position seek/tell
  statuses, while releasing the existing WAV allocations on pad failure.
- `tests/dsd/test_p07.py`: repair the existing buffered-close integration
  fixture. Its reused 32,768-frame clipping input can fail during active
  writing instead of finalization, so the test now supplies a short buffered
  stream, checks the finalization diagnostic, and asserts `/dev/full` retains
  its original character-device identity.
- `tests/dsd/test_p07_output_failures.py` and `Makefile.am`: register a focused
  executable P07 gate. The regular-file controls use the real filesystem and
  `RLIMIT_FSIZE`; the optional character-device control uses the existing
  `/dev/full` only when verified to be a character device. Missing resource
  limits give a named **UNRUN** with exit 2; an absent `/dev/full` is recorded
  **UNRUN**, never PASS.

The binary64 decoder, reconstruction FIR, SRC, clipping arithmetic, graph
sample format, and public `rate` implementation are unchanged. No new output
buffer, retry loop, transaction, or file-adoption machinery was introduced.

## Independent executable observations on the corrected binary

- The same six active-write size limits now exit **2**, emit `output write
  failed`, do not print `Done.`, and leave **no** partial regular file.
- A control conversion followed by a near-final-block size limit also returns
  nonzero, reports an output failure, and removes the incomplete output.
- A short 4,096-frame DSF conversion with a 128-byte output limit fails during
  buffered finalization rather than during active output flow. It returns
  **2**, emits `output finalization failed`, does not print `Done.`, and
  removes the partial regular WAV.
- `/dev/full` is a real character device on this host. The buffered
  finalization test returns **2**, reports the failed finalization, and
  preserves the same device inode and device number. It does not print
  `Done.`. This closes the corresponding former P07 **UNRUN** qualification
  for this host and corrected source.
- A successful DSD finite EOF, intentional trim, and unrelated byte-identical
  signed-16 PCM-to-PCM WAV copy retain exit status **0**.
- The focused test suite: **12 pass, 0 fail, 0 unrun**. Evidence is in
  `tests/dsd/results/P07/output-errors/output-failures.json`. The refreshed
  66-case CLI integration record is separately stored as
  `tests/dsd/results/P07/output-errors/integration-after-hotfix.json`.

## Build and regression gates

Commands executed against the corrected tree:

```
autoreconf -fi
./configure --disable-shared --without-libltdl CFLAGS='-O2 -g'
make -j4
make check
make check-dsd DSD_RESULTS=<SEPARATE_TEST_RESULTS>
python3 tests/dsd/test_p07_output_failures.py \
  --sox src/sox_ng --results <SEPARATE_OUTPUT_EVIDENCE>
```

**Exit codes and final result:** The first integrated `make check-dsd`
exited 1 solely because the existing `buffered_finalization_failure` fixture
was large enough to fail during active writing. That failure returned the
correct nonzero status, but correctly did **not** print the finalization-only
diagnostic the test demanded. The fixture was corrected and rerun with
`/dev/full` present, rather than weakening its assertion.

The following final commands all **exited 0**: `autoreconf -fi`,
`./configure --disable-shared --without-libltdl CFLAGS='-O2 -g'`,
`make -j4`, `make check`, and (after the fixture correction) `make check-dsd`
with results routed outside the historical phase directories. The standalone
focused output-error command also exited 0.

- Full DSD P07 runner: **36 pass, 0 fail, 0 skip, 0 xfail**.
- P07 decoder API: **171,537 assertions, 0 failures**; inherited P06 scalar
  unit: **93,640 assertions, 0 failures**.
- P07 conversion/integration suite: **66 pass, 0 fail, 0 unrun**. The former
  buffered close UNRUN is now an actual executable PASS on `/dev/full`.
- New output-error suite: **12 pass, 0 fail, 0 unrun**.
- Independent final SRC: **6 comparisons**; independent composite:
  **8 comparisons**; impulse/phase: **18 pulses**, all pass their existing
  numerical tolerances. No tolerance, reference, or DSP source was changed.
- Legacy public `rate`: **9/9** unchanged PCM goldens pass.
- Generic `make check`: **PASS**. Prior-phase DSD tests included in
  `make check-dsd` also pass.

No previous phase's recorded results or numerical evidence were overwritten;
new P07 correction evidence uses the separate `output-errors/` directory.


This patch does not reclassify the historical P06 or P07 **5% throughput
acceptance** gates: the requisite P05 baseline and prepared low-noise host
were not available in this round. The change adds finalization checks and a
single file-type check per output file, not work in the per-sample decode
fast path. It would be unjustified to claim a new throughput certification.

The complete deliverable is a source-only continuation archive. All historical
P00-P07 result bytes are retained unchanged, and
`tests/dsd/results/P00/P00_SHA256SUMS.txt` is regenerated for the delivered
source contents (excluding that manifest itself).
