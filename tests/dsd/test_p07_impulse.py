#!/usr/bin/env python3
"""P07 independently measured private-SRC impulse, phase and boundary response.

The comparator intentionally uses a *different* Kaiser FIR design. Tolerances
below measure the resulting two-FIR difference rather than reusing P06's
one-int32-LSB reconstruction bound. Finite start and end pulses exercise the
private backend's zero extension rather than legacy public-rate LPC.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import subprocess
import sys

try:
    import numpy as np
    from scipy.signal import firwin, resample_poly
except ImportError as error:
    print(f"UNRUN required P07 impulse/phase SRC reference (missing {error.name})", file=sys.stderr)
    raise SystemExit(2) from None

CASES = ((88200, 48000), (176400, 96000), (352800, 192000),
         (88200, 96000), (176400, 48000), (352800, 384000))
LENGTH = 16384
POSITIONS = (0, LENGTH // 2, LENGTH - 1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--unit', type=Path, required=True)
    parser.add_argument('--results', type=Path, required=True)
    args = parser.parse_args()
    rows = []
    for source_hz, target_hz in CASES:
        divisor = math.gcd(source_hz, target_hz)
        up, down = target_hz // divisor, source_hz // divisor
        high = max(up, down)
        tap_count = 401 * high + 1
        if tap_count % 2 == 0:
            tap_count += 1
        reference_taps = firwin(tap_count, 0.975 / high,
                                window=('kaiser', 18.9))
        expected = (LENGTH * target_hz + source_hz // 2) // source_hz
        for pulse in POSITIONS:
            run = subprocess.run([str(args.unit.resolve()), '--impulse',
                                  str(source_hz), str(target_hz),
                                  str(LENGTH), str(pulse)],
                                 capture_output=True, timeout=45)
            if run.returncode:
                raise AssertionError((source_hz, target_hz, pulse,
                                      run.returncode, run.stderr[-250:]))
            actual = np.frombuffer(run.stdout, dtype='<f8').copy()
            input_signal = np.zeros(LENGTH, dtype=np.float64)
            input_signal[pulse] = 0.5
            reference = resample_poly(input_signal, up, down,
                                      window=reference_taps)[:expected]
            if len(actual) != expected or len(reference) != expected or not np.all(np.isfinite(actual)):
                raise AssertionError(('finite pulse length', source_hz, target_hz, pulse))
            difference = float(np.max(np.abs(actual - reference)))
            row = dict(input_hz=source_hz, output_hz=target_hz,
                       input_pulse_frame=pulse, output_frames=expected,
                       full_abs_max=difference,
                       comparison='independent 180dB Kaiser FIR; finite zero extension')
            # A short pulse excites the different transition-band shapes;
            # edge pulses also expose different FIR boundary windows.
            # This is not the FIR one-LSB numerical contract.
            boundary_limit = .013 if pulse == 0 else .001
            if difference > boundary_limit:
                raise AssertionError(('impulse boundary', row, boundary_limit))
            if pulse == LENGTH // 2:
                # Fit and subtract a linear phase ramp: two linear-phase
                # rational SRCs may select fractional-sample center offsets.
                fft_length = 1 << 17
                freqs = np.fft.rfftfreq(fft_length, 1 / target_hz)
                A = np.fft.rfft(actual, n=fft_length)
                B = np.fft.rfft(reference, n=fft_length)
                band = (freqs >= 100) & (freqs <= .9 * min(source_hz, target_hz) / 2)
                transfer = A[band] / B[band]
                deviation_db = float(np.max(np.abs(20 * np.log10(np.abs(transfer)))))
                phase = np.unwrap(np.angle(transfer))
                linear_phase = np.polyfit(freqs[band], phase, deg=1)
                phase_residual = float(np.max(np.abs(phase - np.polyval(linear_phase, freqs[band]))))
                delay_samples = float(-linear_phase[0] * target_hz / (2 * np.pi))
                row.update(passband_gain_delta_db=deviation_db,
                           phase_residual_rad=phase_residual,
                           relative_fractional_delay_samples=delay_samples)
                if (deviation_db > 2e-6 or phase_residual > 1e-6 or abs(delay_samples) > .005):
                    raise AssertionError(('impulse passband/phase', row))
            rows.append(row)
    report = dict(schema='sox.dsd.p07.independent-impulse.v1', cases=len(rows),
                  input_frames=LENGTH,
                  comparator='SciPy resample_poly with independently specified Kaiser taps',
                  passband='100 Hz to 90% of the lower input/output Nyquist',
                  max_passband_gain_delta_db=2e-6, max_phase_residual_rad=1e-6,
                  max_relative_delay_frames=.005,
                  center_or_final_impulse_tolerance_abs=.001,
                  first_impulse_tolerance_abs=.013,
                  note='Empirical SRC impulse/phase/zero-extension tolerances, separate from P06 scalar FIR LSB bound',
                  results=rows)
    args.results.mkdir(parents=True, exist_ok=True)
    destination = args.results / 'impulse-reference.json'
    temporary = destination.with_suffix('.tmp')
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    temporary.replace(destination)
    print(f'P07 private SRC impulse/phase PASS: {len(rows)} independently compared finite pulses')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
