# P11 force-override corrective evidence, 2026-10-11

The documented `SOX_DSD_KERNEL_FIR` and `SOX_DSD_KERNEL_SDM` environment
variables are authoritative. Previous `LSX_DSD_*_KERNEL` spellings work only
as lower-priority compatibility aliases. P05-era preflight now accepts P11
implemented tiers for **active** decoder/encoder contexts and ignores invalid
forces when that kernel family is inactive. The public decoder's optional
`kernel_fir` option overrides environment, and its older initializer only
writes the legacy version-1 record prefix. The full record has an additive
`sox_dsd_decode_options_init_extended` initializer.

`commands.tsv` and the matching logs are the post-ABI-correction complete
verification run (12 executable gates, 12 success exit codes). The integration
log covers 29 end-to-end executions and the P05 planner regression 156 passes;
`verification.json` records changed file hashes compared with the original
P11 archive and confirms earlier phase files are unchanged. The post-ABI
build logs document incremental rebuild success. Source, benchmark and test
results remain available under `tests/dsd/results/P11/`.

Both P11 hardware-compatibility gates remain unrun: execution on AVX1 without
AVX2, and startup on a genuine non-AVX host. Nothing in this correction
modifies or re-ratifies the original P10 certification record.
