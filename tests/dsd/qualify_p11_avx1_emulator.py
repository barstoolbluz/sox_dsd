#!/usr/bin/env python3
"""P11 AVX1-without-AVX2 executable qualification using trap-accurate QEMU TCG.

Unlike a CPUID mask on AVX2 silicon, this CPU model traps AVX2 and FMA.
Checks both FIR and normal SDM in the unit binary and real conversions.
No benchmarking, architecture promotion, or native-silicon claim is made.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import signal
import struct
import subprocess
import tempfile
import wave

ROOT=Path(__file__).resolve().parents[2]

def digest(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

def save(p: Path, value: dict) -> None:
    p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_suffix('.tmp')
    tmp.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
    tmp.replace(p)

def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--qemu',default='qemu-x86_64')
    p.add_argument('--cc',default='cc')
    p.add_argument('--results',type=Path,required=True)
    p.add_argument('--unit',type=Path,default=ROOT/'test/dsd_test_p11')
    p.add_argument('--sox',type=Path,default=ROOT/'src/sox')
    p.add_argument('--candidate',type=Path,default=ROOT/'test/sox_p10_candidate')
    a=p.parse_args()
    a.results.mkdir(parents=True,exist_ok=True)
    dest=a.results/'avx1-no-avx2-replay.json'
    report={'schema':'P11/AVX1-QEMU-qualification/1','status':'UNRUN',
      'note':'Instruction-validation compatibility only. No older-AVX physical host or throughput claim.',
      'checks':[],'errors':[],'limits':[],'commands':[]}
    qemu=shutil.which(a.qemu)
    cc=shutil.which(a.cc)
    missing=[name for name,val in [('qemu-x86_64',qemu),('C compiler',cc),
      ('P11 unit',a.unit.is_file()),('SoX CLI',a.sox.is_file()),
      ('P10 candidate CLI',a.candidate.is_file())] if not val]
    if missing:
        report['limits'].append('Not executed: missing '+', '.join(missing))
        save(dest,report)
        print('UNRUN:',report['limits'][-1])
        return 2
    assert qemu is not None and cc is not None
    report['qemu_version']=subprocess.run([qemu,'--version'],text=True,capture_output=True).stdout.splitlines()[0]
    report['binary_sha256']={k:digest(v) for k,v in [('unit',a.unit),('sox',a.sox),('candidate',a.candidate)]}
    env=dict(os.environ,SOX_OPTS='',OMP_NUM_THREADS='1')
    for name in ('SOX_DSD_KERNEL_FIR','SOX_DSD_KERNEL_SDM','LSX_DSD_FIR_KERNEL','LSX_DSD_SDM_KERNEL'):
        env.pop(name,None)
    def trial(label,argv,expected=0,contains=(),with_env=None,output=None):
        proc=subprocess.run([str(x) for x in argv],cwd=ROOT,
                  capture_output=True,text=True,timeout=300,env=with_env or env)
        row={'check':label,'command':[str(x).replace(str(ROOT),'<tree>') for x in argv],
             'returncode':proc.returncode,'expected':expected,
             'stdout':proc.stdout[-5000:],'stderr':proc.stderr[-5000:]}
        if output is not None and output.is_file():row['output_sha256']=digest(output)
        passed=proc.returncode==expected and all(word in proc.stdout for word in contains)
        if output is not None:passed=passed and output.is_file() and output.stat().st_size>100
        row['status']='PASS' if passed else 'FAIL'
        report['checks'].append(row)
        if not passed:report['errors'].append(label)
        save(dest,report)
        print(label,row['status'],flush=True)
        return row
    with tempfile.TemporaryDirectory(prefix='p11-avx1-qemu-') as td:
        work=Path(td)
        for insn,assembly,expected in (
            ('avx','vaddpd %%ymm1, %%ymm2, %%ymm0',0),
            ('avx2','vpaddq %%ymm1, %%ymm2, %%ymm0',-signal.SIGILL),
            ('fma','vfmadd132pd %%ymm1, %%ymm2, %%ymm0',-signal.SIGILL)):
            src=work/(insn+'.c');exe=work/insn
            src.write_text('int main(void) { __asm__ volatile("'+assembly+'" ::: "ymm0"); return 0; }\n')
            compile_cmd=[cc,'-O0','-mavx','-mno-avx2','-mno-fma',str(src),'-o',str(exe)]
            build=subprocess.run(compile_cmd,capture_output=True,text=True)
            if build.returncode:
                report['errors'].append(insn+' probe compiler: '+build.stderr[-600:])
                save(dest,report);return 1
            trial('SandyBridge '+insn+' trap probe',[qemu,'-cpu','SandyBridge',exe],expected)
        trial('SandyBridge FIR and SDM unit',[qemu,'-cpu','SandyBridge',a.unit],0,
              ('P11 host feature mask=3','PASS FIR tier=avx1','PASS SDM tier=avx1','P11 kernel unit suite PASS'))
        trial('Nehalem scalar/SSE2-only unit',[qemu,'-cpu','Nehalem',a.unit],0,
              ('PASS FIR tier=sse2','PASS SDM tier=sse2','P11 kernel unit suite PASS'))
        for cpu in ('Nehalem','core2duo'):
            trial(cpu+' baseline CLI startup',[qemu,'-cpu',cpu,a.sox,'--version'])
        source=work/'pcm.wav'
        samples=[]
        for i in range(1024):
            x=math.sin(2*math.pi*997*i/88200)
            samples.extend((int(round(0.12*x*(2**31-1))),int(round(0.08*x*(2**31-1)))))
        with wave.open(str(source),'wb') as wav:
            wav.setnchannels(2);wav.setframerate(88200);wav.setsampwidth(4)
            wav.writeframes(struct.pack('<'+'i'*len(samples),*samples))
        for tier in ('scalar','sse2','avx1'):
            opts=dict(env,SOX_DSD_KERNEL_SDM=tier)
            outputs=[]
            for mode,prefix in [('emulated',[qemu,'-cpu','SandyBridge']),('native',[])]:
                target=work/('sdm-'+tier+'-'+mode+'.dsf')
                cmd=[*prefix,a.candidate,'--dsd-mode','auto','--dsd-layout-loss','warn','-D',
                     '--buffer','257','--single-threaded',source,'-r','2822400',target]
                row=trial('SDM '+tier+' '+mode,cmd,with_env=opts,output=target)
                outputs.append(row.get('output_sha256'))
            if outputs[0]!=outputs[1] or None in outputs:
                report['errors'].append('SDM '+tier+' emulated/native hash mismatch')
        input_dsf=work/'sdm-avx1-emulated.dsf'
        for tier in ('scalar','sse2','avx1'):
            opts=dict(env,SOX_DSD_KERNEL_FIR=tier)
            hashes=[]
            for mode,prefix in [('emulated',[qemu,'-cpu','SandyBridge']),('native',[])]:
                target=work/('fir-'+tier+'-'+mode+'.wav')
                cmd=[*prefix,a.sox,'--dsd-mode','auto','-D','--buffer','257','--single-threaded',
                     input_dsf,'-r','88200','-e','signed-integer','-b','32',target]
                row=trial('FIR '+tier+' '+mode,cmd,with_env=opts,output=target)
                hashes.append(row.get('output_sha256'))
            if hashes[0]!=hashes[1] or None in hashes:
                report['errors'].append('FIR '+tier+' emulated/native hash mismatch')
        badenv=dict(env,SOX_DSD_KERNEL_FIR='avx1')
        cmd=[qemu,'-cpu','Nehalem',a.sox,'--dsd-mode','auto','-D',input_dsf,
             '-r','88200',work/'unavailable.wav']
        trial('Nehalem forced FIR AVX1 rejected',cmd,expected=2,with_env=badenv)
        badsdm=dict(env,SOX_DSD_KERNEL_SDM='avx1')
        cmd=[qemu,'-cpu','Nehalem',a.candidate,'--dsd-mode','auto',
             '--dsd-layout-loss','warn','-D',source,'-r','2822400',
             work/'unavailable-sdm.dsf']
        trial('Nehalem forced SDM AVX1 rejected',cmd,expected=2,with_env=badsdm)
    report['status']='PASS' if not report['errors'] and len(report['checks'])==21 else 'FAIL'
    save(dest,report)
    print('P11 QEMU AVX1 replay:',report['status'],len(report['checks']),'checks')
    return 0 if report['status']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())
