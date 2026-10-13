# An advertised decode profile that cannot be used

Found while auditing the P15 continuation. Our finding, which may be wrong.

## What happens

`dsdpcm -p legacy`, equivalently `--dsd-decode legacy`, fails at every output
rate we tried (352800, 176400, 88200, 44100) with exit 2 and:

```
sox_ng FAIL sox_ng: P05 preflight: DSD reconstruction is scheduled for
P06/P07/P08; plan with --dsd-plan (no output created)
```

P06, P07 and P08 are complete. The two profiles the release contract names,
`mastering` and `wideband`, both succeed at exit 0.

This is distinct from `--dsd-mode legacy`, the native repack path, which works
and which `test_p15.py` covers as `legacy_repack`. `docs/dsd/MIGRATION_P15.md:21`
draws that distinction itself: "`--dsd-decode legacy` selects generic legacy
reconstruction *within the new planner*, and does not mean `--dsd-mode legacy`."

## Where it is advertised

Three user-facing places offer it:

| location | text |
|---|---|
| `src/dsd.c:225` | `[-p mastering\|wideband\|legacy] [-l preserve\|sacd] [rate]` |
| `sox_ng.1:1398` | `--dsd-decode mastering\|wideband\|legacy\|decode.PROFILE.v1.dsdRATE` |
| `docs/dsd/MIGRATION_P15.md:18,21` | documents it as selecting the reconstruction profile |

The third is new in this P15 round: the migration guide written for the release
documents an option that cannot be exercised.

## Why we think it matters for P15 specifically

`docs/dsd/sows/P15.md` states the first release carries **two** decode
profiles, so `legacy` is plausibly not meant to be in it. Its completion
criterion is that "every advertised first-release feature has a passing
evidence ID", and its risk list includes release documentation misstating
semantics.

`test_p15.py` exercises `--dsd-mode legacy` but no case exercises the legacy
decode profile: `grep -cE "dsd-decode.*legacy|-p legacy"` returns 0. So the 134
CLI cases pass with an advertised option untested and non-functional.

## What we are not claiming

Not a DSP defect, and not necessarily an implementation defect at all. The
plausible readings are that `legacy` decode is intentionally unimplemented and
should not be advertised, or that the preflight message is stale and the
restriction no longer reflects reality. Which of those is correct, and whether
the fix is to withdraw the option from help, the manpage and the migration
guide or to implement it, is a design decision we do not make.

A reviewer of this continuation reported no implementation defect meeting their
rules 1-3. We do not read this as contradicting them: under a defect definition
scoped to DSP and correctness it would not qualify. We raise it because P15's
subject is release readiness, where an advertised, documented, always-failing
option is in scope by definition.

## Reproduce

```sh
sox_ng --dsd-layout-loss warn in.dsf -b 32 -e signed-integer out.wav \
  dsdpcm -p legacy -l preserve 352800     # exit 2, stale P05 message
sox_ng --dsd-mode legacy -D in.dsf out.dsf   # exit 0, unrelated path
```
