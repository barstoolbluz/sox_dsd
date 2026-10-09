# P04 continuation checkpoint (2026-10-08)

Input archive: `/mnt/data/sox_ng-P04-21ac0e78.tar.gz` (immutable); SHA-256 recorded at `tests/dsd/results/P04/build/input_archive.sha256`. The supplied archive contains no `P04_brief.md`; `docs/dsd/sows/P04.md`, `DSD_DESIGN.md` and earlier handoffs govern.

Implementation state: New `src/sox_dsd.h`, `src/dsd_layout_i.h`, `src/dsd_layout.c`, `src/dsd_layout_query.h`. Native DSF/DFF/WSD parsing, owned layout APIs, pre-header writer installation, WAV extensible mask bridging, CLI role assignment/loss policy/remix remapping are implemented. A successful `make -j2` with zero compile warnings and `python3 tests/dsd/run.py --phase P04 --results tests/dsd/results/P04` with 36 PASS / 0 XFAIL / 0 FAIL has been observed. See `tests/dsd/results/P04/build/{make-iter4,runner-iter4}.log` and `tests/dsd/results/P04/run.json`.

**Do not treat this intermediate checkpoint as the final handoff.** Remaining work: independent P04 C/CLI fixture tests and integration into check-dsd; validate WAV PCM/float, DFF metadata fidelity, role ownership, rejection policies, exact channel reorder; rerun complete generic/numeric/benchmark gates, inspect warning-free clean build, create final handoff, inventory and complete tarball. Resume from this tree and the latest `.tar.gz` checkpoint; do not start over from original unless rollback needed.

Update: All 28 independent cases from `tests/dsd/test_layout.py` pass; records under `tests/dsd/results/P04/layout/layout.json`. `src/formats.c` now rejects WAV encoding/alias combinations that cannot serialize a mask. `src/dsd_layout_i.h` retains source-physical DSF bit order. The full check-dsd target includes P02 and P03 inherited probes plus the new P04 matrix. Full generic/numeric/benchmark qualification, final clean build and packaging remain to be completed.

Final continuation note: The independent matrix was expanded from 28 to 30
cases with WAV front-center round-trip and unrelated PCM compatibility checks.
Versioned public getter records now accept bounded known prefixes, validated
from C11 and C++17, and the final runner remains 36/0/0. The final authoritative
continuation tree is the archive containing `docs/dsd/handoffs/P04.md` and
`tests/dsd/results/P04/P04_SHA256SUMS.txt`, not the early checkpoint archive.
The controlled-host benchmark gate is inconclusive (4.6% timing spread versus
2% admission), and the optional `make dist` gate requires manual tools absent
from this host. This does not invalidate the successfully built complete
continuation tarball.
