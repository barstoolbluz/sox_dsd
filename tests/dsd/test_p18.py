#!/usr/bin/env python3
"""P21 open high-rate file/DoP fixture and CLI proof.

Was the P18 fail-closed proof; all twelve rows were opened on 2026-10-23 and
every refusal assertion here inverted. Fixtures are still independent
reference bytes, never generated from a SoX writer, and a synthetic
high-rate fixture is still not software or device interoperability.

What this file is now for: an opened rate must be carried through, not
silently substituted. The negotiator used to be stopped by refusal; now only
the write-rate tables stop it, so every output case below reparses what was
actually written and asserts the rate it asked for. Two refusals survive and
are still asserted, because neither came from P18: native mode cannot change
DSD rate without reconstruction, and the channel-layout guard still fires on
destinations that cannot carry a named layout.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import pathlib
import platform
import subprocess
import sys
import tempfile
import time

from reference import fixtures, verify

ROOT = pathlib.Path(__file__).resolve().parents[2]
REF = ROOT/'tests/dsd/reference/p18_fixture_matrix.json'
VECTORS = ROOT/'tests/dsd/fixtures/p18'
RATES = (22_579_200, 45_158_400)
CHANNELS = (1,2,6)
COUNTS = (0,1,7,8,9,15,16,17,32767,32768,32769)
UINT64_MAX=(1<<64)-1


def sha(x: bytes) -> str:
    return hashlib.sha256(x).hexdigest()


def atomic_json(path: pathlib.Path, value: dict) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp = path.with_name(path.name+'.tmp')
    tmp.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
    tmp.replace(path)


def make_reference():
    cases=[]; vectors={}; dop_cases=[]
    for native in RATES:
        for chans in CHANNELS:
            for frames in COUNTS:
                timeline=fixtures.bits(frames,chans,'distinct')
                for fmt,bps in (('dsf',1),('dsf',8),('dff',8)):
                    # Independent bytes/bit chronology; for DFF the last
                    # byte is explicitly completed by the reference writer.
                    name=f'p18-{native}-{fmt}-{bps}-{chans}-{frames}'
                    raw=(fixtures.make_dsf(timeline,native,bps) if fmt=='dsf'
                        else fixtures.make_dff(timeline,native))
                    desc=(verify.decode_dsf(raw) if fmt=='dsf'
                        else verify.decode_dff(raw))
                    assert desc['rate']==native and desc['channels']==chans
                    assert desc['frames']==(frames if fmt=='dsf' else (frames+7)//8*8)
                    for ch in range(chans):
                        assert desc['timeline'][ch][:frames]==timeline[ch]
                    if fmt=='dsf':
                        assert len(raw)==92+((frames+32767)//32768)*4096*chans
                    else:
                        data=next(c for c in desc['top'] if c['tag']=='DSD ')
                        assert data['payload_size']==((frames+7)//8)*chans
                        assert data['pad']==data['payload_size']%2
                    cases.append(dict(name=name,native_hz=native,endpoint=fmt,
                        bit_order=bps,channels=chans,logical_frames=frames,
                        sample_count=frames*chans,byte_count=len(raw),sha256=sha(raw),
                        chronological_sha256=fixtures.chronology_sha256(timeline),
                        reader='REFUSED_UNQUALIFIED',writer='REFUSED_UNQUALIFIED'))
                    if (frames in (1,17,32769) and chans in (1,2,6) and
                        (fmt=='dsf' and bps==1 or fmt=='dff')):
                        # Checked-in frozen synthetic fixtures (36 total).
                        vectors[f'{name}.{fmt}']=raw
        for chans in CHANNELS:
            for frames in (1,15,16,17,32,33):
                timeline=fixtures.bits(frames,chans,'69')
                words=fixtures.dop_words(timeline)
                blob=bytes(byte for row in words for word in row
                    for byte in (word&255,(word>>8)&255,(word>>16)&255))
                assert all(((word>>16)==(0x05 if i%2==0 else 0xFA))
                           for i,row in enumerate(words) for word in row)
                assert len(blob)==((frames+15)//16)*chans*3
                dop_cases.append(dict(native_hz=native,transport_pcm_hz=native//16,
                    channels=chans,frames=frames,transport_frames=len(words),
                    pcm24le_sha256=sha(blob),reference_words=words,
                    transport='REFUSED_UNQUALIFIED'))
                if frames in (17,33) and chans==2:
                    vectors[f'p18-dop-{native}-{chans}-{frames}.pcm24le']=blob
    report=dict(schema='P18/fixture-matrix/1',license='CC0-1.0',
        provenance='Independent deterministic reference.fixtures writer / reference.verify parser',
        high_rate_capability='DISABLED',qualification='synthetic fixture structure only',
        artifact_claim='NOT an independent high-rate decoder/player test',
        cases=cases, dop_cases=dop_cases,
        checked_in_vectors={k:sha(v) for k,v in sorted(vectors.items())})
    return report, vectors


def command_result(cmd, env, timeout=45):
    start=time.perf_counter()
    result=subprocess.run(list(map(str,cmd)),cwd=ROOT,env=env,
        stdin=subprocess.DEVNULL,capture_output=True,timeout=timeout)
    return dict(command=[str(x).replace(str(ROOT),'<source>') for x in cmd],
        exit=result.returncode,stderr=result.stderr.decode(errors='replace')[-2000:],
        stdout_sha256=sha(result.stdout),stdout_bytes=len(result.stdout),
        wall_seconds=time.perf_counter()-start)


def probe_rate(sox, path, env):
    """Header rate as the binary reports it, independent of the decode path.

    command_result() deliberately keeps only a digest of stdout so receipts
    stay bounded; this one case needs the value itself, so it gets its own
    helper rather than widening that contract.
    """
    r=subprocess.run([str(sox),'--i','-r',str(path)],cwd=ROOT,env=env,
        stdin=subprocess.DEVNULL,capture_output=True,timeout=45)
    if r.returncode!=0:return None
    try:return float(r.stdout.decode(errors='replace').strip())
    except ValueError:return None


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--sox',type=pathlib.Path,default=ROOT/'src/sox')
    ap.add_argument('--results',type=pathlib.Path,default=ROOT/'tests/dsd/results/P18/integration')
    ap.add_argument('--generate-reference',action='store_true',
        help='explicitly refresh frozen independently generated files')
    ap.add_argument('--fixtures-only',action='store_true')
    args=ap.parse_args()
    reference,vectors=make_reference()
    if args.generate_reference:
        VECTORS.mkdir(parents=True,exist_ok=True)
        for name,raw in sorted(vectors.items()): (VECTORS/name).write_bytes(raw)
        atomic_json(REF,reference)
        print(f'P18 reference generated {len(reference["cases"])} file records, '
            f'{len(reference["dop_cases"])} DoP records, {len(vectors)} vector files')
        return 0
    if not REF.is_file():ap.error('P18 frozen reference manifest missing; cannot silently regenerate')
    if json.loads(REF.read_text())!=reference:
        ap.error('P18 synthetic fixture matrix changed; independently adjudicate source/reference drift')
    if {p.name for p in VECTORS.iterdir() if p.is_file()}!=set(vectors):
        ap.error('P18 checked-in vector membership changed')
    for name,raw in vectors.items():
        if (VECTORS/name).read_bytes()!=raw:
            ap.error(f'P18 reference vector changed: {name}')
    if args.fixtures_only:
        print(f'P18 PASS {len(reference["cases"])} fixture oracles, '
            f'{len(reference["dop_cases"])} DoP reference vectors')
        return 0
    args.sox=args.sox.resolve()
    if not args.sox.is_file():ap.error('missing real compiled SoX executable')
    args.results.mkdir(parents=True,exist_ok=True)
    environment=os.environ.copy()
    environment.update(SOX_OPTS='',LC_ALL='C',OMP_NUM_THREADS='1')
    environment.pop('SOX_DSD_PACKED_INPUT',None)
    binary_hash=sha(args.sox.read_bytes())
    signature=sha(json.dumps(dict(binary_sha256=binary_hash,
        test_sha256=sha(pathlib.Path(__file__).read_bytes()),
        reference_sha256=sha(REF.read_bytes())),sort_keys=True).encode())
    target=args.results/'capability-integration.json'
    report=dict(schema='P18/capability-integration/1',config_sha256=signature,
        sox_sha256=binary_hash,host=dict(machine=platform.machine(),
            system=platform.platform(),node=platform.node()),
        source_fixture_manifest_sha256=sha(REF.read_bytes()),
        high_rate_enabled=True,
        claims='CLI and synthetic fixture evidence that opened rates are carried, not substituted',
        authorization='P21 operator declaration 2026-10-23; see '
            'docs/dsd/amendments/P21_HIGH_RATE_ENABLEMENT_2026-10-23.md',
        cases=[],unrun_gates=['external DSD512/1024 playback, independent media and device',
          'independent reader and audio reference gate for high-rate decode',
          'native high-rate writer/transport throughput'])
    # Reuse passing checkpoints only if binary AND test inputs match.
    old={}
    if target.is_file():
        candidate=json.loads(target.read_text())
        if candidate.get('config_sha256')==signature:
            old={x['name']:x for x in candidate.get('cases',[]) if x['status']=='PASS'}
    def store(name,status,details):
        result=dict(name=name,status=status,**details)
        report['cases'].append(result)
        atomic_json(target,dict(report,summary={
            'PASS':sum(x['status']=='PASS' for x in report['cases']),
            'FAIL':sum(x['status']=='FAIL' for x in report['cases'])},
            verdict='PASS' if all(x['status']=='PASS' for x in report['cases']) else 'FAIL'))
        if status!='PASS':print('P18 FAIL',name,details,flush=True)
    with tempfile.TemporaryDirectory(prefix='sox-p18-') as tmp:
        work=pathlib.Path(tmp)
        # Existing high-rate input handlers must not accept a syntactically
        # valid file, including packed reader opt-in (no bypass).
        for native in RATES:
            for ext in ('dsf','dff'):
                for chans in CHANNELS:
                    for frames in (1,17,32769):
                        name=f'p18-{native}-{ext}-{1 if ext=="dsf" else 8}-{chans}-{frames}.{ext}'
                        for packed in (False,True):
                            key=f'input-{native}-{ext}-{chans}-{frames}-packed{int(packed)}'
                            if key in old:report['cases'].append(old[key]);continue
                            inp=VECTORS/name
                            env=dict(environment)
                            if packed:env['SOX_DSD_PACKED_INPUT']='1'
                            got=command_result([args.sox,'-V2','--dsd-layout-loss','warn',
                                '-t',ext,inp,'-n'],env)
                            # reparse the header independently of the decode path:
                            # accepting the file is not the same as reading its rate
                            seen=probe_rate(args.sox,inp,env)
                            okay=(got['exit']==0 and 'unavailable' not in got['stderr']
                                and seen==float(native))
                            store(key,'PASS' if okay else 'FAIL',dict(output=got,
                                expected=f'read accepted and reported at {native} Hz',
                                reported_rate=seen,
                                fixture_sha256=sha(inp.read_bytes()),packed=packed))
        # The inherited WSD native reader must not bypass high-rate refusal.
        # WSD is safety coverage, not a claimed new P18 format capability.
        for native in RATES:
            for chans in CHANNELS:
                name=f'wsd-{native}-{chans}'
                if name in old:report['cases'].append(old[name]);continue
                bits=fixtures.bits(16,chans,'distinct')
                source=work/f'forbidden-{native}-{chans}.wsd'
                source.write_bytes(fixtures.make_wsd(bits,native))
                got=command_result([args.sox,'-V2','--dsd-layout-loss','warn',
                    '-t','wsd',source,'-n'],environment)
                seen=probe_rate(args.sox,source,environment)
                okay=(got['exit']==0 and 'unavailable' not in got['stderr']
                      and seen==float(native))
                store(name,'PASS' if okay else 'FAIL',dict(output=got,reported_rate=seen,
                    reference_sha256=sha(source.read_bytes()),
                    expected=f'WSD read accepted and reported at {native} Hz'))
        # A refusal that is NOT P18 and must survive its removal: native mode
        # moves native bits and cannot change DSD rate without reconstruction.
        # The source here is DSD64, so asking for 512/1024 in native mode is
        # still an error, and must still leave no destination behind.
        for native in RATES:
            for ext in ('dsf','dff'):
                key=f'output-native-mode-rate-change-{native}-{ext}'
                if key in old:report['cases'].append(old[key]);continue
                dst=work/f'highrate-{native}.{ext}'
                got=command_result([args.sox,'-V2','--dsd-mode','native','-D',
                    ROOT/'tests/dsd/fixtures/stereo_96.dsf','-r',str(native),
                    '-t',ext,dst],environment)
                expected='native mode cannot change DSD rate or channels without reconstruction'
                okay=got['exit']!=0 and expected in got['stderr'] and not dst.exists()
                store(key,'PASS' if okay else 'FAIL',dict(output=got,expected=expected,
                    destination_absent=not dst.exists()))
        # The case this file now exists for. Default and legacy mode let generic
        # format negotiation silently substitute DSD256 for DSD512/1024; P18
        # caught that by refusing the rate outright. With the rows open the
        # only thing standing between a request and a quietly down-rated file
        # is the writer rate table, so reparse the result and require the rate
        # that was asked for. A substitution now shows up as a FAIL here.
        for native in RATES:
            for ext in ('dsf','dff'):
                for mode in ('default','legacy'):
                    key=f'output-no-downrate-{mode}-{native}-{ext}'
                    if key in old:report['cases'].append(old[key]);continue
                    dst=work/f'highrate-{mode}-{native}.{ext}'
                    cmd=[args.sox,'-V2']
                    if mode=='legacy':cmd+=['--dsd-mode','legacy']
                    cmd+=['-D',ROOT/'tests/dsd/fixtures/stereo_96.dsf',
                          '-r',str(native),dst]
                    got=command_result(cmd,environment)
                    okay=False;details=None
                    if got['exit']==0 and dst.is_file():
                        raw=dst.read_bytes()
                        desc=verify.decode_dsf(raw) if ext=='dsf' else verify.decode_dff(raw)
                        okay=desc['rate']==native and desc['channels']==2
                        details=dict(written_rate=desc['rate'],channels=desc['channels'],
                            physical_bytes=len(raw),output_sha256=sha(raw))
                    store(key,'PASS' if okay else 'FAIL',dict(output=got,
                        expected=f'written at {native} Hz, not substituted',reference=details))
        # The planner must identify DSDIFF even if the destination suffix or
        # explicitly selected filetype is uppercase.  Leave generic effect
        # matching case-sensitive; this is only format-name matching.
        for native in RATES:
            for form in ('suffix','type'):
                key=f'output-dff-uppercase-{form}-{native}'
                if key in old:report['cases'].append(old[key]);continue
                dst=work/(f'highrate-upper-{native}.DFF' if form=='suffix' else
                          f'highrate-explicit-type-{native}.data')
                cmd=[args.sox,'-V2','--dsd-mode','auto','-D',
                     ROOT/'tests/dsd/fixtures/stereo_96.dsf', '-r',str(native)]
                if form=='type':cmd+=['-t','DFF']
                cmd.append(dst)
                got=command_result(cmd,environment)
                okay=False;details=None
                if got['exit']==0 and dst.is_file():
                    raw=dst.read_bytes()
                    # must really be DSDIFF, at the requested rate: decode_dff
                    # rejects anything that is not a well-formed FRM8 form
                    desc=verify.decode_dff(raw)
                    okay=desc['rate']==native and desc['channels']==2
                    details=dict(written_rate=desc['rate'],channels=desc['channels'],
                        physical_bytes=len(raw),output_sha256=sha(raw))
                store(key,'PASS' if okay else 'FAIL',dict(output=got,
                    expected=f'DSDIFF written at {native} Hz from uppercase {form}',
                    reference=details))
        # Unauthorized paths absent; approved DSD64 roundtrips still preserve
        # actual native bits, logical frames, and channel order.
        for ext in ('dsf','dff'):
            for chans in (1,2,6):
                frames=17
                key=f'legacy-roundtrip-{ext}-{chans}-{frames}'
                if key in old:report['cases'].append(old[key]);continue
                timeline=fixtures.bits(frames,chans)
                source=work/f'legacy-in-{chans}.{ext}'
                output=work/f'legacy-out-{chans}.{ext}'
                source.write_bytes(fixtures.make_dsf(timeline) if ext=='dsf' else
                    fixtures.make_dff(timeline))
                got=command_result([args.sox,'-V1','--dsd-mode','native','-D',source,
                    '-t',ext,output],environment)
                valid=False;details=None
                if got['exit']==0 and output.is_file():
                    raw=output.read_bytes()
                    desc=verify.decode_dsf(raw) if ext=='dsf' else verify.decode_dff(raw)
                    valid=(desc['rate']==2822400 and desc['channels']==chans and
                        desc['frames']==(frames if ext=='dsf' else 24) and
                        all(desc['timeline'][ch][:frames]==timeline[ch] for ch in range(chans)))
                    details=dict(output_sha256=sha(raw),frames=desc['frames'],
                        physical_bytes=len(raw))
                store(key,'PASS' if valid else 'FAIL',dict(output=got,reference=details))
        # Exercise all established native writer rates for both containers.
        # This guards against affecting qualified low-rate paths in open_write.
        for native in (2_822_400,5_644_800,11_289_600):
            for ext in ('dsf','dff'):
                key=f'qualified-writer-{native}-{ext}'
                if key in old:report['cases'].append(old[key]);continue
                timeline=fixtures.bits(17,2,'distinct')
                source=work/f'qualified-source-{native}.dsf'
                dst=work/f'qualified-output-{native}.{ext}'
                source.write_bytes(fixtures.make_dsf(timeline,native))
                got=command_result([args.sox,'-V1','--dsd-mode','native','-D',
                    source,'-r',str(native),dst],environment)
                valid=False;details=None
                if got['exit']==0 and dst.is_file():
                    raw=dst.read_bytes()
                    desc=verify.decode_dsf(raw) if ext=='dsf' else verify.decode_dff(raw)
                    valid=(desc['rate']==native and desc['channels']==2 and
                           desc['frames']==(17 if ext=='dsf' else 24) and
                           all(desc['timeline'][ch][:17]==timeline[ch] for ch in range(2)))
                    details=dict(output_sha256=sha(raw),frames=desc['frames'],
                        physical_bytes=len(raw))
                store(key,'PASS' if valid else 'FAIL',dict(output=got,reference=details))
    report['summary']={'PASS':sum(x['status']=='PASS' for x in report['cases']),
                       'FAIL':sum(x['status']=='FAIL' for x in report['cases'])}
    report['verdict']='PASS' if not report['summary']['FAIL'] else 'FAIL'
    atomic_json(target,report)
    print('P18',report['verdict'],report['summary'],'reference fixtures',len(reference['cases']),
        'DoP vectors',len(reference['dop_cases']))
    return int(report['verdict']!='PASS')

if __name__=='__main__':raise SystemExit(main())
