#!/usr/bin/env python3
"""Recompile a single changed SRC header's dependants with recorded flags."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--build',type=Path,required=True)
ap.add_argument('--expected-header',required=True)
ap.add_argument('--receipt-name',required=True)
a=ap.parse_args()
b=a.build.resolve();p=b/'build-record.json';record=json.loads(p.read_text())
s=Path(record['source']);h=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
before=json.loads((b/'build-inputs.json').read_text())
changed=[name for name,v in before.items() if h(s/name)!=v]
assert all(name=='src/rate_poly_fir0.h' for name in changed),changed
assert h(s/'src/rate_poly_fir0.h')==a.expected_header
commands=json.loads((b/'compile_commands.json').read_text())
cc=next(c['arguments'] for c in commands if c['file']==str(s/'src/rate.c'))
receipt={'header_before':record['header_sha256']['src/rate_poly_fir0.h'],
         'header_after':a.expected_header,'commands':[],'binaries':{}}
def run(command):
    receipt['commands'].append(command)
    subprocess.run(command,check=True,stdout=subprocess.DEVNULL)
run(cc)
run(['ar','r',str(b/'libsox_ng.a'),str(b/'obj/src__rate.c.o')])
flags=record['cflags'];inc=['-I'+str(b/'src'),'-I'+str(s/'src')]
def link(output,inputs,extra=()):
    run([cc[0],*flags,*inc,*inputs,str(b/'libsox_ng.a'),'-lm',*extra,'-o',str(output)])
    receipt['binaries'][str(output.relative_to(b))]=h(output)
link(b/'sox_ng',[str(b/'obj/src__sox_ng.c.o')])
link(b/'sox_dsd_profile_linkonly',[str(b/'obj/src__sox_ng.c.o')],['-pg'])
for name in record['probes']:
    extra=['-DDSD_OPTIMIZATION=1'] if name=='decode_optimization' else []
    link(b/'test'/('dsd_test_'+name),[str(s/'tests/dsd'/('test_'+name+'.c'))],extra)
assert h(s/'src/rate_poly_fir0.h')==a.expected_header
assert not [name for name,v in before.items() if name!='src/rate_poly_fir0.h' and h(s/name)!=v]
record['header_sha256']['src/rate_poly_fir0.h']=a.expected_header
record['sox_sha256']=h(b/'sox_ng');record['library_sha256']=h(b/'libsox_ng.a')
record['profile_sha256']=h(b/'sox_dsd_profile_linkonly')
record['probe_source_sha256']={name:h(s/'tests/dsd'/('test_'+name+'.c')) for name in record['probes']}
record['probe_binary_sha256']={name:h(b/'test'/('dsd_test_'+name)) for name in record['probes']}
record['header_finalization_receipt']=a.receipt_name
before['src/rate_poly_fir0.h']=a.expected_header
(b/'build-inputs.json').write_text(json.dumps(before,indent=2)+'\n')
(b/a.receipt_name).write_text(json.dumps(receipt,indent=2)+'\n')
p.write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({'status':'PASS','build':str(b),'header':a.expected_header,'sox_sha256':record['sox_sha256']}))
