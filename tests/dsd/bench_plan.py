#!/usr/bin/env python3
"""P05 plan-only startup / allocation benchmark; no unimplemented DSP is run.

The wall time includes input-header reads, option parsing and JSON serialization.
It is not a throughput or certified relative-performance gate.
"""
from __future__ import annotations
import argparse
import json
import pathlib
import statistics
import subprocess
import tempfile
import time
from reference import fixtures

ROOT=pathlib.Path(__file__).resolve().parents[2]


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--sox',type=pathlib.Path,default=ROOT/'src/sox')
    ap.add_argument('--results',type=pathlib.Path,default=ROOT/'tests/dsd/results/P05/preflight_bench')
    ap.add_argument('--repetitions',type=int,default=11)
    a=ap.parse_args()
    a.results.mkdir(parents=True,exist_ok=True)
    sox=a.sox.resolve()
    home=pathlib.Path('/var/tmp/sox-ng-bench')
    home.mkdir(parents=True,exist_ok=True)
    cases=[]
    with tempfile.TemporaryDirectory(prefix='p05-',dir=home) as temp:
        folder=pathlib.Path(temp)
        inp=folder/'fixture.dsf'
        inp.write_bytes(fixtures.make_dsf(fixtures.bits(64,2)))
        out=folder/'discard.wav'
        for n in (1,4,16,64):
            command=[str(sox),'--dsd-plan']
            if n>1:command+=['--combine','mix']
            command += [str(inp)]*n+[str(out)]
            durations=[];memory=[];fail=[]
            for repetition in range(a.repetitions):
                meter=folder/'meter.txt'
                timed=['/usr/bin/time','-f','%e %M','-o',str(meter)]
                started=time.perf_counter_ns()
                p=subprocess.run(timed+command,cwd=folder,capture_output=True,text=True,timeout=30)
                elapsed=(time.perf_counter_ns()-started)/1e9
                if p.returncode!=0:
                    fail.append({'run':repetition,'exit':p.returncode,'stderr':p.stderr[:300]})
                    continue
                try:
                    plan=json.loads(p.stdout)
                    assert plan['input_decoder_count']==(n if n>1 else 0)
                    assert len(plan['inputs']) == n
                    rss=int(meter.read_text().split()[1]); memory.append(rss)
                    durations.append(elapsed)
                except (AssertionError,ValueError,IndexError) as exc:
                    fail.append({'run':repetition,'error':str(exc)})
            case=dict(inputs=n,mode='native' if n==1 else 'parallel per-input decode',
                repetitions=a.repetitions,measured=len(durations),failures=fail,
                wall_seconds=durations,max_rss_kib=memory,
                wall_median_seconds=statistics.median(durations) if durations else None,
                rss_median_kib=statistics.median(memory) if memory else None,
                normalized_command=['sox_ng','--dsd-plan',
                    *(['--combine','mix'] if n>1 else []),
                    f'<DSD64-stereo-input> x{n}','<WAV-output>'])
            cases.append(case)
    result=dict(schema='sox.dsd.P05.preflight_bench.v1',
                host_preparation='not asserted; see benchprep status log',
                timing='process startup + header open + planner + JSON output',
                profiling_limit='not comparable to P00-P04 per-sample throughput gate',
                cases=cases)
    (a.results/'preflight.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    for c in cases:
        print(f"inputs={c['inputs']} count={c['measured']}/{c['repetitions']} "
              f"median={c['wall_median_seconds']} rss_kib={c['rss_median_kib']} "
              f"failures={len(c['failures'])}")
    return int(any(c['failures'] or not c['measured'] for c in cases))


if __name__=='__main__':raise SystemExit(main())
