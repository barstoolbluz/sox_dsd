# P10 hotfix: read/repack placement, and the external PCM corpus arm

Date: 2026-10-10. Work applies to the source snapshot in
`P10_HOTFIX_CHECKPOINT.md`. This addendum supersedes older P10 handoff status
claims only where the later ratification evidence explicitly changed a gate.
The P10 SOW, approved design and frozen ratification criterion are unchanged.

## Outcomes and boundaries

P10 **remains INCOMPLETE**, promotion **BLOCKED**; all mastering profiles
remain unqualified. Representative hardware/ISA one-hour evidence was
adjudicated **PASS** in the preceding ratification. The independent real-world
corpus remains **PARTIAL** until the external PCM arm is executed, admitted,
checked and independently adjudicated. The historical read/repack throughput
record **FAILS** on the prepared Threadripper 7970X host: +6.81% at 0.41%
noise, with the entire bootstrap interval beyond the 5% limit. A new prepared-
host qualification of this hotfix is still required; do not promote on the
basis of a developer-host timing observation.

The historical throughput A/B test establishes a causal dependency on the
change to `src/pcmdsd.c`, not its microarchitectural explanation. Both the
old and simplified diagnostic retain failure semantics: the number shown is
only the **minimum explicit attenuation lower bound at the first overloaded
sample**, not enough attenuation to admit the remaining frames. The change
removes the 192-byte stack buffer and `snprintf`/`strcpy` from the diagnostic
function, without removing its warning or changing the public ABI. The linked
DFF reader code moved by 256 bytes between the archive diagnostic and this
simplification. The code itself is unchanged; that displacement establishes
placement sensitivity, not the reason for the original 6.81% speed change.

The confined reader stabilization adds an x86-64 GCC/Clang-only 4096-byte function
alignment hint to `dff_read_fragment` and `dff_read`. This pins their page
offsets, including instruction-cache set position, regardless of movement in
preceding linked objects. On other architectures and compilers the original implementation is
unchanged. It adds no branches, sample conversion, buffer copying, or state.
A passing hardware throughput comparison, not the comment or the alignment
hint, determines whether this mitigation actually solves the release gate.

## PCM_AUDIO measurement contract

New driver: `tests/dsd/corpus_pcm.py`.

1. Supply a JSON list pairing exact inventory release names with the host's
   first-track paths; every release must match the inventory's STREAMINFO
   rate, channels, bit depth and MD5. The inventory does not contain audio
   paths, and the source tree ships no copyrighted recordings.
2. Copy each remote/sshfs FLAC once to a local temporary directory, hashing
   the source as bytes arrive. Do not modify the original. Run `flac -t`
   against the *local* copy and losslessly decode just a sample-exact excerpt
   to 24-bit stereo WAVE with integer `--skip`/`--until` positions. Check and
   SHA-256 the actual PCM payload and the exact decoded excerpt container.
   The five 176400-Hz read-only sources are handled identically: no in-place
   decode, metadata rewrite, rename or modification. Existing STREAMINFO
   values of all zeroes indicate absent source MD5: FLAC frame CRCs and
   source/excerpt hashes are still recorded, but an MD5 verification of that
   source cannot be claimed.
3. Execute the uninstalled `test/sox_p10_candidate` composite, with `-D`, one
   explicit `pcmdsd` after optional **explicitly requested** gain, ordinary
   PCM half reference, and every requested native rate. No FLAC support is
   enabled in SoX and no rate/profile/guard/analysis configuration changes.
   Failure is nonzero; no limiter, normalization, or silent gain rescue is
   allowed. The optional negative gain ladder records *every* attempt, unity
   rejection, diagnostic and eventual admitting value.
4. Parse the admitted DSF by bounded batches of interleaved channel blocks.
   Carry the prior 27 valid bits between batches and count every complete
   **sliding** 28-bit window per channel, including crossing block boundaries.
   Check the native frame count and 28-bit count exactly. DSD64 admission
   requires each 28-bit window to contain 4..24 ones; at DSD128 and DSD256,
   population is **diagnostic only**. Source PCM levels are compared with
   output reconstructed using **`dsdpcm -l sacd`** at the profile working rate,
   *not* preserve. Accept |RMS delta| <=0.25 dB and |peak delta| <=0.5 dB.
   This measures levels and bit-window populations; it makes no claim about
   unmeasured spectral values or state extrema.
5. Write `pcm-corpus.json` atomically as sources finish. `--resume` reuses a
   completed row only under the same configuration/executable and hashed source-
   mapping identities and unchanged source size/mtime; it does not independently rehash a skipped
   source. Completed input passes also export `pcm-sources.json`,
   `pcm-unity.json`, and `pcm-ladder.json` in the **existing ratification
   checker schema**, without overwriting any `DSD_NATIVE` records. Source
   paths, scratch paths and executable paths do not enter these receipts.

