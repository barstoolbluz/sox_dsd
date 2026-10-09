#!/usr/bin/env python3
"""P07 regression goldens for the unchanged public `rate` effect.

Expected raw-PCM hashes were recorded with the *P06-plus-hotfix* binary before
P07 changes, using the exact same inputs/arguments; no P07 SRC code or P07
output was used to derive them.  Signed-32 raw output excludes WAV metadata.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--sox',type=Path,required=True)
    p.add_argument('--goldens',type=Path,default=ROOT/'tests/dsd/results/P07/numeric/public-rate-goldens.json')
    args=p.parse_args()
    manifest=json.loads(args.goldens.read_text())
    if not manifest.get('all_equivalent') or len(manifest['cases'])!=9:
        raise AssertionError('missing/unqualified P06-plus-hotfix public-rate goldens')
    with tempfile.TemporaryDirectory(prefix='p07-rate-regression-') as td:
        for case in manifest['cases']:
            output=Path(td)/'output.raw'
            cmd=[str(args.sox.resolve()),'-D',str(ROOT/'tests/dsd/fixtures'/case['input']),
                 '-t','raw','-e','signed-integer','-b','32',str(output),
                 'rate',*case['public_rate_options'],str(case['output_hz'])]
            cp=subprocess.run(cmd,capture_output=True,text=True,timeout=45,
                              env={**os.environ,'OMP_NUM_THREADS':'1'})
            if cp.returncode:
                raise AssertionError(f"public rate failed: {case['name']}: {cp.stderr[-250:]}")
            sha=hashlib.sha256(output.read_bytes()).hexdigest()
            if sha!=case['control_sha256'] or output.stat().st_size!=case['pcm_bytes']:
                raise AssertionError(f"public rate changed: {case['name']} SHA={sha}")
    print(f'P07 public rate: {len(manifest["cases"])} P06-hotfix PCM goldens PASS')
    return 0
if __name__=='__main__':raise SystemExit(main())
