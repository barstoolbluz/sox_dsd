#!/usr/bin/env python3
"""2.0.0 acceptance for the certified switched-resonator modulators (DSD64/128).

1. Each vendored certificate is replayed exactly, and constants.h is checked
   to be the header that certificate generates.
2. An independent pure-Python binary64 implementation of the recurrence,
   reading its constants from the generated headers, must reproduce every
   decision and recovery counter that SoX's production modulate path emits,
   on ordinary and hostile native input that drives recovery mode.
3. The CLI encodes mono, stereo and 5.1 with the v3 profile and the resonator
   kernel, and the retired v1 IDs are refused.
No music files are needed.
"""
import argparse, json, math, os, random, re, shutil, struct, subprocess, sys, tempfile, wave
from pathlib import Path

RATES = {64: 2822400, 128: 5644800}
failures = []

def check(ok, what):
    print(('PASS ' if ok else 'FAIL ') + what, flush=True)
    if not ok:
        failures.append(what)

def load_constants(header):
    text = header.read_text()
    def array(name):
        m = re.search(r'%s\[8\] = \{([^}]*)\}' % name, text)
        return [float.fromhex(v.strip()) for v in m.group(1).split(',')]
    m = re.search(r'transform\[8\]\[8\] = \{(.*?)\n\};', text, re.S)
    rows = re.findall(r'\{([^}]*)\}', m.group(1))
    c = {'T': [[float.fromhex(v.strip()) for v in r.split(',')] for r in rows]}
    for name in ('feedback', 'resonator', 'state_cap', 'recovery_entry_cap', 'recovery_exit_cap'):
        c[name] = array(name)
    for name in ('IQ_ENERGY_LIMIT', 'IQ_RECOVERY_ALPHA', 'IQ_RECOVERY_EXIT_ENERGY'):
        c[name] = float.fromhex(re.search(r'#define %s (\S+)' % name, text).group(1))
    return c

def oracle(c, xs):
    """The certified recurrence, operation for operation, in Python floats."""
    T, g, a = c['T'], c['resonator'], c['feedback']
    entry, exitcap = c['recovery_entry_cap'], c['recovery_exit_cap']
    alpha, limit, exit_e = c['IQ_RECOVERY_ALPHA'], c['IQ_ENERGY_LIMIT'], c['IQ_RECOVERY_EXIT_ENERGY']
    s = [0.0] * 8
    mode = entries = steps = 0
    out = bytearray(len(xs))
    for i, x in enumerate(xs):
        rec = mode
        if not rec and not all(abs(s[j]) <= entry[j] for j in range(8)):
            rec = 1
            entries += 1
        v = x
        for j in range(8):
            v = v + a[j] * s[j]
        q = -1 if math.copysign(1.0, v) < 0 else 1
        t = [0.0] * 8
        base = s[0] - g[0] * s[1]
        if rec:
            base = base * alpha
        base = base + x
        t[0] = base - q
        for j in range(1, 7):
            z = s[j] + s[j - 1]
            z = z - g[j] * s[j + 1]
            if rec:
                z = z * alpha
            t[j] = z
        t[7] = s[7] + s[6]
        if rec:
            t[7] = t[7] * alpha
            e = 0.0
            for r in range(8):
                z = 0.0
                for j in range(r, 8):
                    z = z + T[r][j] * t[j]
                e = e + z * z
            if not e <= limit:
                raise AssertionError(f'oracle energy breach at {i}')
            steps += 1
            if e <= exit_e and all(abs(t[j]) <= exitcap[j] for j in range(8)):
                rec = 0
        s = t
        mode = rec
        out[i] = 1 if q > 0 else 0
    return bytes(out), entries, steps

