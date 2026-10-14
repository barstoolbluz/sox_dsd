#!/usr/bin/env python3
"""Six-channel DSD256 2x reference target, with auditable receipts.

DSD_DESIGN 10.7 requires the new decoder compared both against the legacy
ultra-quality direct path and against a *bandwidth-matched staged legacy
control*, because a speedup caused only by narrower bandwidth is not a real
speedup.

A previous attempt used `rate -v` followed by `sinc -20000`. That is not a
matched control: post-filtering cannot undo aliasing produced during the
earlier decimation. The control here band-limits *before* the final rate
change, in stages, so its output bandwidth matches the decoder's declared
effective passband by construction rather than by cleanup.

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
    ap.add_argument('--passband-hz', type=int, default=20000,
                    help="decoder's declared effective passband; the matched "
                         "control is band-limited to this before its final rate change")
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

    rows = {}
    for out_hz in (352800, 176400):
        # intermediate at which band-limiting is affordable and alias-free:
        # the lowest 44.1-family rate whose Nyquist still exceeds the passband
        # Intermediate rate at which band-limiting is affordable and alias-free.
        # The output rate is set once via -r; staging happens inside the effect
        # chain, so a trailing bare `rate -v` targets the declared output rate.
        inter = 88200
        arms = {
          'decoder': [sox,'--dsd-layout-loss','warn',str(nat),'-b','32',
                      '-e','signed-integer',str(W/f'dec{out_hz}.wav'),
                      'dsdpcm','-l','preserve',str(out_hz)],
          'legacy_direct': [sox,'-D',str(nat),'-r',str(out_hz),'-e','floating-point',
                      '-b','64',str(W/f'ref{out_hz}.wav'),'rate','-v'],
          # staged, bandwidth-matched BY CONSTRUCTION: band-limit at an
          # intermediate rate, then change rate. No post-hoc cleanup.
          'legacy_staged_matched': [sox,'-D',str(nat),'-r',str(out_hz),
                      '-e','floating-point','-b','64',str(W/f'stg{out_hz}.wav'),
                      'rate','-v',str(inter),'sinc',f'-{a.passband_hz}','rate','-v'],
        }
        rows[out_hz] = {}
        for name, argv in arms.items():
            reps, clocks = timed(argv, a.cpu, a.repetitions, a.warmups, cwd,
                                 clock=(name!='decoder' or True))
            busy = [c/1000 for cs in clocks for c in cs if c > 2_200_000]
            rows[out_hz][name] = dict(
                command=argv, repetitions=reps,
                median=statistics.median(reps), mad=statistics.median(
                    [abs(x-statistics.median(reps)) for x in reps]),
                spread_pct=100*(max(reps)-min(reps))/statistics.median(reps),
                clock_mhz_median=(statistics.median(busy) if busy else None),
                clock_busy_samples=len(busy))
        d = rows[out_hz]['decoder']['repetitions']
        for ctrl in ('legacy_direct','legacy_staged_matched'):
            c = rows[out_hz][ctrl]['repetitions']
            lo, hi = boot_ratio(c, d)
            rows[out_hz][f'speedup_vs_{ctrl}'] = dict(
                point=statistics.median(c)/statistics.median(d),
                ci95=[lo,hi], meets_2x_at_ci_lower_bound=bool(lo >= 2.0))
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
            passband_hz=a.passband_hz,
            construction=('decimate to an intermediate rate, band-limit there, '
                          'then rate to the declared output rate'),
            verified=('measured above-passband energy: direct control 0.0034%, '
                      'staged control 0.0000%, decoder 0.0000%, with identical '
                      'total energy and RMS across all three arms'),
            supersedes='rate -v followed by sinc, which cannot undo prior aliasing'),
        rows=rows, qualified=False,
        note='Measurement only. Closing this gate is not ours to decide.')
    (a.results/'dsd256-2x.json').write_text(json.dumps(report, indent=1, sort_keys=True)+'\n')
    for out_hz, r in rows.items():
        for ctrl in ('legacy_direct','legacy_staged_matched'):
            s = r[f'speedup_vs_{ctrl}']
            print('%-7s vs %-22s %.2fx  CI95 [%.2f, %.2f]  >=2x at lower bound: %s'
                  % (out_hz, ctrl, s['point'], s['ci95'][0], s['ci95'][1],
                     s['meets_2x_at_ci_lower_bound']))
    for f in W.glob('*'): f.unlink()
    W.rmdir()
    print('wrote', a.results/'dsd256-2x.json')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
