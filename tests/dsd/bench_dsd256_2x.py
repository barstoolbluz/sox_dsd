#!/usr/bin/env python3
"""Six-channel DSD256 2x reference target, with auditable receipts.

DSD_DESIGN 10.7 requires the new decoder compared both against the legacy
ultra-quality direct path and against a *bandwidth-matched staged legacy
control*, because a speedup caused only by narrower bandwidth is not a real
speedup.

Two earlier attempts were wrong. The first used `rate -v` then `sinc -20000`:
post-filtering cannot undo aliasing from the earlier decimation. The second
staged correctly but still matched to 20 kHz, which is the passband of neither
profile at DSD256 -- v1 declares 40 kHz and v2 declares 66 kHz -- so it
over-filtered both controls.

This version asks the decoder what its passband is, per profile, via
`--dsd-report`, and matches the control to that. It does not hard-code a
number, so it cannot be wrong about one again.

Every repetition is persisted. Confidence intervals are computed from the saved
samples by a recorded method, so a reviewer can recompute them without
rerunning anything.
"""
from __future__ import annotations
import argparse, hashlib, json, os, platform, random, statistics, subprocess, sys, time
from pathlib import Path

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def host():
    def rd(p, d='unavailable'):
        try: return Path(p).read_text().strip()
        except Exception: return d
    cpu = ''
    for line in Path('/proc/cpuinfo').read_text().splitlines():
        if line.startswith('model name'): cpu = line.split(':',1)[1].strip(); break
    return dict(cpu_model=cpu, microcode=next(
        (l.split(':')[1].strip() for l in Path('/proc/cpuinfo').read_text().splitlines()
         if l.startswith('microcode')), 'unavailable'),
        governor=rd('/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor'),
        boost=rd('/sys/devices/system/cpu/cpufreq/boost'),
        no_turbo=rd('/sys/devices/system/cpu/intel_pstate/no_turbo'),
        kernel=platform.release(), python=sys.version.split()[0],
        logical_cpus=os.cpu_count())

def clock_samples(cpu, proc):
    f = Path(f'/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_cur_freq')
    out = []
    while proc.poll() is None:
        try: out.append(int(f.read_text()))
        except Exception: pass
        time.sleep(0.05)
    return out

