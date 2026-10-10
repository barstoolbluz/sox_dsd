#!/usr/bin/env python3
"""One-time, high-precision analysis-v1 FIR creation. Never updates a freeze.

The coefficients are synthesized without using libsox, its SRC, or the P06
filter generation code. On-disk representation is little-endian IEEE binary64.
The frozen manifest is the input to *all* subsequent quality comparisons.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import mpmath as mp

ROOT = Path(__file__).resolve().parent
RATES = (2822400, 5644800, 11289600)
PASS_HZ, STOP_HZ, CUTOFF_HZ = 20000, 24000, 22000
ATTENUATION_DESIGN_DB = 205
GENERATOR_PRECISION_DPS = 60


def coefficients(rate):
    mp.mp.dps = GENERATOR_PRECISION_DPS
    transition = mp.mpf(STOP_HZ - PASS_HZ) / rate
    atten = mp.mpf(ATTENUATION_DESIGN_DB)
    length = int(mp.ceil((atten - 8) / (mp.mpf('2.285') * 2 * mp.pi * transition))) + 1
    length += (length % 2 == 0)  # integer delay, exact linear phase
    radius = (length - 1) // 2
    beta = mp.mpf('0.1102') * (atten - mp.mpf('8.7'))
    inv_i0 = 1 / mp.besseli(0, beta)
    normalized_cutoff = mp.mpf(CUTOFF_HZ) / rate
    half = []
    for delta in range(radius + 1):
        x = mp.mpf(delta) / radius
        taper = mp.besseli(0, beta * mp.sqrt(1-x*x)) * inv_i0
        value = ((2 * normalized_cutoff) if delta == 0 else
                 mp.sin(2 * mp.pi * normalized_cutoff * delta) / (mp.pi * delta))
        half.append(value * taper)
    norm = half[0] + 2 * mp.fsum(half[1:])
    centered = [float(v / norm) for v in half]
    # Mirror the exact double bits rather than round each side separately.
    full = list(reversed(centered[1:])) + centered
    assert len(full) == length and all(math.isfinite(t) for t in full)
    return struct.pack('<' + 'd'*length, *full), dict(
        rate_hz=rate, num_taps=length, delay_native_frames=radius,
        decimation_factor=rate//88200, float64_endianness='little',
        coeff_sum_f64=math.fsum(full))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--create', action='store_true', required=True)
    args = parser.parse_args()
    if (ROOT/'manifest.json').exists() or any(ROOT.glob('fir-*.f64le')):
        parser.error('analysis-v1 is frozen; refusing to overwrite existing coefficients')
    records=[]
    for rate in RATES:
        raw, info = coefficients(rate)
        name=f'fir-{rate}.f64le'
        # Write each file using exclusive creation; a preexisting partial freeze is an error.
        with (ROOT/name).open('xb') as out:
            out.write(raw)
        info['file']=name
        info['sha256']=hashlib.sha256(raw).hexdigest()
        records.append(info)
        print(f'{rate}: {info["num_taps"]} taps SHA256 {info["sha256"]}', flush=True)
    spec=dict(id='analysis-v1', status='frozen', version=1,
        design='symmetric Kaiser-windowed ideal low-pass; arbitrary precision mpmath',
        generator_precision_decimal_digits=GENERATOR_PRECISION_DPS,
        passband_end_hz=PASS_HZ, stopband_start_hz=STOP_HZ,
        design_attenuation_db=ATTENUATION_DESIGN_DB, cutoff_hz=CUTOFF_HZ,
        required_stop_attenuation_db=180, required_passband_error_db=0.00001,
        analysis_output_rate_hz=88200,
        decimation='full convolution; delay-compensated indices delay + m*(rate/88200), m=0..ceil(native_frames/factor)-1',
        reference_native_bit_sign={'0': -1, '1': 1},
        unit_reference='normalized PCM; 0dBFS sine peak=1, band power=0.5',
        boundaries='discard max(0.25 s, twice complete FIR support) at both ends',
        retain_seconds_minimum=1.0,
        window_noncoherent={'name':'periodic Blackman-Harris four-term',
                            'coefficients':[0.35875,0.48829,0.14128,0.01168],
                            'enbw_correction':'divide integrated squared FFT by N*sum(w^2)'},
        window_coherent='rectangular, only for integer cycles in aligned measured segment',
        fit='least squares DC+sine+cosine at specified source frequency; remove these only before THD+N',
        residual_band_hz=[20,20000],
        band_dbfs='10*log10(power/0.5)',
        source_peaks_dbfs=[-0.1,-6,-20,-60,-90,-120],
        frequencies_hz=[997,1000],
        full_scale_case='separate and unqualified unless admitted after interpolation',
        records=records)
    (ROOT/'manifest.json').write_text(json.dumps(spec,sort_keys=True,indent=2)+'\n')
    checks={info['file']:info['sha256'] for info in records}
    checks['manifest.json']=hashlib.sha256((ROOT/'manifest.json').read_bytes()).hexdigest()
    (ROOT/'SHA256SUMS.txt').write_text(''.join(f'{checks[k]}  {k}\n' for k in sorted(checks)))

if __name__ == '__main__':
    main()
