"""P00 measurement definitions. Not a released DSD reconstruction reference.

The FIR/decimator and certified analysis-v1 coefficients are deliberately not
present until their separately gated implementation and verification phase.
This file establishes unambiguous units and independent PCM mathematical tests.
"""
from __future__ import annotations

import math

# Exact four-term Blackman-Harris constants and periodic-window convention.
BH4 = (0.35875, 0.48829, 0.14128, 0.01168)


def band_dbfs(power: float) -> float:
    """0 dBFS is a sine of peak amplitude 1, power 0.5."""
    if power < 0 or not math.isfinite(power):
        raise ValueError('invalid normalized power')
    return 10 * math.log10(power / 0.5) if power else -math.inf


def snr_db(signal_power: float, noise_power: float) -> float:
    if signal_power <= 0 or noise_power < 0 or not all(map(math.isfinite, (signal_power, noise_power))):
        raise ValueError('invalid powers')
    return 10 * math.log10(signal_power / noise_power) if noise_power else math.inf


def blackman_harris4(length: int):
    """Periodized four-term BH; return weights and noise equivalent bandwidth."""
    if length < 2:
        raise ValueError('window length must be >=2')
    import numpy as np
    t = 2 * np.pi * np.arange(length, dtype=np.float64) / length
    a0, a1, a2, a3 = BH4
    w = a0 - a1 * np.cos(t) + a2 * np.cos(2 * t) - a3 * np.cos(3 * t)
    enbw_bins = length * float(np.dot(w, w)) / float(np.sum(w) ** 2)
    return w, enbw_bins


def tone_fit(samples, sample_rate: float, fundamental_hz: float):
    """DC + sine + cosine least-squares fit at a known frequency.

    Returns gain, phase (sin-reference) and residual, without windowing.
    Residual includes harmonics and noise; it is NOT THD-only or noise-only.
    """
    import numpy as np
    x = np.asarray(samples, dtype=np.float64)
    if x.ndim != 1 or x.size < 16 or not np.all(np.isfinite(x)):
        raise ValueError('need >=16 finite samples')
    if not 0 < fundamental_hz < sample_rate / 2:
        raise ValueError('invalid fitted frequency')
    theta = (2 * np.pi * fundamental_hz / sample_rate) * np.arange(len(x), dtype=np.float64)
    basis = np.column_stack((np.ones(len(x)), np.sin(theta), np.cos(theta)))
    dc, a, b = np.linalg.lstsq(basis, x, rcond=None)[0]
    residual = x - basis @ np.array([dc, a, b])
    amplitude = math.hypot(float(a), float(b))
    return dict(dc=float(dc), peak_amplitude=amplitude,
                gain_dbfs=20 * math.log10(amplitude) if amplitude else -math.inf,
                phase_rad=math.atan2(float(b), float(a)),
                fitted_power=amplitude ** 2 / 2, residual=residual)


def baseband_residual_power(residual, sample_rate: float, low_hz=20.0, high_hz=20000.0,
                            window='blackman-harris-4'):
    """Integrated one-sided residual power, with window-energy normalization.

    A rectangular window is available only by explicit request for a coherent
    segment. BH4 is the noncoherent default. Fitted fundamental and DC should
    be removed before calling this; no assumptions about their precision.
    """
    import numpy as np
    x = np.asarray(residual, dtype=np.float64)
    if x.ndim != 1 or x.size < 16 or not np.all(np.isfinite(x)):
        raise ValueError('need >=16 finite samples')
    if not (0 <= low_hz < high_hz <= sample_rate / 2):
        raise ValueError('invalid band')
    if window == 'blackman-harris-4':
        w, enbw = blackman_harris4(len(x))
    elif window == 'rectangular':
        w, enbw = np.ones(len(x), dtype=np.float64), 1.0
    else:
        raise ValueError('window selection is explicit')
    spectrum = np.fft.rfft(x * w)
    freq = np.fft.rfftfreq(len(x), d=1.0/sample_rate)
    weight = np.full(spectrum.size, 2.0)
    weight[0] = 1.0
    if len(x) % 2 == 0:
        weight[-1] = 1.0
    selected = (freq >= low_hz) & (freq <= high_hz)
    watts = float(np.sum(weight[selected] * np.abs(spectrum[selected]) ** 2) /
                  (len(x) * np.sum(w * w)))
    return dict(power=watts, dbfs=band_dbfs(watts), low_hz=low_hz,
                high_hz=high_hz, window=window, enbw_bins=enbw)


ANALYSIS_V1 = {
    'id': 'analysis-v1',
    'state': 'specification-only; coefficient generation and certification unrun in P00',
    'native_rates_hz': [2822400, 5644800, 11289600],
    'fir': {'design': 'symmetric binary64 at native DSD rate',
            'passband_end_hz': 20000, 'stopband_start_hz': 24000,
            'maximum_passband_error_db': 0.00001,
            'minimum_stopband_rejection_db': 180,
            'coefficients_sha256': None},
    'decimate_to_hz': 88200,
    'measurement_trim': 'max(250ms, twice FIR impulse support) each end',
    'minimum_retained_seconds': 1.0,
    'tone_frequencies_hz': [997, 1000],
    'source_peaks_dbfs': [-0.1, -6, -20, -60, -90, -120],
    'full_scale': 'separate explicit case',
    'fundamental': 'least squares with DC, sine, cosine at known frequency',
    'thdn': '20Hz..20kHz residual power after fundamental/DC removal, harmonics included',
    'band_dbfs': '10*log10(P/0.5); sine with peak=1 has 0 dBFS',
    'snr': '10*log10(P_fundamental/P_residual), separately reported',
    'window_default': 'periodic BH4 0.35875 - 0.48829 cos + 0.14128 cos(2x) - 0.01168 cos(3x)',
    'coherent_window': 'rectangular only for explicitly coherent aligned cycles',
    'independent_reference_required': True,
    'phase_P00_quality_claims': [],
}
