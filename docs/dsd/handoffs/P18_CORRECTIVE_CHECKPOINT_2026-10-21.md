# P18 corrective checkpoint — 2026-10-21

**Authority unchanged:** P18_COMPLETE_FAIL_CLOSED; all 12 DSD512/1024 capability rows disabled. No independent high-rate media, player, DSP certification or device qualification is claimed.

Base continuation Git HEAD `66155d1` is synthetic (original 51c391f2 source archive had no `.git`). User's independent reproduction identifies two real defects: (1) default and `--dsd-mode legacy` allow SoX output-format negotiation to replace explicit DSD512/1024 with DSD256 and write a file; (2) uppercase DFF path or `-t DFF` yields misleading **DSF** write refusal from P05 planner.

Correction in progress: `src/formats.c` checks exact requested high rate against resolved canonical DSF/DFF handler before file open; `src/dsd_plan.c` case-insensitive matching only for DFF explicit type/path suffix. `tests/dsd/test_p18.py` adds eight default/legacy denial cases and four uppercase DFF planner cases; `tests/dsd/test_p18.c` checks four direct `sox_open_write` denials and retention of original file bytes. Six qualified lower-rate DSF/DFF writer regressions cover all DSD64/128/256 native clocks. Manifest source hash list adds `src/formats.c` and expects 106 integration cases. No generic rate negotiation or DSP hot paths altered.

Next: clean rebuild (`make -B` where needed to defeat inherited stale-object mtimes), focused P18 C and CLI test, complete generic and DSD regressions, P16 replay, P18 numeric/benchmark evidence, `check-rename`, manifest reseal/check, Git commit, downloadable full tree and correction-only bundle. Record new statuses and unresolved gates in `handoffs/P18.md`. Preserve frozen P00/P15 provenance, no assertions relaxed.

## Corrective closeout checkpoint

Source Git checkpoint `ad8d9f7` passed clean rebuild, generic `make check`, 398 C checks, 106/106 P18 CLI, 219/219 P16 fresh/cached, 45/45 P18 DSD suite, 11 numerical development checks, 36 inherited development benchmark cases, `make check-rename`, and P18 manifest `--seal`/`--check`. All invocations exited zero (`tests/dsd/results/P18/build/corrective-gates.status`). The source manifest tracks the added `src/formats.c` SHA-256, and all 12 high-rate rows remain denied. See `P18_CORRECTIVE_2026-10-21.md` for reproducible details. Next: commit the authoritative new evidence and package a fresh clone so no compiled binary can mask the source.
