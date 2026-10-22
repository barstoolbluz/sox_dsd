# P20 DSD512 candidate correction — engineering handoff

**Status (October 22, 2026): EXPERIMENTAL CANDIDATE ACCEPTED FOR NATIVE QUALIFICATION. NOT AUTHORIZED FOR PRODUCTION.**

## 1. Decision and why

The original `encode.mastering.v1.dsd512` remains a valid *historical numerical experiment*, but **does not satisfy the sustained nominal bitstream gate**. The supplied operator's 3,600-second DSD512 receipt records 81,285,120,000 processed native frames, 6–22 one-bits in moving 28-bit windows, a longest constant-bit run of 10, and zero nonfinite states or monitor overloads. The required sustained-population interval is 7–22. The `6` is real in the saved report and is not an interpolation-envelope or numeric-state failure. The source archive includes the operator's assessment and digests for 61 state snapshots; some intermediate raw snapshots were omitted from the working set, so those raw digests cannot all be independently recomputed here. The overload records reach ~0.500287 and reject at the input-envelope gate as intended.

I implemented a **separately selected** `encode.mastering.v2.dsd512` (seventh-order CLANS-7 recurrence, independent frozen DSD512 training guards). It is a candidate, not an upgrade to the original v1 and not a production profile. The same CLANS-7 binary64 coefficients have an existing P19 DSD1024 precedent; changing the native sample clock is still an independently tested proposition, not an automatic qualification. The old eighth-order DSD512 v1 definition, its coefficient words, its frozen bounds, and the public default lookup are unchanged.

**Conservative handoff:** proceed to a prepared-host 3,600-second DSD512-v2 nominal soak and independent audio-quality assessment. **Do not turn on a writer or reader here.** P18's 12 high-rate format and DoP capabilities remain disabled. The user's separate 12/12 whole-file DSD512 commercial decode results are functional evidence for a future *read-only* phase, independent of this encoder change, and were not reproduced here.

## 2. Changes and invariants

- `src/sdm_p20_candidates.h` — separate `lsx_sdm_p20_dsd512` 7th-order definition at exactly 22,579,200 Hz. The original P17 and P19 definitions are untouched.
- `src/sdm.c` — explicit opt-in identity lookup for the new candidate, after the existing v1 DSD512 entry. Normal rate lookup still selects the unchanged v1 by default.
- `src/pcmdsd_p20_guards.h` — new, clock-specific, frozen eight-coordinate bounds from **training alone**: `[32, 64, 512, 4096, 65536, 1048576, 67108864, 16]`. Frozen derivation: `2**ceil(log2(16*max(1,training_max)))`; holdout not used for tuning.
- `src/pcmdsd.c` — candidate row with `qualified=0`, `certificate_sha256=NULL`, no public writer capability. Original P17/P19 rows unchanged.
- `tests/dsd/test_p10.c` — new identity/blocked-routing tests and two private candidate-soak modes. In the soak runner, `original-v1` **names the original stress-program waveform**, not the encoder: **both P20 soak modes always use the DSD512 v2 candidate**.
- `tests/dsd/p20_qualify_dsd512.py`, `test_p20_cross_isa.py`, `test_p20_bitstream_oracle.py`, `p20_audio_compare.py`, `p20_soak_{run,assess}.py`, and `generate_p20_candidate_certificate.py` — bounded test/receipt and evidence-binding programs. The supplied P17 training/holdout definitions are reused without modification.
- `tests/dsd/reference/p20_dsd512_v2_guard.json` and `p20_dsd512_v2_certificate.json` — independent, **unqualified** integrity records. The only refreshed preexisting certificate is `tests/dsd/reference/p19_dsd1024_v2_certificate.json`, regenerated because its source digests of `sdm.c`, `pcmdsd.c` and `test_p10.c` correctly became stale. Its original bytes are preserved at `tests/dsd/results/P20_DSD512_CORRECTION/preimage/p19_dsd1024_v2_certificate.json`. The original P17 registry is unchanged and archived similarly.

