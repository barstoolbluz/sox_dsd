# P10 gate assessment with both corpus arms present (2026-10-11)

**Every gate the ratification criterion defines now passes, and
`remaining_release_gates` is empty.** This was produced by running the
ratification round's own collector, `tests/dsd/qualify_p10_ratification.py`,
unmodified, at its default paths.

| Gate | Status |
| --- | --- |
| `independent_realworld_corpus` | PASS |
| `inherited_analysis_v1` | PASS |
| `inherited_numeric_183_bit_identical` | PASS |
| `inherited_prepared_host_read_repack` | PASS |
| `no_promotion` | PASS |
| `nominal_30min_all_rates` | PASS |
| `original_expected_overload_replay` | PASS |
| `regressions_and_candidate_cli` | PASS |
| `representative_hardware_1hour_per_profile_isa` | PASS |
| `stage_unity_scaling_and_distribution` | PASS |

Overall `status` is `PASS`. `qualified` is `False` and `promotion` is
`BLOCKED`, and the collector's own `profile_activation` field explains why:
"UNQUALIFIED: requires explicit positive certification; P15 governs defaults"

So passing every gate is not the same as a qualified profile. The collector
distinguishes the two deliberately, and records that an explicit positive
certification is still required and that P15 governs activation defaults. That
certification is a judgement, not a measurement, and nothing here makes it.

## What changed to get here

Nothing was measured again. The corpus gate had read `PARTIAL` only because the
collector reads both domains from a single base directory,
`results/P10_realworld_corpus_2026-10-10`, looking for `pcm-sources.json`,
`pcm-unity.json` and `pcm-ladder.json` alongside the DSD files, and the PCM arm
had been filed in a separate directory of its own. The four PCM records now sit
where the collector was written to expect them. That layout was the ratification
round's design; putting them elsewhere was our error.

The per-domain result, recomputed by that collector from the rows rather than
read from any summary:

- `DSD_NATIVE`: PASS, 18 sources, 14 admitted at unity, 4 explicitly rejected
  and then admitted under declared attenuation, 12 genres.
- `PCM_AUDIO`: PASS, 51 measurements, 51 admitted, 13 genres, both clock
  families.

## On evidence that cannot be re-rendered

The collector states its own limitation: "Recorded hardware provenance and audio
hashes are operator-supplied; external commercial sources are not distributed or
re-rendered here. The 1-hour soak qualifies the scalar P10 recurrence, not legacy
SIMD or future P11 runtime kernels."

That is the honest shape of these two gates. The corpus is 19 privately held
commercial releases and the soak needs real hardware time; neither can be
reproduced by a model session, and the criterion was written to accept attested
measurement with provenance rather than to demand re-execution. Whether that is
the right standard is a question about the criterion, not about these runs.
