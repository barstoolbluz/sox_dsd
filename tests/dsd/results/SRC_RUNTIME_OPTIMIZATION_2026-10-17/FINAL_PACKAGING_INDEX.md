# Final packaging index

This index describes the final staged payload. The earlier `BUILD_EVIDENCE.md` and `agent_build/STAGED_MANIFEST.json` remain unchanged as historical staging records.

Original workspace prefix: `/workspace/scratch/4dd8292178b8/`. Staged directory names retain their workspace suffixes. In particular, original `work-evidence/` paths map to `work-evidence/` here. JSON paths and commands retain their original spelling; derived primary observations resolve logs against their explicit parent directory.

Final work-evidence copy: 6,285 files, 49,834,029 bytes. Temporary work payloads, generated audio, Python cache files and object/archive intermediates were omitted from that new copy. Original files in the attached repository, including original audio and build artifacts, remain in the full source archive.

| Staged group | Regular files | Bytes |
|---|---:|---:|
| `(root files)` | 10 | 637,144 |
| `agent_build` | 332 | 3,759,412 |
| `agent_dsd` | 149 | 16,214,398 |
| `agent_src` | 30 | 674,153 |
| `build-baseline` | 11 | 16,477,128 |
| `build-candidate` | 14 | 8,268,318 |
| `build-candidate-guard1` | 13 | 8,258,253 |
| `build-default-off` | 2 | 3,567,695 |
| `build-default-off-guard1` | 2 | 3,567,581 |
| `build-sanitize` | 7 | 14,894,990 |
| `build-sanitize-guard1` | 7 | 40,206,428 |
| `documentation` | 5 | 93,151 |
| `screen-variants` | 20 | 14,215,300 |
| `work-evidence` | 6,286 | 49,979,295 |

These group counts exclude this final index and `SHA256SUMS`. The standard `SHA256SUMS` file binds the final evidence payload while excluding itself. The full repository has a separate internal manifest, which includes the evidence manifest and excludes only itself. External archive/patch/report hashes are recorded outside both archives, avoiding circular hashes.

The support patch contains only new tests, helpers, documentation, references and selected reproducibility scripts/corpora. Its empty-directory application and byte comparison are recorded in `support-patch-verification.json`. The final frozen-source audit is `FROZEN_SOURCE_PACKAGING_AUDIT.json`. The primary incomplete receipt, extracted 48-case subset, recovery case, failed control receipt, revised controls and diagnostic repeats remain identifiable separately.
