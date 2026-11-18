# Phase 08 audited harness working copy (P08-D03)

This file is the **explicit working-copy overlay** over the immutable
`Switched_Resonator_Qualification_Harness_AuditFixed_v2_Full.tar.gz`.
The immutable archive SHA-256 is
`7d64bc18a7839786636c4a45365dd6d3e7ca42f0392b9c56f491bb2897954414`.
The working-copy builder verifies the archive before extraction, checks its
own `SHA256SUMS`, runs the original harness's complete unit/integration tests,
and verifies **both** preserved historical roots:
`qualification/` and `qualification-new/`. Their original 1.1.0 binaries,
trace identities and calibrated results are not modified or repurposed.

For historical-only verification:

```
python3 source/tests/pcm64/qualification/audited_workcopy.py \
  --immutable-archive inputs/Switched_Resonator_Qualification_Harness_AuditFixed_v2_Full.tar.gz \
  --workdir /tmp/p08-harness-historical --historical-only
```

For the **new** 18-case native64 family, use a new workdir, along with the
actual current receipt root and all three exact executable witnesses:

```
python3 source/tests/pcm64/qualification/audited_workcopy.py \
  --immutable-archive inputs/Switched_Resonator_Qualification_Harness_AuditFixed_v2_Full.tar.gz \
  --workdir /tmp/p08-harness-native \
  --native-results evidence/phase08/qualification --source source \
  --sox tested-binaries/qualification-sox \
  --probe tested-binaries/qualification-encode-probe \
  --oracle tested-binaries/qualification-decode-api-oracle
```

The current check executes the *real* Phase 08 `qualification/verify.py`
(including mutation controls), demands receipt schema `/2` and exactly
matching Git revision, and refuses to use either historical results root as
current evidence. See `WORKING_COPY_VERIFICATION.json` and the captured full
logs in the new workdir. A historical-only PASS does **not** qualify native64.

No historical results or calibration are regenerated or relabeled.
