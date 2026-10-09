# P02 DFF read hotfix evidence (2026-10-09)

**Controlled throughput gate: INCONCLUSIVE.** The measurements below are not admissible: every paired case used in the large DFF comparison exceeded the design's 2% measurement-noise limit. CPU 1's nine-run host noise probe showed 25.6% spread; probes on CPUs 0, 2, 3 and 4 likewise exceeded 2% (3.0%, 15.2%, 9.5%, 20.4%). This virtualized container does not provide the required clock/SMT/governor controls. No claim of formal passage is made.

- `p01-versus-p02-optimized.json` contains all 544 successful benchmark commands, with executable paths and other machine-specific command information omitted. This is the P01-relative regression measurement. The candidate uses the accepted P02 source with **only** the hotfixed `dff_read()` logic applied, avoiding later P04 channel-layout changes. The six historically comparable repack workloads still hash-identically, and the intentional P02 six-channel small differences remain excluded. Noise makes the aggregate verdict `incomplete`.
- `p05-before-after-first.json` and `p05-before-after-repeat.json` compare independently built original P05 and hotfixed P05 trees using the same explicit channel-identity-loss policy in both arms. Both demonstrate lower DFF CPU time in all four large cases. Each run has >2% noise. The first run uses 25 pairs; the repeat uses 15. These are not P01-relative certification.
- `p05-byte-equivalence.json` independently compares eight repack outputs of the supplied tree and this hotfix (DFF and DSF, two and six channels, small and large buffers), including complete output sizes and SHA-256 hashes. All eight match.
- `validation-summary.json` records compiled regression gates and excludes machine-local paths.
- `SHA256SUMS.txt` records every delivered source/evidence file except itself; run `sha256sum -c tests/dsd/results/P02/DFF-read-hotfix-2026-10-09/SHA256SUMS.txt` at the archive root.

Historical results elsewhere under `tests/dsd/results` are unchanged. The controlled-host repro instructions and handoff are in `docs/dsd/handoffs/P02_DFF_READ_HOTFIX.md`.
