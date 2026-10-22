# P17 DSD512/DSD1024 qualification: evidence and release decision

**Date:** 2026-10-21. **Input source assertion:** `sox_dsd/main` 2bda0491, from the supplied working-set manifest; this archive does not contain `.git` metadata. **Uploaded archive SHA-256:** `8a0f2ccbbdb3534b101880c5eebc25c5690259347513933ac67a49b8cc6ea377`.

**Decision:** Four experimental high-rate reconstruction profiles and two experimental encoder profiles have six separately hashed candidate evidence records. **All six remain unqualified. No high-rate read, writer, modulation, DoP or physical-device capability was enabled.** The accepted DSD64/128/256 configurations, the first three P10 guard rows, and `LSX_PCMDSD_CERTIFICATE_SHA256` were not changed. This packet is preparation for an explicit subsequent read-only authorization, not that authorization.

The permanent continuum-extrema/alias-proof waiver `docs/dsd/amendments/CONTINUUM_EXTREMA_WAIVER_2026-10-21.md` governs this work. Sampled P17 spectral evidence is retained and the waived proof is not requested again. This packet does not claim that a device or player accepts high-rate files.

## Evidence produced

- `src/pcmdsd_guards.h` now contains five 8-coordinate rows. Row 3 is trained at **22,579,200 Hz**; row 4 at **45,158,400 Hz**. The first three P10 rows and their production certificate remain byte-for-byte numerically unchanged. The two candidate `profiles[]` records in `src/pcmdsd.c` point to their corresponding new state bounds **while retaining `qualified=0` and `certificate_sha256=NULL`**. This prevents a latent unbounded experimental instance without giving it production authority.
- `tests/dsd/p17_qualify_guards.py`: derives, freezes, independently rechecks and holds out clock-specific P10-method state bounds. It checks the source/stimulus/executable SHA-256 for each run, rejects incompatible restarts, and never uses holdout results to change the frozen bounds. A 16x admitted-training-maximum rule is rounded up to a power of two for each coordinate. Records are under `tests/dsd/results/P17_qualification_2026-10-21/guards/`; source of truth is `tests/dsd/reference/p17_guards.json`.
- `tests/dsd/p17_dsf_probe.c`: **private, uninstalled** DSF full-file high-rate decoder, accepting a strict DSD/fmt/data DSF layout, checking lengths and bit order, processing fixed-size bounded channel blocks, and checking chronological **packed versus independently expanded** decoding for every frame with matching PCM bytes. It reports frame counts, per-channel RMS/DC/peak, hashes and optional little-endian 64-bit floating-point PCM export for an independent external audio oracle. This code is not a shipping DSF read handler and cannot turn a capability bit on.
- `tests/dsd/test_p17_dsf_probe.py`: synthetic cross-checks against the independent in-tree DSF construction/parse reference, including mono/stereo/six-channel, both DSF bits-per-sample variants, DSD512/1024, two reconstruction profiles, short and partial-block data, malformed metadata and PCM output length. An additional four-case streaming probe decodes **half-second, multi-megabyte** synthetic DSFs at both rates and both profiles, with partial final blocks, bounded memory and CPU/RSS receipts (`test_p17_long_dsf_stream.py`). Neither fixture success nor this streaming smoke is independent licensed-media qualification.
- `tests/dsd/p17_media_qualification.py`: prepared-host batch runner for full licensed DSF files, with content SHA-256 and resumable per-file/per-profile/per-ISA receipts, raw kernel and output accounting, and a fail-closed summary. No commercial material or independent reference audio was supplied in this upload, so its commercial qualification field is `UNRUN_OR_INCOMPLETE`.
- `tests/dsd/p17_soak_run.py`, `tests/dsd/p17_soak_assess.py`: full-composite private P10 SDM soak wrapper and receipt/guard assessor, with deterministic segment/final-state snapshots, source and binary hashes, nonfinite/overload and all-eight-state checks, packed 28-bit history and output sample counts. Local one-second exercises are explicitly **SMOKE ONLY**, never one-hour qualification.
- `tests/dsd/generate_p17_qualification_certificates.py`: versioned SHA-256 manifests for **four decode and two encode candidates** in `tests/dsd/reference/p17_qualification_certificates.json` and macros in `src/dsd_p17_certificates.h`. Hashes bind source, frozen coefficient/profile definitions, prior sampled/finite oracles, evidence and this release boundary. These are **candidate evidence hashes, NOT release certificates**. They are deliberately not passed to production C profile pointers: both the evidence and its binary hash must be separately evaluated before promotion. `tests/dsd/test_p17_qualification_registry.py` rejects accidental promotion or stale/altered manifests.

### Guard derivation and failure accounting

