#!/usr/bin/env python3
"""Replay the 43 historically stranded P15 intervals' *alias schedules*.

This is source-binding and routing QA only.  It does NOT run FIR magnitude
arithmetic, certify any band, adjudicate an old OPEN, or alter release gates.
Any routing contradiction fails closed instead of reporting a spectral PASS.
"""
from __future__ import annotations

from fractions import Fraction
from hashlib import sha256
import argparse
import json
from pathlib import Path

from p15_full_band_campaign import ROOT, SNAPSHOTS, canonical_plan
from p15_src_capture_matrix import verify_pair
from p15_src_stagewise_continuum import complete_paths, BranchBoundary

OLD_SUMMARY=ROOT/'tests/dsd/results/P15_full_band_campaign_partial_2026-10-17/SUMMARY.json'
OLD_SUMMARY_SHA256='043e5475cb9c8d054759daa20005efd675ae58b98bfd0b6d221709b1585e3045'
DEFAULT=ROOT/'tests/dsd/results/P15_campaign_dispatch_corrective_2026-10-17/SCHEDULE_REPLAY.json'


class ScheduleReplayError(ValueError):pass


def replay():
    if sha256(OLD_SUMMARY.read_bytes()).hexdigest()!=OLD_SUMMARY_SHA256:
        raise ScheduleReplayError('historical stalled-interval summary changed')
    summary=json.loads(OLD_SUMMARY.read_text())
    jobs=canonical_plan()
    by_key={(j['cell_id'],j['mode'],j['lo'],j['hi']):j for j in jobs}
    stalls=summary['nonterminating_intervals']
    if len(stalls)!=43 or summary['intervals_nonterminating']!=43 or len(jobs)!=11516:
        raise ScheduleReplayError('historical campaign population changed')
    operators={};seen=set();results=[]
    for old in stalls:
        key=old['cell_id'],old['mode'],old['lo'],old['hi']
        if key in seen or key not in by_key:
            raise ScheduleReplayError('unknown/duplicate historical interval')
        seen.add(key)
        job=by_key[key]
        rate_key=job['intermediate_hz'],job['output_hz']
        if rate_key not in operators:
            _,operators[rate_key]=verify_pair(SNAPSHOTS/f'{rate_key[0]}-{rate_key[1]}',*rate_key)
        pending=[(Fraction(job['lo']),Fraction(job['hi']))]
        splits=[];leaves=0
        while pending:
            if len(splits)>=500:
                raise ScheduleReplayError('unbounded alias schedule for '+repr(key))
            lo,hi=pending.pop()
            paths=complete_paths(job['profile'],operators[rate_key],lo,hi,
                                 require_direct=job['mode']=='pass')
            if isinstance(paths,BranchBoundary):
                boundary=paths.at
                if not lo<boundary<hi:
                    raise ScheduleReplayError('non-interior alias split')
                splits.append(str(boundary))
                pending.extend(((lo,boundary),(boundary,hi)))
            else:
                leaves+=1
        results.append(dict(cell_id=job['cell_id'],mode=job['mode'],lo=job['lo'],hi=job['hi'],
                            status='COMPLETE-SCHEDULE',exact_splits=len(splits),
                            stationary_leaves=leaves,boundaries=splits[:20],error=None))
    return dict(schema='P15/43-historical-stalls-exact-boundary-replay/1',
                previously_stalled_intervals=len(results),stationary_schedule_results=results,
                qualified_release=False,
                scope='alias routing only; no FIR magnitude or composite frequency bound')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=DEFAULT)
    args=p.parse_args()
    result=replay()
    data=json.dumps(result,sort_keys=True,indent=2)+'\n'
    output=args.output
    if output.exists():
        if output.is_symlink() or output.read_text()!=data:
            raise ScheduleReplayError('conflicting historical routing replay')
    else:
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(data)
    print(json.dumps(dict(status='COMPLETE-SCHEDULE-NOT-SPECTRAL-PASS',
        intervals=result['previously_stalled_intervals'],
        exact_splits=sum(r['exact_splits'] for r in result['stationary_schedule_results']),
        qualified_release=False),sort_keys=True))

if __name__=='__main__':main()
