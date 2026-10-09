#!/usr/bin/env python3
"""P07 true executable CLI conversion matrix and boundary policy checks.

Includes native rates and supported PCM endpoints, and checks file frame counts
against a separate integer oracle. Results contain no machine-specific paths.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import stat
import subprocess
import tempfile
import time
import wave
from reference import fixtures

RATES=(2822400,5644800,11289600)
PCM=(44100,48000,88200,96000,176400,192000,352800,384000,705600)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--sox',type=Path,required=True)
    parser.add_argument('--results',type=Path,required=True)
    p=parser.parse_args()
    sox=p.sox.resolve()
    rows=[]
    with tempfile.TemporaryDirectory(prefix='p07-') as td:
        path=Path(td)
        native_frames=4097
        def invoke(name,source,rate,profile,extra=(),expect_ok=True,channels=1):
            dest=path/(name+'.wav')
            args=[str(sox),'-D',*extra,str(source),str(dest),'dsdpcm','-p',profile,str(rate)]
            t=time.monotonic()
            cp=subprocess.run(args,capture_output=True,text=True,timeout=45,
                              env={**os.environ,'OMP_NUM_THREADS':'1'})
            row=dict(name=name,phase='P07',status='pass',exit_code=cp.returncode,
                elapsed_ms=round((time.monotonic()-t)*1000,3),
                arguments=['-D',*extra,'INPUT','OUTPUT','dsdpcm','-p',profile,str(rate)])
            try:
                if expect_ok:
                    assert cp.returncode==0,(cp.returncode,cp.stderr[-500:])
                    assert dest.is_file()
                    with wave.open(str(dest),'rb') as out:
                        assert out.getframerate()==rate,(name,out.getframerate(),rate)
                        assert out.getnchannels()==channels,(name,out.getnchannels(),channels)
                        assert out.getnframes()==(native_frames*rate+source_rate//2)//source_rate, \
                            (name,out.getnframes(),native_frames,rate,source_rate)
                        row.update(frames=out.getnframes(),sha256=hashlib.sha256(out.readframes(out.getnframes())).hexdigest())
                else:
                    assert cp.returncode!=0,(name,cp.stderr[-500:])
                    assert not dest.exists(),('partial output left by rejected request',name)
            except Exception as exc:
                row['status']='fail';row['reason']=str(exc)
                print('FAIL',name,str(exc),flush=True)
            rows.append(row)
        for n in RATES:
            source_rate=n
            source=path/f'in_{n}.dsf'
            source.write_bytes(fixtures.make_dsf(fixtures.bits(native_frames,1,'69'),rate=n))
            for r in PCM:
                for profile in ('mastering','wideband'):
                    invoke(f'n{n}_r{r}_{profile}',source,r,profile)
        source_rate=RATES[0]
        source=path/'mono.dsf'
        source.write_bytes(fixtures.make_dsf(fixtures.bits(native_frames,1,'69'),rate=source_rate))
        # Output values must not depend on sample/buffer partitioning.
        invoke('partition_4096',source,705600,'mastering',('--buffer','4096','--single-threaded'))
        invoke('partition_64',source,705600,'mastering',('--buffer','64','--single-threaded'))
        partition=[r for r in rows if r['name'].startswith('partition_')]
        if partition[0].get('sha256')!=partition[1].get('sha256'):
            partition[1]['status']='fail';partition[1]['reason']='chunk partition changes PCM bytes'
        invoke('strict_wide64_reject',source,44100,'wideband',('--dsd-bandwidth','strict'),expect_ok=False)
        invoke('strict_master64_allow',source,44100,'mastering',('--dsd-bandwidth','strict'))
        # Channel clones must have independent histories.
        stereo=path/'stereo.dsf'
        stereo.write_bytes(fixtures.make_dsf(fixtures.bits(native_frames,2,'distinct'),rate=source_rate))
        invoke('stereo_channel_clones',stereo,705600,'wideband',channels=2)
        # Fatal clipping must propagate past downstream effects and eliminate output.
        high=path/'high.dsf'
        high.write_bytes(fixtures.make_dsf(fixtures.bits(32768,1,'ones'),rate=source_rate))
        for ch in (1,2):
            if ch==2:
                high.write_bytes(fixtures.make_dsf(fixtures.bits(32768,2,'ones'),rate=source_rate))
            out=path/f'clip_{ch}.wav'
            args=[str(sox),'--dsd-clip','error','-D',str(high),str(out),
                  'dsdpcm','-l','sacd','88200','gain','-3']
            cp=subprocess.run(args,capture_output=True,text=True,timeout=45,
                              env={**os.environ,'OMP_NUM_THREADS':'1'})
            valid=cp.returncode!=0 and 'clip error' in cp.stderr.lower() and not out.exists()
            rows.append(dict(name=f'fatal_clip_{ch}ch_downstream',phase='P07',
                 status='pass' if valid else 'fail',exit_code=cp.returncode,
                 diagnostic_present='clip error' in cp.stderr.lower(),output_exists=out.exists()))
        # Automatic guard/norm cannot retroactively protect sacd-mode clips.
        for flag in ('-G','--norm'):
            target=path/('reject_'+flag.replace('-','')+'.wav')
            cp=subprocess.run([str(sox),flag,'-D',str(high),str(target),
                               'dsdpcm','-l','sacd','88200'],capture_output=True,
                              text=True,timeout=45)
            passed=(cp.returncode!=0 and not target.exists() and
                    'cannot be combined' in cp.stderr)
            rows.append(dict(name='sacd_reject_'+flag,phase='P07',
                 status='pass' if passed else 'fail',exit_code=cp.returncode,
                 diagnostic_present='cannot be combined' in cp.stderr))
        # IEEE float WAV still crosses the graph int32 boundary.  Its stored
        # floats must be clipped even though the library double API can exceed 1.
        floating=path/'float-graph.wav'
        cp=subprocess.run([str(sox),'--dsd-clip','warn','-D',str(high),
                           '-e','floating-point','-b','32',str(floating),
                           'dsdpcm','-l','sacd','88200'],capture_output=True,
                          text=True,timeout=45)
        peak=0.
        try:
            data=floating.read_bytes()
            pos=12
            while pos+8<=len(data):
                chunk,sz=struct.unpack_from('<4sI',data,pos)
                if chunk==b'data':
                    pcm=data[pos+8:pos+8+sz]
                    peak=max(abs(v[0]) for v in struct.iter_unpack('<f',pcm))
                    break
                pos+=8+sz+(sz&1)
        except Exception:
            peak=float('inf')
        passed=(cp.returncode==0 and peak==1. and
                'clipped' in cp.stderr and floating.is_file())
        rows.append(dict(name='float_writer_graph_boundary',phase='P07',
                         status='pass' if passed else 'fail',exit_code=cp.returncode,
                         output_peak=peak,graph_clip_diagnostic='clipped' in cp.stderr))
        # Parallel clone ownership must be independent of thread count.
        six=path/'six.dsf'
        six.write_bytes(fixtures.make_dsf(fixtures.bits(native_frames,6,'distinct'),rate=source_rate))
        six_hashes=[]
        for threads in ('1','2'):
            dst=path/('six-'+threads+'.wav')
            cp=subprocess.run([str(sox),'-D',str(six),str(dst),
                               'dsdpcm','-p','wideband','705600'],capture_output=True,
                              text=True,timeout=45,env={**os.environ,'OMP_NUM_THREADS':threads})
            six_hashes.append(hashlib.sha256(dst.read_bytes()).hexdigest()
                               if cp.returncode==0 and dst.is_file() else None)
        rows.append(dict(name='six_channel_parallel_identity',phase='P07',
                         status='pass' if six_hashes[0] is not None and
                          six_hashes[0]==six_hashes[1] else 'fail',
                         output_equivalent=six_hashes[0]==six_hashes[1]))
        # Use a *short* stream whose output fits stdio buffering: the large
        # clip fixture can instead fail during output_flow, which is a
        # different gate and must not satisfy this finalization assertion.
        full=Path('/dev/full')
        try:
            original=full.stat()
        except OSError:
            original=None
        if original is not None and stat.S_ISCHR(original.st_mode):
            flush_input=path/'buffered-flush.dsf'
            flush_input.write_bytes(fixtures.make_dsf(
                fixtures.bits(4096,1,'random'),rate=source_rate))
            cp=subprocess.run([str(sox),'-S','-D',str(flush_input),
                               '-t','wav',str(full),'dsdpcm','88200'],
                              capture_output=True,text=True,timeout=45)
            try:
                current=full.stat()
                preserved=(stat.S_ISCHR(current.st_mode) and
                           current.st_rdev==original.st_rdev and
                           current.st_ino==original.st_ino)
            except OSError:
                preserved=False
            diagnostic='finalization failed' in cp.stderr
            valid=(cp.returncode!=0 and diagnostic and preserved and
                   'Done.' not in cp.stderr)
            rows.append(dict(name='buffered_finalization_failure',phase='P07',
                             status='pass' if valid else 'fail',exit_code=cp.returncode,
                             fatal_diagnostic=diagnostic,device_preserved=preserved))
        else:
            rows.append(dict(name='buffered_finalization_failure',phase='P07',
                             status='unrun',reason='/dev/full character device unavailable'))
    failures=[r['name'] for r in rows if r['status']=='fail']
    unrun=[r['name'] for r in rows if r['status']=='unrun']
    summary=dict(schema='sox.dsd.p07.integration.v1',cases=len(rows),
                 pass_count=sum(r['status']=='pass' for r in rows),
                 fail_count=len(failures),unrun_count=len(unrun),
                 failures=failures,unrun=unrun,results=rows)
    p.results.mkdir(parents=True,exist_ok=True)
    dst=p.results/'integration.json'
    tmp=dst.with_suffix('.tmp');tmp.write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n');tmp.replace(dst)
    print(json.dumps(dict(pass_count=summary['pass_count'],fail_count=summary['fail_count'],results='integration.json')))
    return int(bool(failures))

if __name__=='__main__':raise SystemExit(main())
