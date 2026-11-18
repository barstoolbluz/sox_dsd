#!/usr/bin/env python3
"""Apply all 21 receiver mutations to *isolated fixtures* and prove detection.

Never rewrite or compile an altered production source in the delivery tree.
The 15 production mutants must trip immutable accepted-source attestation,
including faults shared by real CLI, encoder probe and public decoder oracle.
The six reference mutants must independently disagree with exact/window oracles.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import numpy as np
import mpmath as mp
from attestation import expected as pinned, verify as verify_accepted_source
from audited_spectrum import analyze as audited_analysis, BANDS

HERE=Path(__file__).resolve().parent
SOURCE=HERE.parents[2]
PRODUCTION={
 'cert_header_bit','clamp_cli','clamp_lib','close_suppress_cli',
 'close_suppress_core','decoder_core_halfgain','dffpad_cli',
 'dupgain_core','dupgain_file','fenv_guard_off','fir_coeff_center_2m20',
 'fir_coeff_center_ulp','int32_src_lib','naive_round','shift_native_core'
}
BANDPOWER={'bandpower_no_onesided_x2','bandpower_norm_sumw','bandpower_unweighted_dc'}
REFERENCE={'fir_ref_prec53','fir_ref_window_shift','cascade_prec53'}
ALL=PRODUCTION|BANDPOWER|REFERENCE


def demand(condition,why):
    if not condition:raise AssertionError(why)


def apply_patch(root,patch):
    cp=subprocess.run(['patch','--batch','--forward','-p1','-i',str(patch)],
                      cwd=root,capture_output=True,text=True,timeout=10)
    demand(cp.returncode==0,'receiver mutation failed to apply: '+str(patch.name)+
           ' '+cp.stdout[-1000:]+cp.stderr[-1000:])


def imported(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def production_fault(name,patch,work):
    root=work/'source'; pin=pinned()['source_file_sha256']
    for filename in pin:
        target=root/filename;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(SOURCE/filename,target)
    apply_patch(root,patch)
    try:
        verify_accepted_source(root)
    except AssertionError as e:
        demand('accepted production source changed:' in str(e),
               'rejected for unrelated reason '+str(e))
        return 'immutable source-word fingerprint: '+str(e)
    raise AssertionError(name+' escaped production fingerprint')


def bandpower_fault(name,patch,work):
    p=work/'source/tests/pcm64/qualification.py'
    p.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(SOURCE/'tests/pcm64/qualification.py',p)
    apply_patch(work/'source',patch)
    # The perturbation has nonzero weighted DC, nonuniform taper and actual
    # frequency content: every normalization/DC mutant changes a band.
    n=8192;fs=2822400;idx=np.arange(n,dtype=np.float64)
    v=0.07+0.04*idx/n+0.18*np.sin(2*np.pi*997*idx/fs)
    v+=0.027*np.cos(2*np.pi*30011*idx/fs)
    sys.path.insert(0,str(SOURCE/'tests/pcm64'))
    sys.path.insert(0,str(HERE))
    m=imported('mutant_qualification_'+name,p)
    _,measured=m.bandpower(v,fs,30.0)
    _,reference=audited_analysis(v,fs,30.0)
    deviations=[]
    for band in BANDS:
        deviations.append(abs(measured[band]['dbfs']-reference[band]['dbfs']))
    demand(max(deviations)>1e-4, 'mutant spectral bug escaped independent analyzer')
    return f'independent 8192-frame Kaiser reference differs in band dBFS, max delta={max(deviations):.9g}'


def reference_fault(name,patch,work):
    p=work/'source/tests/pcm64/qualification'/('reference_cascade.py' if name=='cascade_prec53' else 'fir_reference.py')
    p.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(SOURCE/'tests/pcm64/qualification'/p.name,p)
    apply_patch(work/'source',patch)
    # The full gate uses the unchanged source, current certified stage fixture
    # and real unmutated compiled C probes. No acceptable external change is
    # injected; the reference implementation alone carries the fault.
    result=work/'results';result.mkdir()
    if name=='cascade_prec53':
        run=[sys.executable,str(p), '--source',str(SOURCE),
             '--exporter',str(SOURCE/'test/dsd_test_p15_src_stage_export'),
             '--src-probe',str(SOURCE/'test/dsd_test_p07_reference'),
             '--cascade-probe',str(SOURCE/'test/pcm64_cascade_probe'),
             '--results',str(result)]
    else:
        run=[sys.executable,str(p),'--source',str(SOURCE),'--results',str(result)]
    env={**os.environ,'PYTHONPATH':os.pathsep.join((str(HERE),str(SOURCE/'tests/dsd'))),
         'OPENBLAS_NUM_THREADS':'1'}
    cp=subprocess.run(run,capture_output=True,text=True,env=env,timeout=180)
    reason=cp.stderr.strip()[-1000:]
    demand(cp.returncode!=0 and
           ('reference' in reason.lower() or 'window' in reason.lower() or
            'phase' in reason.lower() or 'bound' in reason.lower() or
            'disagree' in reason.lower() or 'oracle' in reason.lower()),
           f'{name}: false acceptance or unrelated failure {cp.returncode}: {reason}')
    return 'mutated reference CLI rejected: '+reason


def run_all(mutants,results):
    mutants=Path(mutants).resolve();results=Path(results).resolve()
    verify_accepted_source(SOURCE)
    found={p.stem:p for p in mutants.glob('*.diff')}
    demand(set(found)==ALL,'unexpected or missing 21 receiver mutants')
    rows=[]
    for name,patch in sorted(found.items()):
        with tempfile.TemporaryDirectory(prefix='p08-mut-'+name+'-',dir=results) as t:
            work=Path(t)
            if name in PRODUCTION: reason=production_fault(name,patch,work)
            elif name in BANDPOWER: reason=bandpower_fault(name,patch,work)
            else:reason=reference_fault(name,patch,work)
        rows.append({'mutation':name,'status':'REJECTED',
            'class':'production-source' if name in PRODUCTION else 'reference-window'
            if name in BANDPOWER else 'reference-precision-phase',
            'mutant_patch_sha256':hashlib.sha256(patch.read_bytes()).hexdigest(),
            'detector':reason})
    return {'suite':'p08-receiver-mutation-matrix','status':'PASS',
            'accepted_source_revision':pinned()['accepted_production_revision'],
            'mutations_expected':len(ALL),'mutations_rejected':len(rows),
            'mutations':rows}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--mutants',type=Path,required=True)
    ap.add_argument('--results',type=Path,required=True)
    a=ap.parse_args();a.results.mkdir(parents=True,exist_ok=True)
    try:
        record=run_all(a.mutants,a.results)
        (a.results/'mutation-matrix.json').write_text(json.dumps(record,
            indent=2,sort_keys=True)+'\n')
    except Exception as e:
        (a.results/'mutation-matrix-failure.json').write_text(json.dumps({
            'status':'FAIL','error':f'{type(e).__name__}: {e}'},indent=2)+'\n')
        print(f'FAIL mutation matrix: {type(e).__name__}: {e}',file=sys.stderr)
        return 1
    print(f'PASS mutation matrix: {record["mutations_rejected"]}/21 receiver mutants rejected')
    return 0

if __name__=='__main__':raise SystemExit(main())
