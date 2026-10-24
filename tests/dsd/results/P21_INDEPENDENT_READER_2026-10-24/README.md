# Independent-reader and audio-reference gate, 2026-10-24

P17 declared this gate and never implemented it. Its collector,
`tests/dsd/p17_media_qualification.py`, returned the literal string `UNRUN`
for `independent_reader_and_audio_reference_gate` and an all-`False`
`decoder_profile_qualified` map. A gate that cannot pass is
indistinguishable from a gate that was never written, and when P21 opened
the high-rate read rows on operator declaration, this was the one capability
resting on evidence we had ourselves labelled insufficient.

`tests/dsd/p21_independent_reader.py` implements it. The P17 collector now
derives its verdict from this evidence and still reports `UNRUN` when the
evidence is absent.

## What it does

For each licensed DSD512 track, decode a fixed interval twice: once with
`src/sox`, once with an independently written DSD reader used as a second
opinion. Compare in the audio band.

Three decode paths are covered, including the one users get by default:

    --dsd-decode mastering    176400 Hz    decode.mastering.v1
    --dsd-decode wideband     705600 Hz    decode.wideband.v1
    (no flag, CLI default)    176400 Hz    decode.mastering.v2

## What it establishes, and what it does not

Agreement in the audio band validates container parsing, block and channel
interleave, bit order, sample alignment and gross gain. Those are the things
a reader can get wrong while still producing plausible-sounding output.

It does **not** establish filter equivalence. The reference reconstructs DSD
to PCM with its own filter, so out-of-band behaviour differs by design and
bit-exactness is impossible. It does not establish device interoperability.
And it cannot cover DSD1024 read at all: no independent DSD1024 media
exists, so `decode.*.dsd1024` stays unqualified no matter how this runs.

## Thresholds, and why these

| gate | threshold | measured on good input |
|---|---|---|
| in-band Pearson r | >= 0.999 | 0.99997 |
| level delta | <= 0.1 dB | 0.00003 dB |
| channel identity | same-channel r must exceed cross-channel r | 0.99997 vs 0.687 |
| negative control | a different track must correlate < 0.5 | 0.02 |

Every threshold sits orders of magnitude from the measured value, and each
has a demonstrated failure mode. The gate was mutation-tested by wrapping
`sox` in a shim that corrupts its output, confirming it fails for the right
reason rather than failing generically:

    channel swap        r falls to 0.688, and same-vs-cross inverts
    +0.42 dB gain       level delta trips alone; correlation stays clean
    64-sample shift     r falls to 0.56 / 0.50; level unaffected
    noise substitution  every threshold trips

The gain case matters most: it shows the gate discriminates between kinds of
fault rather than just detecting "different".

## Receipts

`cases/<media-sha-prefix>-<profile-id>.json` per track and profile;
`independent-reader-evidence.json` for the verdict. Licensed media appears
only as a SHA-256. No PCM is retained; it is written to scratch and deleted.

## Reproducing

Requires numpy and scipy. The media is private and not in the repository.

    python3 tests/dsd/p21_independent_reader.py \
      --media-root <private DSF directory> --sox src/sox \
      --results <scratch dir> --seconds 10 --start-seconds 5
