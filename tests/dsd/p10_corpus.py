"""Frozen P10 synthetic corpus definitions, independent training/holdout seeds.

The admitted corpus is determined AFTER actual composite interpolation. A
nominal case that overloads is retained as a rejection, never silently lowered.
All ordinary sources are int32 graph-equivalent. Tapers only bound the finite
source; the frozen one-second analysis interval is outside those tapers.
"""
from __future__ import annotations
import hashlib
import json
import numpy as np
RATES = (2822400, 5644800, 11289600)
SOURCES = (44100, 48000, 88200, 96000, 176400, 192000, 352800, 384000, 705600)
POLICY = {2822400: (88200, 20000, 40000), 5644800: (176400, 30000, 60000),
          11289600: (176400, 40000, 80000)}


def identity(config):
    return hashlib.sha256(json.dumps(config, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def stimulus(config):
    rate = config['source_hz']
    n = int(round(config['seconds']*rate))
    t = np.arange(n, dtype=np.float64)/rate
    kind = config['kind']
    peak = config.get('peak', 10**(config.get('dbfs', -6.)/20))
    frequency = config.get('frequency', 997.)
    rng = np.random.Generator(np.random.PCG64(config.get('seed', 10001)))
    if kind == 'tone':
        y = peak*np.sin(2*np.pi*frequency*t)
    elif kind == 'silence':
        y = np.zeros(n)
    elif kind == 'dc':
        y = np.full(n, peak)
    elif kind == 'multitone' or kind == 'sustained':
        frequencies = config.get('frequencies', [37., 997., 5501., 11003., 17011.])
        y = sum((peak/len(frequencies))*np.sin(2*np.pi*f*t + j*.317)
                for j,f in enumerate(frequencies))
    elif kind == 'noise':
        y = rng.uniform(-peak, peak, n)
    elif kind == 'sweep':
        # Independent holdout reverses the low-frequency sweep.
        low, high = config.get('sweep', [5., 250.])
        y = peak*np.sin(2*np.pi*(low*t + .5*(high-low)*t*t/config['seconds']))
    elif kind == 'impulse':
        y = np.zeros(n);y[n//2] = peak
    elif kind == 'step':
        y = np.where(t < config['seconds']/2, -peak, peak)
    elif kind == 'limited':
        # The source is explicitly a limited waveform, NOT an encoder limiter.
        y = np.clip(peak*2*np.sin(2*np.pi*frequency*t), -peak, peak)
    elif kind == 'starts':
        y = peak*np.sin(2*np.pi*frequency*t)*(np.sin(2*np.pi*7*t)>0)
    else:
        raise ValueError('unknown frozen stimulus '+kind)
    taper = config.get('taper_seconds', .1)
    m = min(int(round(taper*rate)), n//2)
    if m:
        u = np.arange(m, dtype=np.float64)/m
        # C2 endpoint ramp avoids a hidden full-scale discontinuity at EOF.
        ramp = u*u*u*(10+u*(-15+6*u))
        y[:m] *= ramp;y[-m:] *= ramp[::-1]
    if not np.all(np.isfinite(y)) or np.max(np.abs(y), initial=0)>1:
        raise ValueError('fixture not representable in the int32 graph')
    integer = np.rint(y*(2**31-1)).astype('<i4')
    samples = integer.astype(np.float64)/(2**31-1)
    raw = samples.astype('<f8').tobytes()
    return raw, dict(source_f64le_sha256=hashlib.sha256(raw).hexdigest(),
        source_i32le_sha256=hashlib.sha256(integer.tobytes()).hexdigest(),
        frames=n, source_peak=float(np.max(np.abs(samples), initial=0)),
        source_rms=float(np.sqrt(np.mean(samples*samples))) if n else 0.,
        graph_normalization='int32/SOX_SAMPLE_MAX', configuration_sha256=identity(config))


def training_cases(native):
    R,P,_ = POLICY[native]
    base = dict(native_hz=native, source_hz=R, seconds=1.6,
                split='training', seed=101001, taper_seconds=.1)
    specs = [dict(name='silence', kind='silence'),
        dict(name='tone997-high', kind='tone', frequency=997., dbfs=-.1),
        dict(name='tone997-mid', kind='tone', frequency=997., dbfs=-6.),
        dict(name='tone997-low', kind='tone', frequency=997., dbfs=-90.),
        dict(name='dc-positive', kind='dc', peak=1.),
        dict(name='dc-negative', kind='dc', peak=-1.),
        dict(name='sweep', kind='sweep', peak=.75),
        dict(name='multitone', kind='multitone', peak=.85),
        dict(name='noise', kind='noise', peak=.5),
        dict(name='impulse', kind='impulse', peak=1.),
        dict(name='bandlimited-step', kind='step', peak=.7),
        dict(name='limited', kind='limited', peak=.65),
        dict(name='starts', kind='starts', peak=.5),
        dict(name='edge', kind='tone', frequency=.99*P, dbfs=-6.),
        dict(name='sustained-60s', kind='sustained', peak=.8, seconds=60.),
        dict(name='48k-tone', kind='tone', source_hz=48000, dbfs=-6.),
        dict(name='705k-noise', kind='noise', source_hz=705600, peak=.4)]
    return [base | spec for spec in specs]


def holdout_cases(native):
    R,P,_ = POLICY[native]
    base = dict(native_hz=native, source_hz=R, seconds=1.6,
                split='holdout', seed=201003, taper_seconds=.1)
    cases = []
    for hz in (997., 1000.):
        for db in (-.1,-6.,-20.,-60.,-90.,-120.,0.):
            cases.append(base | dict(name=f'tone-{int(hz)}-{db:g}', kind='tone',
                frequency=hz, dbfs=db, separately_handled_fullscale=db==0))
    cases += [base | spec for spec in [
        dict(name='silence',kind='silence'),
        dict(name='near-silence',kind='noise',peak=1e-6),
        dict(name='dc-positive',kind='dc',peak=1.),
        dict(name='dc-negative',kind='dc',peak=-1.),
        dict(name='sweep',kind='sweep',peak=.8,sweep=[250.,5.]),
        dict(name='multitone',kind='multitone',peak=.9,
            frequencies=[53.,1000.,6011.,13001.,19001.]),
        dict(name='noise',kind='noise',peak=.55),
        dict(name='limited',kind='limited',peak=.7,frequency=311.),
        dict(name='starts',kind='starts',peak=.6,frequency=1000.),
        dict(name='edge',kind='tone',dbfs=-6.,frequency=.97*P),
        dict(name='noise-60s',kind='noise',peak=.5,seconds=60.,skip_analysis=True),
        dict(name='deliberate-overload',kind='step',peak=1.,expected_overload=True),
        dict(name='explicit-attenuation-retry',kind='step',peak=10**(-6/20))]]
    return cases
