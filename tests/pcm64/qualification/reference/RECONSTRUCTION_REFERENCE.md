# Phase 08 reconstruction comparison (R3 corrective)

`accepted-reconstruction-sse2.zlib` holds **retained** little-endian FLOAT64
sample words from the accepted R3 `894833f` physical evidence, not from a
new run of the decoder being qualified. The 18 WAV payloads were extracted
from `evidence/phase08/native64-family/*.reconstructed.wav` of the delivered
R3 package. The 19th (`gain_effect`) was independently reproduced on the
same accepted R3 CLI and matched the SHA-256 already frozen in
`accepted-physical-behavior.json` at R3. Every uncompressed case is 1,537
stereo frames (24,592 bytes). Case order is lexicographic.

The compressed fixture SHA-256 is
`dde0a8fb4cf13bd595ba068ad0bc7ca1bab13a8010943ecdd64ef02a50175e21`.
The verifier checks this identity and every uncompressed case against the
previously accepted per-case digest. Do not regenerate either artifact from
the candidate under test or auto-update it after a source change.

An SSE2 result must match the accepted words exactly. For an explicitly
selected *other* FIR kernel, require finite FLOAT64 samples and absolute
error at most `2^-48` PCM units (3.55e-15). This bound allows ordinary
summation-order variation (measured accepted scalar/SIMD differences were
about 1e-16 at worst) but rejects material gain/filter errors. It does not
relax exact WAV/receipt integrity, exact DSD decisions and post-clip inputs,
or same-backend CLI/public-decoder-API parity.

The independent certified-resonator recurrence uses
`accepted-dsd64-constants.h` and `accepted-dsd128-constants.h` only when
Phase 08 explicitly enables the frozen path. The original Phase 06A path
continues to read its historical production headers.