The driver does not prove artistic provenance: it checks an operator-supplied
commercial-release inventory against source bytes and records. Independent
corpus qualification still calls for auditor review of source provenance.
All 19 listed releases are available only on the operator's host. They cover
both 44.1-kHz and 48-kHz rate families, but the 176.4-kHz candidate group
shares a single artist/catalogue lineage, which must be recorded in the corpus
adjudication. Coverage requires >=60 seconds, two independent recordings per
native rate and two genres; rejected unity passes may be retried only with
explicit recorded gain.

### Run on the material host

Create a local `pcm-paths.json` (outside the source tree), containing:

```json
[
  {
    "release": "1976. Joachim Kuhn - Hip Elegy (2014) [24-88.2]",
    "path": "/actual/host/path/to/first-track.flac",
    "track": "First track"
  }
]
```

The example is a *mapping format*, not a completed corpus: add the actual
paths of enough independent releases before executing. From the source root:

```sh
python3 tests/dsd/dsd_windows.py --self-check tests/dsd/fixtures/stereo_96.dsf
python3 tests/dsd/corpus_pcm.py \
  --sox src/sox_ng --candidate test/sox_p10_candidate \
  --sources /local/pcm-paths.json \
  --results tests/dsd/results/P10_realworld_corpus_2026-10-10 \
  --scratch /local/temp-storage \
  --seconds 60 --offset 30 --gain-ladder=-0.1,-0.25,-0.5,-1,-2,-3
python3 tests/dsd/qualify_p10_ratification.py \
  --output /local/new-qualification/qualification.json
```

The source map and work directory must be on the operator's host. Do not
point `--scratch` into the source mount. Recording all native rates is the
full qualification path; restricting `--native-hz` runs only a diagnostic.
Requalify against the separately retained **8f52d842** baseline built on
that SAME host with the original `-O2 -g` flags. The baseline binary is not
part of this source archive. On the representative Threadripper host (CPU 8
was used by the recorded gate), use:

```sh
sudo tests/dsd/benchprep.sh prepare --cpu 8
tests/dsd/benchprep.sh noise --cpu 8 --runs 9
python3 tests/dsd/bench_read_p02.py \
  --baseline-sox /local/baseline-8f52d842/sox_ng \
  --sox src/sox_ng --results /local/P10-hotfix-throughput \
  --pairs 40 --warmups 3 --cpu 8 --operation all \
  --null-extra-arg=--dsd-layout-loss --null-extra-arg=warn \
  --require-comparable dff-6ch-repack-small \
  --require-comparable dsf-6ch-repack-small
sudo tests/dsd/benchprep.sh restore
```

Ensure the results path and benchmark working directory are local. Preserve
both output hashes for every comparable workload. The gate admits only runs
with noise **under 2%**; require the **entire** bootstrap interval to lie at
or below +5% for a pass. An interval straddling +5% is **inconclusive**,
not passing. Independently review all other workloads and revert host tuning
via `restore` even if the benchmark exits unsuccessfully. Never compare
against the ratified regression as a substitute for the gate's approved
baseline; a new prepared-host verdict is currently **UNRUN**.

## Source changes, testing and deviation record

Changed: `src/pcmdsd.c` (diagnostic path), `src/dsdiff.c` (function alignment),
`tests/dsd/dsd_windows.py` (bounded exact DSF window analysis), `Makefile.am`,
`docs/dsd/handoffs/P10.md`, and the P00 delivery hash index. Added:
`tests/dsd/corpus_pcm.py`, `tests/dsd/test_p10_pcm.py`, this handoff,
`P10_HOTFIX_CHECKPOINT.md`, and a new hotfix validation receipt. There are
no coefficient, guard, frozen analysis, profile activation or production
routing changes. Previously recorded evidence stays byte-identical.

Development-host tests and exact command/exit record are maintained in the
new `tests/dsd/results/P10_hotfix_validation_2026-10-10/` receipt. The
compiled-host profile is virtual AMD EPYC 9V74, not the Threadripper 7970X
used for the 5% gate. Development A/B timings with measurement noise >=2%
are **INCONCLUSIVE** regardless of the median; output equivalence is checked.
External PCM/FLAC recordings and a prepared representative host were not
present in this sandbox; their mandatory gate outcomes are **UNRUN**, not
PASS. A synthetic end-to-end exercise proves the new driver is runnable but
cannot satisfy the independent-external-recordings criterion.

There is no P11 promotion or authorization to change mastering profile flags.
Next work: run the external PCM arm, rerun the paired throughput gate on the
prepared host, independently adjudicate both, and only then reconsider P10
release qualification.
