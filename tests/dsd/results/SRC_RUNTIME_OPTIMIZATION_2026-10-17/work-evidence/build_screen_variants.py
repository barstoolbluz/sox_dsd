#!/usr/bin/env python3
"""Independent source-delta arms; identical baseline objects otherwise."""
from pathlib import Path
import hashlib,json,shutil,subprocess
W=Path('/workspace/scratch/4dd8292178b8');S=W/'sox_ng';B=W/'build-baseline'
DEST=W/'screen-variants';DEST.mkdir(exist_ok=True)
arms={'pair2':{'rate_poly_fir0.h':W/'agent_src/rate_poly_fir0_batch2.h'}}
for name,headers in arms.items():
    d=DEST/name;d.mkdir(exist_ok=True)
    shutil.copytree(S/'src',d/'src',dirs_exist_ok=True)
    for h,p in headers.items():shutil.copyfile(p,d/'src'/h)
    if name=='fifo-reuse':
        p=d/'src/fifo.c';t=p.read_text();old='if (f->begin == f->end)\n    lsx_fifo_clear(f);'
        assert t.count(old)==1;t=t.replace(old,'if (f->begin == f->end)\n    f->begin = f->end = 0;');p.write_text(t)
    unit='fifo.c' if name=='fifo-reuse' else 'rate.c'
    obj=d/('src__'+unit+'.o')
    flags=['-O2','-g','-ffp-contract=off','-I'+str(B/'src'),'-I'+str(d/'src')]
    commands=[['gcc',*flags,'-c',str(d/'src'/unit),'-o',str(obj)]]
    subprocess.run(commands[-1],check=True)
    shutil.copyfile(B/'libsox_ng.a',d/'libsox_ng.a')
    commands.append(['ar','rcs',str(d/'libsox_ng.a'),str(obj)]);subprocess.run(commands[-1],check=True)
    commands.append(['gcc',*flags,str(S/'src/sox_ng.c'),str(d/'libsox_ng.a'),'-lm','-o',str(d/'sox_ng')]);subprocess.run(commands[-1],check=True)
    (d/'build.json').write_text(json.dumps({'name':name,'commands':commands,'binary_sha256':hashlib.sha256((d/'sox_ng').read_bytes()).hexdigest()},indent=2)+'\n')
    print(name,d/'sox_ng',flush=True)
