#!/usr/bin/env python3
"""Paired, interleaved packed-vs-expanded benchmark on real DSD material."""
import argparse,os,random,statistics,subprocess,sys,time,json
from pathlib import Path

def run(cmd, env):
    t=time.process_time(); w=time.perf_counter()
    p=subprocess.run(cmd,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    return time.perf_counter()-w, p.returncode, p.stderr

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--file',required=True); ap.add_argument('--reps',type=int,default=21)
    ap.add_argument('--cpu',type=int,default=8); ap.add_argument('--out',required=True)
    a=ap.parse_args()
    f=Path(a.file)
    rate=round(float(subprocess.run(['./src/soxi','-r',str(f)],capture_output=True,text=True).stdout))
    prof={2822400:'decode.mastering.v2.dsd64',5644800:'decode.mastering.v2.dsd128'}.get(rate,'decode.mastering.v2.dsd256')
    out=88200 if rate==2822400 else 176400
    cmd=['taskset','-c',str(a.cpu),'./src/sox','-V1','--dsd-mode','auto','--combine=merge',
         '--dsd-layout-loss','warn','--dsd-decode',prof,'-D',str(f),'-r',str(out),
         '-t','raw','-e','signed-integer','-b','32','/dev/null']
    base=os.environ.copy(); base.update(SOX_OPTS='',OMP_NUM_THREADS='1',LC_ALL='C')
    exp_env=dict(base); exp_env.pop('SOX_DSD_PACKED_INPUT',None)
    pk_env=dict(base); pk_env['SOX_DSD_PACKED_INPUT']='1'
    # warm the page cache for both arms
    for e in (exp_env,pk_env): run(cmd,e)
    E,P=[],[]
    for i in range(a.reps):                       # interleave, alternating order
        order=[(E,exp_env),(P,pk_env)] if i%2==0 else [(P,pk_env),(E,exp_env)]
        for acc,env in order:
            t,rc,err=run(cmd,env)
            if rc!=0: print('FAIL',err.decode()[-300:],file=sys.stderr); sys.exit(1)
            acc.append(t)
        print(f'  rep {i+1}/{a.reps}  exp {E[-1]:.3f}s  packed {P[-1]:.3f}s',flush=True)
    ratios=[e/p for e,p in zip(E,P)]
    rnd=random.Random(20261021)
    boots=sorted(statistics.median(rnd.choices(ratios,k=len(ratios))) for _ in range(20000))
    lo,hi=boots[int(.025*len(boots))],boots[int(.975*len(boots))]
    res=dict(file=f.name,rate=rate,profile=prof,output_hz=out,reps=a.reps,cpu=a.cpu,
             expanded_median_s=round(statistics.median(E),4),
             packed_median_s=round(statistics.median(P),4),
             speedup_median=round(statistics.median(ratios),5),
             speedup_ci95=[round(lo,5),round(hi,5)],
             expanded_spread_pct=round(100*(max(E)-min(E))/statistics.median(E),2),
             packed_spread_pct=round(100*(max(P)-min(P))/statistics.median(P),2),
             faster_than_1x=bool(lo>1.0), slower_than_1x=bool(hi<1.0))
    Path(a.out).write_text(json.dumps(res,indent=2))
    print(json.dumps(res,indent=2))
main()
