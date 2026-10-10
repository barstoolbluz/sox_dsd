# Frozen analysis-v1 (P09)

This reference is not built from `src/dsd_coeffs.h`, `src/rate.c`, or the SoX
decoder. `generate.py --create` synthesizes one symmetric binary64 Kaiser FIR
at each native clock in 60-decimal-digit `mpmath`, then refuses to modify an
existing freeze. The coefficients are little-endian IEEE-754 binary64 bytes,
including the normalized DC scale. All three exact byte hashes are in
`manifest.json` and the sealed inventory is `SHA256SUMS.txt`.

The immutable method is in `analyze.py`: zero-extended linear FFT overlap-add
and factor-32/64/128 integer decimation to 88,200 Hz; integral group-delay
removal; trimming at least 250 ms from *each* boundary and retaining a full
second. For a coherent 997/1000 Hz tone in that aligned second, the window is
rectangular; otherwise the fixed four-term periodic Blackman-Harris window is
used. Frequency-domain powers are corrected for `sum(w**2)` and expressed in
normalized PCM power (`0 dBFS` = sine peak 1 = power 0.5). Least-squares DC,
sine and cosine fit removes only the fundamental and DC before computing
20 Hz–20 kHz THD+N. SNR, gain and phase are separate quantities.

`verify.py` tests response envelope, bitstream output counts and selected
direct-convolution samples for all three rates, coherent known distortion,
known seeded noncoherent noise and fit, plus independently implemented SciPy
firwin/direct-polyphase corroboration. These tests must pass **before** any
candidate dB values may be compared.

`measure_candidates.py` invokes the public P09 test probe and publishes only
unqualified analytic-input diagnostics. Its synthetic tones bypass P10's
interpolation, prefilter and envelope tests; they cannot qualify a mastering
profile. P10 must run the much longer independent production validation and
soaks defined in section 10.5 of `DSD_DESIGN.md`.

To inspect the freeze: `sha256sum -c SHA256SUMS.txt` from this directory.
Changes to any frozen coefficients, constants or scoring procedure require a
*new analysis version*, rather than rewriting the P09 scoring reference.