The known continuum-extrema waiver is respected. No P00 index entry, P10/P17 legacy guard row, historical P17 source, P18 capability switch, or production decoder/writer contract is altered.

## 3. Independently reproduced results

| Test | Result | Interpretation |
|---|---|---|
| `autoreconf`, `configure`, `make -j4`, and `make check` | **PASS** | Built native x86_64; ordinary SoX suite passes, with its pre-existing reported `VOID` skips. |
| P10 private `--unit` | **PASS, 105,489 checks** | Includes opt-in DSD512-v2 tests and disabled public entrypoint. |
| Training | **17/17** | Training only; longest tested training program is 60 seconds. No nonfinite state, input overrun, or 4–24 population excursion. |
| Frozen training guards | **PASS**, source-bound | Holdout cannot update guard bounds. The training-runner exact preimage and original training binary are archived. |
| Independent guarded holdout | **36/36**, 33 accepted, two observed full scale, one correctly rejected overload | No numerical faults or 4–24 excursions. Near-full-scale and negative-DC cases may reach population **6** and are not accepted as sustained nominal-program certifications. |
| Scalar, SSE2, AVX1, AVX2, AVX-512 | **25/25** | Five P17 holdout inputs per kernel. SIMD bits are not falsely required to equal scalar bits. Tested on this x86 host; not a portability certification. |
| Independent unpacked-bit checker | **4/4** | Computed 28-bit sliding counts and longest runs from emitted bits; matches C monitor. A negative-DC input has minimum 6, explicitly reported. |
| Corrected DSD512-v2 nominal smoke | **PASS_SHORT_SMOKE_ONLY** | **300 seconds, 6,773,760,000** native frames; population **8–20**, longest run **5**, zero faults, peak **0.350135**, maximum frozen-guard utilization **5.91%**. Ten segment snapshots plus a final state were checked against their SHA-256 receipts. |
| Corrected DSD512-v2 original-pattern smoke | **PASS_SHORT_SMOKE_ONLY** | One second of the legacy stress waveform, using the new candidate. |
| Sustained gate enforcement | **PASS fail-closed test** | The 300-second data is rejected by the assessor with `--require-sustained`; it cannot be mislabeled as a one-hour pass. |
| P17 unit, encoding and matrix | **PASS** | 32,859 unit checks, 230 candidate checks, 8,640 pairs/406,080 matrix checks. |
| P18 native and CLI | **PASS** | 398 native checks; 106 CLI checks, 198 independent reference fixtures, 36 DoP vectors; high-rate calls explicitly refused. |
| P19 certificate regeneration and `--check` | **PASS** | Previously bound P19 candidate evidence retained, no qualifications promoted. |
| P20 candidate certificate `--check` | **PASS** | Hashes frozen training, holdout, binary snapshots, independent ISA/oracle/audio/smoke evidence and original immutable source. This is not a signed certificate or enablement. |

The reconstruction comparison is an **open quality concern**. On a 997-Hz, approximately −6-dBFS synthetic input, independently decimating both candidate DSD512 bitstreams with the in-tree mastering/halfband FIR coefficients and fitting out the fundamental/DC gave:

- v1 (8th order): **−200.14 dBFS RMS residual**.
- v2 (7th order): **−163.04 dBFS RMS residual**.
- v2 residual penalty: **+37.10 dB** under this diagnostic.

No output clipping was detected. These residuals include reconstruction-filter error as well as shaped-noise/harmonic content and are not a listening test, spectral compliance test or independent reference-audio adjudication. A diagnostic CLANS-8 alternative with superior synthetic residual was discarded: it produced nonfinite numeric runaway on a DC fixture. It is **not** in the shipping candidate. This tradeoff must be adjudicated for high-end DSD512 before any release decision; do not silently conflate a passing population gate with superior audio.

**Evidence location:** `tests/dsd/results/P20_DSD512_CORRECTION/`. Raw case receipts, the exact training runner preimage, training and guarded executables, the 300-second segment states and execution records, ISA/oracle/audio JSON, and regression logs are included. `tests/dsd/reference/p20_dsd512_v2_certificate.json` binds the source and evidence to SHA-256 digests. Neither this file nor the previous P19 operator receipts is a signature. Provenance of the supplied working-set name `699e4363` cannot be authenticated from the tarball alone because it contains no upstream `.git` objects; an import commit is synthetic.