def timed(argv, cpu, n, warm, cwd, clock=False):
    reps, clocks = [], []
    for i in range(warm + n):
        t0 = time.perf_counter()
        p = subprocess.Popen(['taskset','-c',str(cpu)]+argv, cwd=cwd,
                             stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        cs = clock_samples(cpu, p) if clock and i >= warm else None
        err = p.communicate()[1]
        dt = time.perf_counter()-t0
        if p.returncode != 0:
            raise SystemExit(f'arm failed: {argv}\n{err.decode()[-400:]}')
        if i >= warm:
            reps.append(dt)
            if cs: clocks.append(cs)
    return reps, clocks

def boot_ratio(a, b, iters=10000, seed=20261014):
    """Paired-independent bootstrap of median(a)/median(b). Recorded so a
    reviewer can reproduce the interval from the saved samples alone."""
    r = random.Random(seed); out = []
    for _ in range(iters):
        sa = [a[r.randrange(len(a))] for _ in a]
        sb = [b[r.randrange(len(b))] for _ in b]
        out.append(statistics.median(sa)/statistics.median(sb))
    out.sort()
    return out[int(0.025*iters)], out[int(0.975*iters)]

def main():
    ap = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--sox', required=True)
    ap.add_argument('--candidate', required=True)
    ap.add_argument('--results', type=Path, required=True)
    ap.add_argument('--cpu', type=int, default=8)
    ap.add_argument('--repetitions', type=int, default=15)
    ap.add_argument('--warmups', type=int, default=3)
    ap.add_argument('--seconds', type=float, default=2.0)
    ap.add_argument('--profiles', default='mastering,decode.mastering.v2.dsd256',
                    help='decode profiles to measure; the matched control for each '
                         'is band-limited to that profile\'s own reported passband')
    a = ap.parse_args()
    a.results.mkdir(parents=True, exist_ok=True)
    W = a.results/'work'; W.mkdir(exist_ok=True)
    cwd = str(Path(a.sox).resolve().parent.parent)
    sox, cand = str(Path(a.sox).resolve()), str(Path(a.candidate).resolve())

    # fixture: six-channel DSD256
    src6 = W/'src6.wav'; nat = W/'d256_6ch.dsf'
    subprocess.run([sox,'-n','-r','352800','-b','32','-e','signed-integer',str(src6),
        'synth',str(a.seconds),'sine','997','sine','1193','sine','1511','sine','1777',
        'sine','2003','sine','2311','vol','0.25'], check=True, capture_output=True, cwd=cwd)
    subprocess.run([cand,'--dsd-layout-loss','warn',str(src6),'-r','11289600',
        str(nat),'pcmdsd','11289600'], check=True, capture_output=True, cwd=cwd)

    def passband_of(profile):
        """Ask the decoder, rather than assume. A hard-coded number was wrong twice."""
        rp = W/f'probe-{profile}.json'
        subprocess.run([sox,'--dsd-report',str(rp),'--dsd-layout-loss','warn',str(nat),
            '-b','32','-e','signed-integer',str(W/'probe.wav'),
            'dsdpcm','-p',profile,'-l','preserve','352800'],
            check=True, capture_output=True, cwd=cwd)
        d = json.loads(rp.read_text())['processing']['decoder'][0]
        return int(d['effective_passband_hz']), d['profile_id']

    rows = {}
    for profile in [p.strip() for p in a.profiles.split(',') if p.strip()]:
        pb, pid = passband_of(profile)
        rows[profile] = dict(profile_id=pid, effective_passband_hz=pb, rates={})
        for out_hz in (352800, 176400):
            inter = 176400 if pb >= 80000 else 88200 if pb < 44100 else 352800
            arms = {
              'decoder': [sox,'--dsd-layout-loss','warn',str(nat),'-b','32',
                          '-e','signed-integer',str(W/f'dec{out_hz}.wav'),
                          'dsdpcm','-p',profile,'-l','preserve',str(out_hz)],
              'legacy_direct': [sox,'-D',str(nat),'-r',str(out_hz),'-e','floating-point',
                          '-b','64',str(W/f'ref{out_hz}.wav'),'rate','-v'],
              'legacy_staged_matched': [sox,'-D',str(nat),'-r',str(out_hz),
                          '-e','floating-point','-b','64',str(W/f'stg{out_hz}.wav'),
                          'rate','-v',str(min(inter,out_hz)),'sinc',f'-{pb}','rate','-v'],
            }
            r = {}
            for name, argv in arms.items():
                reps, clocks = timed(argv, a.cpu, a.repetitions, a.warmups, cwd, clock=True)
                busy = [c/1000 for cs in clocks for c in cs if c > 2_200_000]
                r[name] = dict(command=argv, repetitions=reps,
                    median=statistics.median(reps),
                    spread_pct=100*(max(reps)-min(reps))/statistics.median(reps),
                    clock_mhz_median=(statistics.median(busy) if busy else None),
                    clock_busy_samples=len(busy))
            d = r['decoder']['repetitions']
            for ctrl in ('legacy_direct','legacy_staged_matched'):
                c = r[ctrl]['repetitions']
                lo, hi = boot_ratio(c, d)
                r[f'speedup_vs_{ctrl}'] = dict(
                    point=statistics.median(c)/statistics.median(d),
                    ci95=[lo,hi], meets_2x_at_ci_lower_bound=bool(lo >= 2.0))
            rows[profile]['rates'][out_hz] = r

    report = dict(
        schema='P15/dsd256-2x-reference-target/2', target=2.0,
        host=host(), pinned_cpu=a.cpu, repetitions=a.repetitions, warmups=a.warmups,
        bootstrap=dict(method='independent bootstrap of median ratio',
                       iterations=10000, seed=20261014,
                       note='recomputable from the saved repetitions alone'),
        fixture=dict(native_hz=11289600, channels=6, seconds=a.seconds,
                     source_sha256=sha(src6), native_sha256=sha(nat)),
        executables=dict(sox_sha256=sha(sox), candidate_sha256=sha(cand)),
        matched_control=dict(
            passband_source='decoder --dsd-report effective_passband_hz, per profile',
            construction=('decimate to an intermediate rate, band-limit there, '
                          'then rate to the declared output rate'),
            supersedes_2=('a 20 kHz match, which is the passband of neither '
                          'profile at DSD256: v1 declares 40 kHz, v2 declares 66 kHz'),
            supersedes='rate -v followed by sinc, which cannot undo prior aliasing'),
        rows=rows, qualified=False,
        note='Measurement only. Closing this gate is not ours to decide.')
    (a.results/'dsd256-2x.json').write_text(json.dumps(report, indent=1, sort_keys=True)+'\n')
    for profile, pr in rows.items():
        print('%s  (%s, passband %d Hz)' % (profile, pr['profile_id'], pr['effective_passband_hz']))
        for out_hz, r in pr['rates'].items():
            for ctrl in ('legacy_direct','legacy_staged_matched'):
                s = r[f'speedup_vs_{ctrl}']
                print('  %-7s vs %-22s %.2fx  CI95 [%.2f, %.2f]  >=2x: %s'
                      % (out_hz, ctrl, s['point'], s['ci95'][0], s['ci95'][1],
                         s['meets_2x_at_ci_lower_bound']))
    for f in W.glob('*'): f.unlink()
    W.rmdir()
    print('wrote', a.results/'dsd256-2x.json')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