| Rate | Training inputs | Admitted | Failed/rejected | Frozen 8-coordinate ceiling |
| --- | ---: | ---: | ---: | --- |
| DSD512 | 17 | 17 | 0 | `128,256,2048,16384,131072,524288,4194304,67108864` |
| DSD1024 | 17 | 15 | **2 nonfinite-state failures** | `64,256,2048,16384,131072,524288,4194304,67108864` |

**Critical DSD1024 encoder finding:** Both the positive-DC and negative-DC 1.6-second training tests, driven at the normal `.5` full-scale SDM envelope, fail at approximately **33,108,316 processed native frames**. State magnitude grows to the binary64 limit; the monitor records `nonfinite_states=1`, failure code 3 and a 28-bit population excursion. These are *not ordinary declared overloads* and must not be classified as successful negative tests. The derived DSD1024 guard row correctly describes the **15 admitted inputs only**. It cannot certify the candidate against the excluded DC inputs. Investigate this instability before authorizing a high-rate encoder. Do not inflate the guard row to hide it or silently change the accepted P10 SDM coefficients. The DSD1024 encoder is **BLOCKED** until the recurrence/envelope policy is resolved and independently re-qualified.

The separate frozen holdout covers 27 distinct nontraining cases plus nine source-rate matrix checks **at each clock (72 total)**, including fullscale/low-level tones, DC, deliberate overload, noise and 60-second segments. Its **DSD512 result is PASS** for all 34 ordinary/expected-rejection cases, with two 0-dBFS tests recorded as **separately handled fullscale observations** according to the original P10 policy. Its **DSD1024 result is FAIL**: guarded DC in both polarities trips the state-bound gate, and the deliberate excessive-envelope source trips the state-bound gate rather than the expected interpolation-envelope gate. The latter is a fail-closed rejection, but it is still the wrong failure class for the P10 criterion. Its two 0-dBFS cases are separately recorded; small nominal-0.5 over-envelope counts are not hidden or certified. The aggregate holdout verdict is **FAIL**. These failures cannot be used to retune frozen ceilings. Two additional guarded, three-second DSD512 ±DC stress cases completed with finite state and correct native frame counts; these supplementary nontraining observations are not a sustained qualification. The rate-specific long-soak obligation below remains independent of any passing short case.

## Decision framework for DSD512 *read-only* capability

The provided operator owns **12 licensed commercial NativeDSD DSD512 stereo tracks**, ~23 GB total. Their bytes were not uploaded and no claims about them appear in this packet. No DSD1024 commercial corpus is available. Run `p17_media_qualification.py` on the licensed tracks on the operator's machine, not on an internet-downloaded surrogate.

For `decode.mastering.v1.dsd512` and `decode.wideband.v1.dsd512`, a later authority may consider enabling the **DSF READ + RECONSTRUCT** path, with **no WRITE, MODULATE, DoP or DFF assumption**, only when all of these independent gates pass:

1. **Media identity / file acceptance.** All 12 distinct files are intact: cryptographic source SHA-256, file bytes, DSF header and data chunk lengths, claimed sampling clock **22,579,200 Hz**, channel count **2**, bit ordering and native sample count are recorded. Decode each **entire** file with both profiles, not excerpts; log errors and first mismatch if any. Confirm output PCM frame counts are the specified exact rational conversion of native frames. No dropped, repeated or invented tail frames, no read outside the declared payload, no nonfinite PCM. A source with a malformed header must fail explicitly.
2. **Independent reference comparison.** Independently parse a source's DSD chronology; compare channel assignments/polarity and exact start/end native-bit counts. For PCM, obtain an external decoder or separate independent algorithm validated for DSD512 at the actual clock; compare aligned samples using the **same intended reconstruction response and output PCM rate**, allowing rigorously justified filter/latency differences rather than imposing an arbitrary cross-filter bit-exactness requirement. Record alignment, gain/DC difference, in-band error spectrum, RMS/peak discrepancy, boundary continuity, transient behavior and any unexpected channel mismatch. An external software path must itself be verified as high-rate-capable. The probe's own packed-vs-expanded equality does **not** qualify as this independent audio oracle.
3. **DSP and performance.** Both profiles pass the source-bound P17 finite/reference and sampled spectral evidence, independently cross-checked on relevant PCM rates. Capture full-track wall time, process CPU seconds, maximum RSS, throughput in native frames/s and real-time factor, output format and per-channel RMS/DC/sample peak. The private probe deliberately decodes every source twice (packed and expanded); its measured throughput and real-time factor reflect **dual-pipeline verification overhead**, not shipping single-decoder performance. Capture a separate like-for-like single-decoder baseline for any release performance conclusion. Repeat representative files and available ISA tiers to check stable results within an explicitly documented scalar/SIMD numerical tolerance. Preserve failures and retry conditions rather than replacing negative receipts.
4. **Stable public integration.** In the later **separately authorized** release change, enable only the appropriate DSD512 READ and RECONSTRUCT capabilities for the validated DSF handler. Test default CLI, direct library read API, probe-only private code, malformed-file exits, PCM output lengths, mono/multichannel boundaries where claimed, unchanged DSD64/128/256 behavior, and continued refusal of DSD512/1024 writers, DFF/DoP and DSD1024 reads where not independently qualified. Avoid permitting a generic rate bit to bypass the specific endpoint gate. Retain the P18 no-silent-down-rate and no-hidden-fallback contract.