## 4. Qualification still required

1. On a prepared native host, build from the **same source revision** and record CPU model, ISA, compiler/toolchain, flags, governor, core affinity, thermals, load and system configuration. Run the *nominal-v2* 3,600-second P20 soak (at least 81,285,120,000 native frames), and independently check its 61 timed state snapshots and final state. Check the **7–22** input-program 28-bit population gate, no nonfinite/overload, guard bounds, frame accounting and the input-envelope gate. The 300-second smoke reported here is **not sufficient**. Do not weaken the gate because the new candidate passes short tests.
2. Assess encoder audio independently, including spectral measurements, shaped ultrasonic noise, reference listening/device compatibility as appropriate, and representative DSD512 content. Reconcile or reject the measured **37.10 dB synthetic residual penalty** before claiming a superior encoder. The P17 4–24 training/holdout admissibility gate and the sustained 7–22 input gate are distinct; a negative-DC or near-full-scale adversarial test with minimum population 6 is not evidence of a sustained *nominal* input-program failure.
3. Future independent high-rate reader or writer enablement requires its own authority and qualifications. The supplied commercial DSD512 read-only results are evidence for that separate discussion, not a side effect of this work. The waived continuum-extrema obligation is outside this phase and must not be reopened.

### Reproduction commands

From the source root, after installing project prerequisites:

```sh
autoreconf -fi
./configure --disable-shared
make -j4
make -C test dsd_test_p10 dsd_test_p17 dsd_test_p18
./test/dsd_test_p10 --unit
./test/dsd_test_p17 unit
./test/dsd_test_p17 encode
./test/dsd_test_p17 matrix
./test/dsd_test_p18
python3 tests/dsd/test_p18.py --results /tmp/p20-p18-replay
make check
python3 tests/dsd/generate_p19_candidate_certificate.py --check
python3 tests/dsd/generate_p20_candidate_certificate.py --check
```

Certificate verification works with the archived evidence binaries even before rebuilding; fresh test runs are separate experiments and must write to new receipt destinations.

**Prepared-host sustained validation (not completed here):**

```sh
python3 tests/dsd/p20_soak_run.py --mode nominal-v2 --seconds 3600 \
  --segment-seconds 60 --unit ./test/dsd_test_p10 \
  --prefix /ABSOLUTE/RESULTS/p20-dsd512-v2-nominal
python3 tests/dsd/p20_soak_assess.py --rate 22579200 --seconds 3600 \
  --unit ./test/dsd_test_p10 --prefix /ABSOLUTE/RESULTS/p20-dsd512-v2-nominal \
  --results /ABSOLUTE/RESULTS/p20-dsd512-v2-nominal-assessment.json --require-sustained
```

Use a *new prefix* for every materially different experiment. The runner refuses to reuse a failed or incompatible receipt. The original-pattern mode (`--mode original-v1`) also runs the **new v2 candidate**; its stress program is expected to hit the existing interpolation-envelope rejection and must not be reclassified as an SDM state failure. Keep the complete original evidence off-tree with the operator for independent audit.

## 5. Scope control and integrity

- The original P17 registry remains byte-for-byte unchanged; its historical generator cannot be re-run from the supplied reduced working set because **49,964 earlier inputs were expressly omitted**. No P15 historical validation claim or P17 certificate regeneration is invented.
- The P18 capability test suite confirms all high-rate routes remain disabled, including format read/write and DoP.
- No production capability was enabled. This delivery is a qualified *work product* for **further candidate testing**, not a qualified encoder or signed release.
- Use the companion `P20_DSD512_V2_RESUME_2026-10-22.md` and `P20_CHECKPOINT.json` to continue after any interruption. The archive-wide `P20_BUNDLE_SHA256SUMS.txt` and root `P20_CONTENTS.md` document integrity and contents.