def stimuli(rate):
    rng = random.Random(20261108 + rate)
    n = 6000
    seq = []
    # ordinary programme level after the default 0.9 gain: within +-0.45
    seq += [0.45 * math.sin(2 * math.pi * 997 * i / RATES[rate]) * (0.5 + 0.5 * math.sin(i / 3000))
            for i in range(n)]
    seq += [rng.uniform(-0.45, 0.45) for _ in range(n)]
    # hostile: admitted rails that force recovery mode, then programme again
    seq += [0.5 if i % 2 == 0 else -0.5 for i in range(n)]
    seq += [rng.choice((0.5, -0.5)) for _ in range(n)]
    seq += [0.5] * n
    seq += [(0.5, -0.5, 0.0)[(i // 97) % 3] for i in range(n)]
    seq += [-0.5] * n
    seq += [0.45 * math.sin(2 * math.pi * 1000 * i / RATES[rate]) for i in range(n)]
    seq += [0.0, -0.0] * (n // 2)
    return seq

def certificate_replay(src, python):
    for rate in RATES:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / f'dsd{rate}'
            shutil.copytree(src / 'resonator' / f'dsd{rate}', root)
            delivered = (root / 'results' / 'proof.json').read_bytes()
            p = subprocess.run([python, '-s', '-E', 'check_certificate.py', '--write'],
                               cwd=root / 'proofs', capture_output=True, text=True)
            check(p.returncode == 0 and json.loads(p.stdout)['status'] == 'PASS',
                  f'DSD{rate} exact certificate replay')
            check((root / 'results' / 'proof.json').read_bytes() == delivered,
                  f'DSD{rate} replayed proof.json equals the vendored record')
            p = subprocess.run([python, '-s', '-E', 'emit_header.py', '--check'],
                               cwd=root / 'proofs', capture_output=True, text=True)
            check(p.returncode == 0, f'DSD{rate} constants.h is the certificate\'s generated header')

def oracle_match(src, unit):
    for rate, hz in RATES.items():
        c = load_constants(src / 'resonator' / f'dsd{rate}' / 'src' / 'constants.h')
        xs = stimuli(rate)
        want, entries, steps = oracle(c, xs)
        p = subprocess.run([str(unit), '--modulate', str(hz)],
                           input=struct.pack(f'<{len(xs)}d', *xs), capture_output=True)
        got = p.stdout
        stats = json.loads(p.stderr.decode().strip().splitlines()[-1]) if p.returncode == 0 else {}
        diff = next((i for i in range(min(len(got), len(want))) if got[i] != want[i]), None)
        check(p.returncode == 0 and got == want,
              f'DSD{rate} production bits equal the independent oracle on {len(xs)} samples'
              + ('' if diff is None else f' (first difference at {diff})'))
        check(stats.get('recovery_entries') == entries and stats.get('recovery_steps') == steps
              and entries > 0,
              f'DSD{rate} recovery counters agree ({entries} entries, {steps} steps)')

def write_wav(path, channels, rate=44100, seconds=0.5):
    n = int(rate * seconds)
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(channels)
        w.setsampwidth(3)
        w.setframerate(rate)
        frames = bytearray()
        for i in range(n):
            for ch in range(channels):
                v = int(0.5 * (2 ** 23 - 1) * math.sin(2 * math.pi * (440 + 110 * ch) * i / rate))
                frames += v.to_bytes(3, 'little', signed=True)
        w.writeframes(bytes(frames))

def cli(sox):
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        for channels in (1, 2, 6):
            src = d / f'in{channels}.wav'
            write_wav(src, channels)
            for rate in RATES:
                out = d / f'out{channels}-{rate}.dsf'
                rep = d / f'r{channels}-{rate}.json'
                # A plain WAV carries no roles; 5.1 needs them for DSF.
                layout = ['--dsd-layout', 'FL,FR,FC,LFE,BL,BR'] if channels == 6 else []
                p = subprocess.run([sox, *layout, '--report', rep, src, '-r', f'dsd{rate}', out],
                                   capture_output=True, text=True)
                ok = p.returncode == 0 and out.stat().st_size > 92
                enc = json.loads(rep.read_text())['processing']['encoder'] if ok else []
                ok = ok and len(enc) == channels and all(
                    e['profile_id'] == f'encode.mastering.v3.dsd{rate}' and
                    e['sdm_kernel_actual'] == 'resonator' and e['failure_code'] == 0 for e in enc)
                check(ok, f'DSD{rate} {channels}-channel encode uses the v3 resonator')
        for rate in RATES:
            out = d / f'retired{rate}.dsf'
            p = subprocess.run([sox, '--encode', f'encode.mastering.v1.dsd{rate}', d / 'in2.wav',
                                '-r', f'dsd{rate}', out], capture_output=True, text=True)
            check(p.returncode != 0 and not out.exists(), f'retired encode.mastering.v1.dsd{rate} refused')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', type=Path, required=True)
    ap.add_argument('--sox', required=True)
    ap.add_argument('--unit', required=True)
    ap.add_argument('--python', default=sys.executable)
    a = ap.parse_args()
    certificate_replay(a.src, a.python)
    oracle_match(a.src, a.unit)
    cli(a.sox)
    print(json.dumps({'failed': len(failures)}))
    return 1 if failures else 0

if __name__ == '__main__':
    sys.exit(main())
