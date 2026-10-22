#!/usr/bin/env python3
"""P17 source-bound candidate registry, frozen guard and release boundary QA."""
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tests/dsd'))
import generate_p17_qualification_certificates as registry

def need(ok,message):
    if not ok:raise AssertionError(message)

def check():
    expected,macros=registry.generate()
    need(registry.OUT.read_text()==expected,'stale P17 SHA registry')
    need(registry.HEADER.read_text()==macros,'stale P17 macro definitions')
    data=json.loads(expected)
    need(len(data['profiles'])==6,'exactly six source-bound candidates required')
    need(data['release_qualified'] is False and data['release_capabilities_enabled'] is False
        and data['device_claims']==[],'candidate promoted to release')
    for name,record in data['profiles'].items():
        key=registry.digest(record)
        need(data['certificate_sha256'][name]==key,name+' record digest')
        macro='LSX_DSD_P17_'+name.replace('.','_').upper()+'_CERTIFICATE_SHA256'
        need(f'#define {macro} "{key}"' in macros,name+' macro mismatch')
        need(record['qualified'] is False and record['production_capability_enabled'] is False,
             name+' production qualification changed')
        need(record['no_continuum_interval_obligation'] is True,name+' waiver lost')
    frozen=json.loads((ROOT/'tests/dsd/reference/p17_guards.json').read_text())
    p10=json.loads((ROOT/'tests/dsd/reference/p10_guards.json').read_text())
    h=(ROOT/'src/pcmdsd_guards.h').read_text()
    m=re.search(r'lsx_pcmdsd_guards\[5\]\[8\] = \{\n((?:  \{[^\n]+\},\n){5})\};',h)
    need(m is not None,'five exactly sized state guard rows')
    rows=[]
    for row in m.group(1).splitlines():
        values=[float.fromhex(x.strip()) for x in row.strip().strip(',{}').split(',')]
        need(len(values)==8,'incorrect guard width');rows.append(values)
    for i,rate in enumerate((2822400,5644800,11289600)):
        need(rows[i]==p10['profiles'][str(rate)]['bounds'],f'P10 bound {rate} changed')
    for i,rate in enumerate((22579200,45158400)):
        need(rows[i+3]==frozen['profiles'][str(rate)]['bounds'],f'P17 bound {rate} changed')
    need('LSX_PCMDSD_CERTIFICATE_SHA256 "df25a2a11855e8a380cd756cf38769701103338faf36b46271aa3df22bc5157e"' in h,
         'P10 certificate altered')
    code=(ROOT/'src/pcmdsd.c').read_text()
    need('lsx_pcmdsd_guards[3],0,NULL' in code and
         'lsx_pcmdsd_guards[4],0,NULL' in code,
         'high-rate experimental encoder has acquired a release certificate')
    print('P17 registry PASS: six unqualified SHA records, exact five guards, frozen P10')
if __name__=='__main__':
    try:check()
    except (AssertionError,OSError,KeyError,ValueError,RuntimeError) as ex:
        print('P17 registry FAIL:',ex,file=sys.stderr);sys.exit(1)
