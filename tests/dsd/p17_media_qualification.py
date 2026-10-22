#!/usr/bin/env python3
"""Private licensed-media P17 DSF whole-track functional evidence collector.

Does not include files, source names or PCM in public receipts. Never converts
an internal packed/expanded identity test into independent audio qualification.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import time

ROOT=Path(__file__).resolve().parents[2]

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(8<<20),b''):h.update(chunk)
    return h.hexdigest()

def load(path):
    return json.loads(path.read_text(),parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))

def atomic(path,row):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.tmp')
    temp.write_text(json.dumps(row,sort_keys=True,indent=2,allow_nan=False)+'\n')
    os.replace(temp,path)

def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('--media-root',type=Path,default=None,
        help='private licensed DSF directory; never copied to evidence')
    a.add_argument('--probe',type=Path,default=ROOT/'test/dsd_test_p17_dsf')
    a.add_argument('--results',type=Path,default=ROOT/'tests/dsd/results/P17_qualification_2026-10-21/media')
    a.add_argument('--expected-dsd512-tracks',type=int,default=12)
    a.add_argument('--tiers',default='scalar')
    a.add_argument('--timeout-per-track',type=int,default=14400)
    a.add_argument('--require-media',action='store_true')
    args=a.parse_args();args.probe=args.probe.resolve();args.results=args.results.resolve()
    if args.expected_dsd512_tracks<1 or args.timeout_per_track<1:
        a.error('track count and timeout must be positive')
    if not args.probe.is_file():a.error('DSF probe not built')
    tiers=args.tiers.split(',')
    if ('scalar' not in tiers or len(set(tiers))!=len(tiers) or any(x not in
        ('scalar','sse2','avx1','avx2','avx512') for x in tiers)):
        a.error('explicit unique supported tiers including scalar required')
    paths=[]
    if args.media_root is not None:
        root=args.media_root.resolve()
        if not root.is_dir():a.error('media directory missing')
        paths=sorted(p for p in root.rglob('*') if p.is_file() and p.suffix.lower()=='.dsf')
    binary_sha=sha(args.probe);runner_sha=sha(Path(__file__))
    cases=[]
    for path in paths:
        full_sha=sha(path);token=full_sha[:20]
        for profile,out in (('mastering',176400),('wideband',705600)):
            for tier in tiers:
                dest=args.results/'full_file'/f'{token}-{profile}-{tier}.json'
                previous=load(dest) if dest.is_file() else None
                reuse=(previous is not None and
                    previous.get('source_sha256')==full_sha and
                    previous.get('probe_sha256')==binary_sha and
                    previous.get('runner_sha256')==runner_sha and
                    previous.get('profile')==profile and previous.get('tier')==tier and
                    previous.get('status')=='PASS_FUNCTIONAL_ONLY')
                if reuse:
                    cases.append(previous);print('REUSE',token,profile,tier,flush=True)
                    continue
                if previous is not None:
                    raise RuntimeError('refusing stale/mismatched media receipt overwrite '+str(dest))
                started=time.monotonic();cmd=[str(args.probe),str(path),profile,str(out),tier,'full']
                try:
                    proc=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,
                        text=True,timeout=args.timeout_per_track)
                    rc=proc.returncode;stderr=proc.stderr[-2000:]
                    result=json.loads(proc.stdout,parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x))) if rc==0 else None
                except (subprocess.TimeoutExpired,ValueError,json.JSONDecodeError) as ex:
                    result=None;rc=124;stderr=str(ex)
                passed=(rc==0 and result is not None and
                    result.get('status')=='PASS_FUNCTIONAL_ONLY' and
                    result.get('packed_expanded_equal') is True and
                    result.get('rate_hz') in (22579200,45158400) and
                    result.get('channels')==2 and result.get('profile')==profile and
                    result.get('destination_hz')==out and result.get('kernel')==tier and
                    result.get('native_frames',0)>0 and
                    result.get('pcm_frames')==(result['native_frames']*out+
                        result['rate_hz']//2)//result['rate_hz'])
                decode_wall=result.get('decode_wall_seconds') if result else None
                speed=(result['native_frames']/decode_wall
                    if decode_wall and decode_wall>0 else None)
                realtime=(speed/result['rate_hz'] if speed else None)
                row=dict(schema='P17/commercial-full-file-case/1',
                    status='PASS_FUNCTIONAL_ONLY' if passed else 'FAIL',
                    source_sha256=full_sha,source_id=token,source_bytes=path.stat().st_size,
                    profile=profile,tier=tier,probe_sha256=binary_sha,runner_sha256=runner_sha,
                    command=['test/dsd_test_p17_dsf','<licensed-file>',profile,str(out),tier,'full'],
                    exit_code=rc,elapsed_seconds=time.monotonic()-started,
                    stderr_tail=stderr,decoder=result,
                    instrumented_native_frames_per_second=speed,
                    instrumented_real_time_factor=realtime,
                    timing_scope='two independent decode contexts (packed+expanded); NOT shipping single-path throughput',
                    independent_reference_qualification='UNRUN_NOT_COLLECTED',
                    device_interoperability='NOT_CLAIMED')
                atomic(dest,row);cases.append(row)
                print(row['status'],token,profile,tier,flush=True)
    by_rate={rate:{x['source_sha256'] for x in cases if
        x['decoder'] is not None and x['decoder']['rate_hz']==rate}
        for rate in (22579200,45158400)}
    dsd512=by_rate[22579200];dsd1024=by_rate[45158400]
    r512=[x for x in cases if x['source_sha256'] in dsd512]
    failed=any(x['status']=='FAIL' for x in cases)
    complete=(not failed and len(dsd512)>=args.expected_dsd512_tracks and
        len(r512)==len(dsd512)*len(tiers)*2 and
        all(x['status']=='PASS_FUNCTIONAL_ONLY' for x in r512) and
        all(x['source_sha256'] in dsd512|dsd1024 for x in cases))
    report=dict(schema='P17/commercial-decoder-evidence/1',
        probe_sha256=binary_sha,runner_sha256=runner_sha,
        host=dict(node=platform.node(),os=platform.platform(),machine=platform.machine()),
        expected_dsd512_tracks=args.expected_dsd512_tracks,
        distinct_dsd512_tracks=len(dsd512),distinct_dsd1024_tracks=len(dsd1024),
        case_count=len(cases),
        full_file_functional_gate='PASS' if complete else ('FAIL' if failed else 'UNRUN_OR_INCOMPLETE'),
        media_sha256=sorted(dsd512|dsd1024),
        case_receipts={f'full_file/{x["source_id"]}-{x["profile"]}-{x["tier"]}.json':x['status'] for x in cases},
        decoder_profile_qualified={f'decode.{p}.v1.dsd{rate}':False
            for rate in (512,1024) for p in ('mastering','wideband')},
        independent_reader_and_audio_reference_gate='UNRUN',
        missing_media='No independent DSD1024 licensed media provided',
        device_claims=[],public_capabilities_enabled=False,qualification='UNQUALIFIED',
        note='Licensed full files were not part of uploaded code bundle; internal PCM parity does not establish an independent decoder oracle')
    atomic(args.results/'commercial-decode-evidence.json',report)
    print('MEDIA',report['full_file_functional_gate'],len(dsd512),'DSD512 tracks')
    return 0 if (complete or not args.require_media) and not failed else 1
if __name__=='__main__':raise SystemExit(main())