A read-only DSF capability can be authorized before any DSD512 encoder qualification; writing, loopback generation and physical player compatibility must **not** be inferred from read-side success. A DSD1024 read profile requires its **own** independent source corpus or fully independent high-rate known-answer material before enabling that native rate; generating it with this unqualified encoder would be a circular oracle.

### Licensed-media operator procedure

Run from the source tree after `autoreconf -fi`, `./configure` and `make -j6`, then `make -C test dsd_test_p17_dsf`. For two profiles over every licensed track with scalar and any **actually supported** additional tiers:

```sh
python3 tests/dsd/p17_media_qualification.py \
  --media-root /secure/absolute/path/to/licensed-dsf \
  --expected-dsd512-tracks 12 --tiers scalar \
  --require-media
```

Use a separate `--results` destination if retaining this packet's explicit UNRUN record. Add `,avx2` or `,avx512` only when the host can actually run it. To export independent-comparison input for one source, invoke the *private* `test/dsd_test_p17_dsf /path/file.dsf mastering 176400 scalar full /tmp/track-mastering.f64le`, then compare against separately produced and correctly aligned PCM. The float export is interleaved little-endian binary64 without a WAV header. The source data need not enter this handoff archive; source hashes and redacted receipts can.

## DSD512 and DSD1024 *encode* criteria (no authorization here)

All of the following remain separate from a successful guard freeze: (a) all nonoverload training/holdout inputs remain finite at both rates, including DC and transitions; (b) exact native frame accounting and a complete source-rate / gain-envelope matrix, with deliberate overload reliably rejected and the candidate guarding all eight state coordinates; (c) one-hour **continuous, unreset** input programs for each rate and original-v1/nominal-v2 stress mode on a prepared host, including both clock-specific bounds and 28-bit window statistics; (d) selected real music/technical reference signals and independent reconstruction-quality assessment; (e) numerical and physical performance/thermal/CPU behavior across actually supported SIMD tiers; and (f) separate file-writer/transport interop before writing native high-rate DSF/DFF or DoP is authorized. The guard maximum is a fail-closed safety ceiling, not a standalone proof of long-term SDM stability.

Run these **four** separate native-clocks/mode pairs (each one hour):

```sh
for rate in 22579200 45158400; do
  for mode in original-v1 nominal-v2; do
    prefix="/durable/soaks/p17-${rate}-${mode}"
    python3 tests/dsd/p17_soak_run.py --rate "$rate" --mode "$mode" \
      --seconds 3600 --segment-seconds 60 --prefix "$prefix"
    python3 tests/dsd/p17_soak_assess.py --rate "$rate" \
      --seconds 3600 --prefix "$prefix" \
      --results "${prefix}-assessment.json" --require-sustained
  done
done
```

The operator must capture CPU model/stepping and microcode, ISA/features and actual dispatch, OS/kernel, executable and source SHA-256, relevant compiler flags, cpuset/affinity, CPU frequency/scaling governor and power/thermal state, virtualized versus physical host, interfering load, elapsed and CPU seconds, RSS, input/output native frame counts, all eight state maxima vs their bounds, failure/overload/nonfinite counts, 28-bit population min/max and out-of-range fraction, longest runs, final bits hash, each continuity snapshot and final-state hash. Run with a warm CPU on a prepared, repeatable host; do not label a container's short smoke as the sustained result. Interrupted runs replay from input frame zero and cross-check existing state snapshots; a mismatch is a failure, not a reason to overwrite the old evidence.

## Existing release boundary and exclusions

The low-rate P10 certificate digest remains `df25a2a11855e8a380cd756cf38769701103338faf36b46271aa3df22bc5157e`. The P18 high-rate `dsd_rates` table must remain 12/12 disabled until new release authority and separate per-operation testing. The original working set intentionally omitted 49,662 files and 1,351 `.npz` files; the historical P15 reviewers cannot be made complete by rewriting receipts or changing the P00 index. Those historical gaps are **not** repaired or relabeled by this qualification packet.

For replay and checkpoint recovery, see `P17_QUALIFICATION_RESUME_2026-10-21.md` and the source/receipt manifests in this archive. **Candidates with a PASS development test but missing independent media, reference, stability or soak evidence stay unqualified.**
