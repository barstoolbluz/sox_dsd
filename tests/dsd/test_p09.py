#!/usr/bin/env python3
"""P09 independent original-byte coefficient identities and exact-rate unit gate."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2]


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--unit',type=Path,required=True)
    ap.add_argument('--results',type=Path,required=True)
    args=ap.parse_args();args.results.mkdir(parents=True,exist_ok=True)
    expected=json.loads((ROOT/'tests/dsd/reference/p09_original_coefficients.json').read_text())
    records=[]
    kind_map={'clans-4':'legacy.v1', 'sdm-8':'mastering.v1',
              'sdm-6':'diagnostic.sdm6.v1','clans-8':'diagnostic.clans8.v1'}
    with tempfile.TemporaryDirectory() as temp:
        for e in expected['entries']:
            if e['filter'] not in kind_map:continue
            rate=e['rate_hz'];name=e['filter']
            pid=f'encode.{kind_map[name]}.dsd{rate//44100}'
            out=Path(temp)/'coeff.bin'
            cmd=[str(args.unit),'--coeff',pid,str(rate),str(out)]
            p=subprocess.run(cmd,capture_output=True,text=True)
            if p.returncode!=0:raise AssertionError(f'{pid}: rc={p.returncode}: {p.stderr}')
            got=hashlib.sha256(out.read_bytes()).hexdigest()
            if got!=e['sha256_a8_g8']:raise AssertionError((pid,got,e['sha256_a8_g8']))
            records.append(dict(profile_id=pid,sha256_original_coefficient_bits=got,status='pass'))
            # Incorrect/native future rates must never silently select lower ones.
            bad=[rate+44100,22579200]
            for b in bad:
                p=subprocess.run([str(args.unit),'--coeff',pid,str(b),str(out)],capture_output=True)
                if p.returncode==0:raise AssertionError(f'{pid} accepted rate {b}')
        unit=subprocess.run([str(args.unit),'--unit'],capture_output=True,text=True)
        if unit.returncode:raise AssertionError(unit.stderr)
    result=dict(schema='P09/coefficients-and-state/1',passed=len(records),
                failed=0,original='unaltered baseline src/sdm.c raw coefficient doubles',
                coefficient_checks=records,unit_stdout=unit.stdout.strip())
    (args.results/'unit.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(dict(coefficients=result['passed'],unit=unit.stdout.strip())))

if __name__=='__main__':main()
