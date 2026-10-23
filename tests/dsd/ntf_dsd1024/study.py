#!/usr/bin/env python3
"""Reproducible native DSD1024 NTF exploration, never a production change.

Stages: prepare (pristine scratch clone), instrument, stimuli, render,
spectrum and assess. Render is always UNGUARDED diagnostic training; candidate
qualification needs separate candidate-specific guard training and holdout.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

import numpy as np

from model import ROOT, SOURCE, RATE, WORKING, canonical, make_designs, sha

HERE = Path(__file__).resolve().parent
DESIGNS = HERE / 'designs.json'
MARKER = '.NTF1024_DISPOSABLE_COPY_ONLY'
CONTROL = 'encode.mastering.v2.dsd1024'
SCHEMA = 'DSD1024-NTF-native-render/1'


def write_once(path: Path, data: dict) -> None:
    path = Path(path)
    body = canonical(data).encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != body:
            raise RuntimeError('Conflicting immutable evidence: ' + str(path))
        return
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.new-', delete=False) as f:
        tmp = Path(f.name)
        f.write(body)
        f.flush()
        os.fsync(f.fileno())
    try:
        try:
            os.link(tmp, path)
        except FileExistsError:
            if path.read_bytes() != body:
                raise RuntimeError('Concurrent immutable evidence conflict: ' + str(path))
    finally:
        tmp.unlink(missing_ok=True)


def definitions() -> dict:
    on_disk = json.loads(DESIGNS.read_text())
    derived = make_designs()
    # Only IEEE-754 coefficient words, provenance, topology and design names
    # are authoritative identities. The linearized NTF eigensolver is purely
    # descriptive and can differ in its final digits across LAPACK builds.
    # Do not silently allow different coefficients or missing design rows.
    def strip_descriptive(table):
        return {**table, 'designs': {
            k: {name: value for name, value in row.items() if name != 'linearized_ntf'}
            for k, row in table['designs'].items()}}
    if strip_descriptive(on_disk) != strip_descriptive(derived):
        raise RuntimeError('DSD1024 coefficient/provenance catalogue differs from source')
    for key, row in on_disk['designs'].items():
        actual = row['linearized_ntf']
        expected = derived['designs'][key]['linearized_ntf']
        if actual.keys() != expected.keys() or actual.get('note') != expected.get('note'):
            raise RuntimeError('Descriptive NTF fields differ: ' + key)
        for name in actual:
            if name == 'note':
                continue
            a, b = actual[name], expected[name]
            if not (isinstance(a,(float,int)) and isinstance(b,(float,int)) and
                    math.isfinite(a) and math.isfinite(b) and
                    math.isclose(a,b,rel_tol=2e-6,abs_tol=2e-6)):
                raise RuntimeError('Linearized NTF differs materially: '+key+' '+name)
    return on_disk


def check_scratch(checkout: Path) -> None:
    checkout = checkout.resolve()
    if (checkout == ROOT.resolve() or ROOT.resolve().is_relative_to(checkout)
            or checkout.is_relative_to(ROOT.resolve())):
        raise RuntimeError('Refusing to instrument source authority, ancestor or descendant')
    marker = checkout / MARKER
    expected = {'original_sdm_sha256': sha(SOURCE), 'designs_sha256': sha(DESIGNS),
                'warning': 'disposable experimental source tree, never distribute as production source'}
    if not marker.is_file() or json.loads(marker.read_text()) != expected:
        raise RuntimeError('Scratch-copy identity/marker mismatch: ' + str(checkout))
    if not (checkout/'src/sdm.c').is_file():
        raise RuntimeError('Missing disposable sdm.c')


def prepare(checkout: Path) -> None:
    definitions()
    checkout = checkout.resolve()
    if checkout == ROOT.resolve() or checkout.is_relative_to(ROOT.resolve()) or ROOT.resolve().is_relative_to(checkout):
        raise RuntimeError('Scratch must be a fresh independent directory outside source tree')
    if checkout.exists():
        raise RuntimeError('Refuse overwrite or reuse of existing scratch directory')
    # Never use hardlinks: instrumentation must not mutate underlying source.
    shutil.copytree(ROOT, checkout, symlinks=False, ignore=shutil.ignore_patterns(
        '__pycache__', '*.pyc', '.git', '.libs', '.deps', 'autom4te.cache'))
    marker = {'original_sdm_sha256':sha(SOURCE), 'designs_sha256':sha(DESIGNS),
              'warning':'disposable experimental source tree, never distribute as production source'}
    (checkout / MARKER).write_text(canonical(marker))
    print('PREPARED', checkout, flush=True)


def instrument(checkout: Path, registry: Path) -> None:
    design = definitions()
    check_scratch(checkout)
    source = checkout/'src/sdm.c'
    original = source.read_text()
    if sha(source) != sha(SOURCE) or 'ntf_dsd1024_trials.h' in original:
        raise RuntimeError('Already modified/unexpected experimental C source')
    header = ['/* PRIVATE EXPERIMENTAL NTF BINDINGS; NEVER ENABLE AS PRODUCTION. */',
              '#ifndef LSX_NTF_DSD1024_TRIALS_H', '#define LSX_NTF_DSD1024_TRIALS_H',
              'static const sdm_filter_t lsx_ntf_dsd1024_trials[] = {']
    entries = [{'key':'clans-7', 'profile':CONTROL, 'order':7, 'index':None}]
    for key, record in sorted(design['designs'].items()):
        if key == 'clans-7':
            continue  # Never create a second incumbent; run frozen P19 directly.
        n = record['order']
        a = ', '.join(record['a'] + ['0x0.0p+0']*(8-n))
        g = ', '.join(record['g'] + ['0x0.0p+0']*(8-n))
        idx = len(entries)-1
        name = 'ntf1024-'+key
        header.append(f'  {{ {{ {a} }}, {{ {g} }}, {n}, 45158400u, "{name}", 0, 0, 0 }},')
        entries.append({'key':key, 'profile':f'encode.experimental.ntf.{key}.dsd1024',
                        'order':n, 'index':idx})
    header += ['};', '#endif', '']
    anchor = '#include "sdm_p20_candidates.h"'
    if original.count(anchor) != 1:
        raise RuntimeError('Frozen P20 include anchor changed')
    after = original.replace(anchor, anchor + '\n#include "ntf_dsd1024_trials.h"')
    profiles = 'static const sdm_profile_t sdm_profiles[] = {'
    if after.count(profiles) != 1:
        raise RuntimeError('Profile registry structure changed')
    head, tail = after.split(profiles, 1)
    pos = tail.find('\n};')
    if pos < 0:
        raise RuntimeError('Missing profile registry closing brace')
    new = ''.join(f'  {{"{entry["profile"]}", &lsx_ntf_dsd1024_trials[{entry["index"]}], 176400}},\n'
                  for entry in entries[1:])
    changed = head + profiles + tail[:pos] + '\n' + new + tail[pos:]
    header_path = checkout/'src/ntf_dsd1024_trials.h'
    if header_path.exists() or registry.exists():
        raise RuntimeError('Preexisting experimental header/registry; refuse overwrite')
    # Atomicity: ensure all validation before changing the disposable source.
    source.write_text(changed)
    header_path.write_text('\n'.join(header))
    write_once(registry, {'schema':'DSD1024-NTF-registry/1', 'design_sha256':sha(DESIGNS),
                          'original_sdm_sha256':sha(SOURCE), 'experimental_sdm_sha256':sha(source),
                          'experimental_header_sha256':sha(header_path), 'candidates':entries})
    print('INSTRUMENTED', len(entries), 'bindings; production source unchanged', flush=True)


def stimuli(out: Path, stress32: bool) -> None:
    sys.path.insert(0, str(ROOT/'tests/dsd'))
    from diagnose_residual_asymmetry import reference_source
    out.mkdir(parents=True, exist_ok=True)
    _, _, _, main_source = reference_source()
    spec = {}
    def put(name: str, samples: bytes, description: str) -> None:
        file = out/(name+'.f64le')
        if file.is_file() and file.read_bytes() != samples:
            raise RuntimeError('Stimulus changed: '+str(file))
        if not file.is_file():
            with tempfile.NamedTemporaryFile(dir=out,prefix='.stimulus-',delete=False) as f:
                tmp=Path(f.name)
                f.write(samples)
                f.flush()
                os.fsync(f.fileno())
            try:
                try:os.link(tmp,file)
                except FileExistsError:
                    if file.read_bytes()!=samples:
                        raise RuntimeError('Concurrent different stimulus: '+str(file))
            finally:tmp.unlink(missing_ok=True)
        spec[name] = {'sha256':sha(file), 'frames':len(samples)//8, 'source_hz':WORKING,
                      'description':description}
    put('primary', main_source, 'exact original unquantized pre-rounding P10 1.6 s 997Hz -6dB taper')
    if sha(out/'primary.f64le') != 'ca844611f9ba9f7f95428f69927e62c03806ddde21d3e43e8d5b3ab46a95701a':
        raise RuntimeError('F64 control generator drifted from frozen DSD512 receipt')
    sr = WORKING
    n = round(1.2*sr)
    t = np.arange(n, dtype=np.float64)/sr
    def taper(x):
        x=x.copy(); k=round(.025*sr);j=np.arange(k,dtype=np.float64)/k
        w=j*j*j*(10+j*(-15+6*j));x[:k]*=w;x[-k:]*=w[::-1]
        return x
    cases = {
        'hot-997':taper(.95*np.sin(2*np.pi*997*t)),
        'quiet-997':taper(.02*np.sin(2*np.pi*997*t)),
        'tone-20k':taper(.6*np.sin(2*np.pi*20000*t)),
        'tone-40k':taper(.6*np.sin(2*np.pi*40000*t)),
        'silence':np.zeros(n, dtype=np.float64),
        'dc-step':np.where((t>=.15)&(t<.55),.7,np.where((t>=.55)&(t<.95),-.7,0.)).astype('float64'),
        'noise-safe':taper(.4*np.random.default_rng(0x510D512).uniform(-1.,1.,size=n)),
        'multitone':taper(.15*sum(np.sin(2*np.pi*f*t) for f in (53,997,5501,17011))),
    }
    for name, arr in cases.items():
        if not np.isfinite(arr).all() or np.max(abs(arr))>1:
            raise RuntimeError('Invalid source stimulus: '+name)
        put(name, arr.astype('<f8').tobytes(), 'P10 binary64 native test '+name+'; 176400Hz 1.2s')
    if stress32:
        segment = round(4*sr)
        t32 = np.arange(segment, dtype=np.float64)/sr
        def taper32(x):
            x=x.copy(); k=round(.02*sr);j=np.arange(k,dtype=np.float64)/k
            w=j*j*j*(10+j*(-15+6*j));x[:k]*=w;x[-k:]*=w[::-1]
            return x
        rng = np.random.default_rng(20261022)
        arrays = [np.zeros(segment), np.full(segment,.7), np.full(segment,-.7),
                  taper32(.15*sum(np.sin(2*np.pi*f*t32) for f in (53,997,5501,17011))),
                  taper32(.4*rng.uniform(-1,1,segment)),
                  taper32(.8*np.sin(2*np.pi*997*t32)),
                  taper32(.6*np.sin(2*np.pi*20000*t32)), np.zeros(segment)]
        put('stress32', b''.join(a.astype('<f8').tobytes() for a in arrays),
            '32s uninterrupted eight-phase zero/DC/music/noise/tone/zero composite')
    write_once(out/'manifest.json', {'schema':'DSD1024-NTF-stimuli/1', 'cases':spec})
    print('STIMULI', len(spec), 'cases', flush=True)


def load_registry(registry: Path, checkout: Path) -> dict:
    r = json.loads(registry.read_text())
    check_scratch(checkout)
    if (r['design_sha256'] != sha(DESIGNS) or r['original_sdm_sha256'] != sha(SOURCE) or
        r['experimental_sdm_sha256'] != sha(checkout/'src/sdm.c') or
        r['experimental_header_sha256'] != sha(checkout/'src/ntf_dsd1024_trials.h')):
        raise RuntimeError('Experimental source/registry identity mismatch')
    return r


def render_one(key: str, definition: dict, inp: Path, binary: Path, checkout: Path,
               receipt_dir: Path, packed_dir: Path, timeout: float) -> dict:
    receipt_path=receipt_dir/(key+'.json')
    packed_path=packed_dir/(key+'.packed')
    source_digest=sha(inp)
    unit_digest=sha(binary)
    base = {'schema':SCHEMA, 'key':key, 'profile':definition['profile'],
            'input_sha256':source_digest, 'input_frames':inp.stat().st_size//8,
            'unit_sha256':unit_digest, 'design_sha256':sha(DESIGNS),
            'experimental_sdm_sha256':sha(checkout/'src/sdm.c'),
            'experimental_header_sha256':sha(checkout/'src/ntf_dsd1024_trials.h'),
            'native_hz':RATE,'working_hz':WORKING, 'kernel':'scalar','scale':0.5,
            'candidate_qualified':False, 'guard':'training/unbounded experimental'}
    if receipt_path.exists():
        prior=json.loads(receipt_path.read_text())
        if any(prior.get(k) != v for k,v in base.items()):
            raise RuntimeError('Incompatible frozen case receipt '+str(receipt_path))
        if packed_path.exists():
            if sha(packed_path) != prior.get('packed_sha256'):
                raise RuntimeError('Packed artifact differs from receipt '+str(packed_path))
        elif prior.get('packed_sha256'):
            # Reproduce an intentionally discarded packed stream WITHOUT
            # replacing the historical receipt or accepting new output.
            packed_path.parent.mkdir(parents=True,exist_ok=True)
            with tempfile.TemporaryDirectory(prefix='dsd1024-restore-',dir=packed_path.parent) as temp:
                t=Path(temp)
                cmd=[str(binary),'--render',str(WORKING),str(RATE),base['profile'],'.5','training',
                     str(inp),str(t/'bits.packed'),str(t/'report.json')]
                cp=subprocess.run(cmd,cwd=checkout,stdin=subprocess.DEVNULL,
                    capture_output=True,env={**os.environ,'LSX_DSD_SDM_KERNEL':'scalar'},timeout=timeout)
                if (not (t/'bits.packed').is_file() or
                    sha(t/'bits.packed') != prior['packed_sha256'] or
                    (t/'bits.packed').stat().st_size!=prior['packed_bytes'] or
                    cp.returncode != prior['return_code'] or
                    not (t/'report.json').is_file() or
                    {k:v for k,v in json.loads((t/'report.json').read_text()).items() if k!='cpu_seconds'} !=
                    {k:v for k,v in prior['status'].items() if k!='cpu_seconds'}):
                    raise RuntimeError('Replayed packed source does not reproduce frozen evidence: '+key)
                os.link(t/'bits.packed',packed_path)
            print('RESTORED_PACKED',inp.stem,key,flush=True)
        print('REUSED',inp.stem,key,'rc',prior['return_code'], flush=True)
        return prior
    if packed_path.exists():
        raise RuntimeError('Unreceipted output exists: '+str(packed_path))
    receipt_path.parent.mkdir(parents=True,exist_ok=True)
    packed_path.parent.mkdir(parents=True,exist_ok=True)
    # Private ephemeral path prevents a crash from publishing half a packed artifact.
    with tempfile.TemporaryDirectory(prefix='dsd1024-',dir=packed_path.parent) as tmp:
        tp=Path(tmp)
        cmd=[str(binary),'--render',str(WORKING),str(RATE),base['profile'],'.5','training',
             str(inp),str(tp/'bits.packed'),str(tp/'monitor.json')]
        start=time.monotonic()
        timed_out=False
        try:
            cp=subprocess.run(cmd,cwd=checkout,stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                env={**os.environ,'LSX_DSD_SDM_KERNEL':'scalar'},timeout=timeout)
            rc=cp.returncode
            err=cp.stderr.decode(errors='replace')[-1800:]
        except subprocess.TimeoutExpired as exc:
            timed_out=True;rc=124
            err='TIMEOUT: '+str(exc)
        elapsed=time.monotonic()-start
        status=json.loads((tp/'monitor.json').read_text()) if (tp/'monitor.json').is_file() else None
        temp_bits=tp/'bits.packed'
        packed_sha=sha(temp_bits) if temp_bits.exists() else None
        written_size=temp_bits.stat().st_size if temp_bits.exists() else 0
        # Treat nonzero return or absent report as FAIL, retain its forensic receipt.
        expected=(inp.stat().st_size//8)*RATE//WORKING
        if rc==0 and (status is None or status['processed_native_frames'] != expected or
                      status['committed_native_frames'] != expected or
                      status['nonfinite_states'] != 0 or status['failure'] != 0):
            rc=90;err+='; complete-frame or finite-state invariant violated'
        record={**base, 'complete':True,'timed_out':timed_out, 'return_code':rc,
                'elapsed_seconds':elapsed,'stderr_tail':err,'status':status,
                'packed_sha256':packed_sha,'packed_bytes':written_size}
        # Publish bitstream prior to receipt; an interrupted transaction is
        # detectable and refuses retry rather than silently replacing evidence.
        if temp_bits.exists():
            os.link(temp_bits, packed_path)
        write_once(receipt_path,record)
        print('RENDER',inp.stem,key,'rc',rc,'failure',status.get('failure') if status else None,
              'frames',status.get('committed_native_frames') if status else None,
              'seconds',round(elapsed,2),flush=True)
        return record


def render(args: argparse.Namespace) -> None:
    r=load_registry(args.registry,args.checkout)
    if not args.binary.is_file():
        raise RuntimeError('Missing compiled experimental test binary')
    cases={d['key']:d for d in r['candidates']}
    if args.only:
        absent=set(args.only)-set(cases)
        if absent:raise RuntimeError('Unknown candidate: '+str(absent))
        keys=args.only
    else:keys=sorted(cases)
    inp=args.input.resolve()
    if not inp.is_file() or inp.stat().st_size%8:
        raise RuntimeError('Invalid native binary64 input')
    rec=args.receipts.resolve();packed=args.packed.resolve()
    with ThreadPoolExecutor(max_workers=args.jobs) as ex:
        futures={ex.submit(render_one,key,cases[key],inp,args.binary.resolve(),args.checkout.resolve(),
                           rec,packed,args.timeout):key for key in keys}
        for future in as_completed(futures):
            future.result()


def native_pass(receipt: dict) -> tuple[bool, str]:
    st=receipt.get('status')
    if receipt.get('timed_out') or receipt.get('return_code') != 0 or st is None:
        return False, 'native renderer failed/timed out'
    if st.get('status') != 3 or st.get('failure') != 0 or st.get('nonfinite_states') != 0:
        return False, 'nonlinear failure/nonfinite'
    if st.get('monitor_overloads_nominal_half') != 0 or st.get('excursions28') != 0:
        return False, 'nominal overload/28-window excursion'
    if st.get('min_ones28') is None or st.get('max_ones28') is None:
        return False, 'missing bit-run distribution'
    if st['min_ones28'] < 1 or st['max_ones28'] > 27:
        return False, 'degenerate 28-bit window'
    return True, 'short-screen only, not nominal soak or qualification'


def decode_and_spectrum(packed: Path, alternative: bool,
                        tone_hz: float = 997., start_s: float = .4, stop_s: float = 1.2) -> dict:
    from scipy.signal import firwin, upfirdn
    sys.path.insert(0,str(ROOT/'tests/dsd'))
    from p20_audio_compare import coefficients
    sys.path.insert(0,str(ROOT/'tests/dsd/ntf_study'))
    from analyze_renders import BANDS, residual_and_bands, dbfs
    half=coefficients('halfband')
    taps=601 if alternative else 401
    beta=25 if alternative else 22
    last=firwin(taps,176400,fs=705600,window=('kaiser',beta))
    source=np.frombuffer(packed.read_bytes(),dtype=np.uint8)
    arr=np.unpackbits(source,bitorder='big').astype(np.float64)
    arr=arr*2.-1.
    # Seven cascaded 2:1 stages: 45.1584 MHz -> 352800 Hz. The
    # 352.8-kHz output exposes the 100-150-kHz noise-only diagnostic.
    for stage in range(7):
        arr=upfirdn(last if stage==6 else half, arr,down=2)
    data=residual_and_bands(arr,352800,BANDS,windowed=True,
                            tone_hz=tone_hz,window_start_s=start_s,window_stop_s=stop_s)
    groups={'0_40k':BANDS[:2], '40_100k':BANDS[2:5], '100_150k':BANDS[5:7],
            '150_176p4k':BANDS[7:]}
    integrated={name:dbfs(math.sqrt(sum(data['parts'][f'{lo}-{hi}Hz']['rms']**2 for lo,hi in bins)))
                for name,bins in groups.items()}
    return {'schema':'DSD1024-NTF-reconstruction/1', 'spectrum':data,
            'integrated_sine_equivalent_dbfs':integrated,'reconstructed_rate_hz':352800,
            'number_of_2x_decimations':7, 'halfband_taps':len(half),
            'last_fir_taps':taps,'last_fir_beta':beta,
            'note':'Reconstruction of 176.4-kHz source; bands above 88.2-kHz contain noise, not transmitted source fidelity'}


def official_analysis(receipt: dict) -> tuple[float, float, float] | None:
    """Exact, tapered-source-aware frequency/window of an admitted source.

    The primary source has a 0.4--1.2s plateau. The 1.2s tonal
    holdouts have 25-ms tapers and were measured on 0.25--0.95s; the
    interval cannot accidentally include the final taper.
    """
    manifest=json.loads((HERE/'evidence/stimuli-manifest.json').read_text())['cases']
    for name, (freq, start, stop) in {
        'primary': (997., .4, 1.2),
        'tone-20k': (20000., .25, .95),
        'tone-40k': (40000., .25, .95),
        'quiet-997': (997., .25, .95),
    }.items():
        if receipt['input_sha256']==manifest[name]['sha256']:
            if receipt['input_frames'] != manifest[name]['frames']:
                raise RuntimeError('Source digest with incompatible frame count')
            return freq, start, stop
    return None


def spectrum(args: argparse.Namespace) -> None:
    inp=args.packed.resolve();receipt=json.loads(args.receipt.read_text())
    if not inp.is_file() or sha(inp)!=receipt.get('packed_sha256'):
        raise RuntimeError('Packed source absent or mismatch')
    good,reason=native_pass(receipt)
    if not args.allow_unsafe and not good:
        raise RuntimeError('Stability screen failed: '+reason)
    official=official_analysis(receipt)
    if official is None and not args.allow_unsafe:
        raise RuntimeError('Unknown source; cannot publish admissible spectral record')
    freq = args.tone_hz if args.tone_hz is not None else official[0] if official else None
    start = args.window_start if args.window_start is not None else official[1] if official else None
    stop = args.window_stop if args.window_stop is not None else official[2] if official else None
    if any(x is None or not math.isfinite(x) for x in (freq,start,stop)) or not (
            0 < freq < WORKING/2 and 0 <= start < stop and
            stop <= receipt['input_frames']/WORKING):
        raise RuntimeError('Invalid tone analysis frequency/window')
    is_admissible=(official is not None and (freq,start,stop)==official and good)
    if not is_admissible and not args.allow_unsafe:
        raise RuntimeError('Window/frequency excludes or misfits the admitted source plateau')
    result=decode_and_spectrum(inp,args.alternative,freq,start,stop)
    result.update(key=receipt['key'],packed_sha256=sha(inp),
                  render_receipt_sha256=sha(args.receipt),
                  experimental_only=True,candidate_qualified=False,
                  status='screen-passed' if is_admissible else 'UNSAFE_EXPLORATION')
    write_once(args.output,result)
    print('SPECTRUM',receipt['key'],result['integrated_sine_equivalent_dbfs'],flush=True)


def assess(args: argparse.Namespace) -> None:
    designs=definitions()
    manifest=json.loads(args.stimuli_manifest.read_text())['cases']
    if not {'primary', *args.screen_inputs}.issubset(manifest):
        raise RuntimeError('Manifest does not cover all required stimuli')
    screens={}
    inputs=args.screen_inputs
    if not args.historical_r1_only:
        raise RuntimeError('R1 four-case assessment superseded: use r2_screen.py assess; or explicitly --historical-r1-only')
    for key in sorted(designs['designs']):
        rows=[]
        for name in inputs:
            path=args.evidence/'screen'/name/(key+'.json')
            if path.is_file():
                record=json.loads(path.read_text())
                if (record['key'] != key or record['design_sha256'] != sha(DESIGNS) or
                    record['input_sha256']!=manifest[name]['sha256'] or
                    record['input_frames']!=manifest[name]['frames'] or
                    record['native_hz']!=RATE or record['working_hz']!=WORKING):
                    raise RuntimeError('Screen evidence identity mismatch: '+str(path))
                good,reason=native_pass(record)
                rows.append({'case':name,'passed':good,'reason':reason,
                             'receipt_sha256':sha(path),'status':record.get('status')})
        complete=len(rows)==len(inputs)
        passed=complete and all(row['passed'] for row in rows)
        screens[key]={'complete':complete,'passed':passed,'cases':rows}
    primary={}
    for key in sorted(designs['designs']):
        path=args.evidence/'spectra'/(key+'.json')
        if not path.is_file():continue
        s=json.loads(path.read_text())
        render_path=args.evidence/'primary'/(key+'.json')
        if not render_path.is_file():
            raise RuntimeError('Primary render receipt missing: '+str(render_path))
        r=json.loads(render_path.read_text())
        if (s['key']!=key or s['status']!='screen-passed' or
            r['key']!=key or not native_pass(r)[0] or
            r['input_sha256']!=manifest['primary']['sha256'] or
            r['input_frames']!=manifest['primary']['frames'] or
            r['design_sha256']!=sha(DESIGNS) or
            s['packed_sha256']!=r['packed_sha256'] or
            s['render_receipt_sha256']!=sha(render_path)):
            raise RuntimeError('Spectral or primary source identity mismatch: '+str(path))
        primary[key]={'integrated_sine_equivalent_dbfs':s['integrated_sine_equivalent_dbfs'],
                      'receipt_sha256':sha(path)}
    control=primary.get('clans-7')
    winners=[]
    if control:
        c=control['integrated_sine_equivalent_dbfs']
        for key,v in primary.items():
            if key=='clans-7' or not screens[key]['passed']:continue
            m=v['integrated_sine_equivalent_dbfs']
            if (m['0_40k']<=c['0_40k']+1 and m['40_100k']<=c['40_100k']-3
                and m['100_150k']<=c['100_150k']-3):
                winners.append({'key':key, 'delta_db':{band:m[band]-c[band] for band in c}})
    winners.sort(key=lambda x:(x['delta_db']['0_40k'],x['delta_db']['40_100k'],x['key']))
    result={'schema':'DSD1024-NTF-comparison/1','native_hz':RATE,
            'source_hz':WORKING,'incumbent':'clans-7',
            'decisions':{'read_qualification':'Self-generated DSD1024 media NOT accepted as independent read qualification; await external independently-produced material.',
                'selection':'DSD1024 finalist is selected independently of DSD512; no DSD512 automatic transfer.',
                'production':'UNMODIFIED, no candidate authorized',
                'win_rule':'passed all mandatory native screens, <= +1 dB low-band change, >=3 dB lower 40-100k and 100-150k residual; then independent candidate qualification before changing product'},
            'required_screen_inputs':inputs,
            'screen_complete_count':sum(x['complete'] for x in screens.values()),
            'screen_pass_count':sum(x['passed'] for x in screens.values()),
            'candidate_count':len(designs['designs']),'screens':screens,
            'spectral_comparison_count':len(primary),'spectra':primary,
            'research_pareto_candidates':winners,
            'final_product_authorization':'NO: CLANS-7 remains incumbent and only qualified-by-existing-P19 controls until independent gates close; study does not alter production'}
    write_once(args.output,result)
    print('ASSESSED',result['screen_pass_count'],'of',len(screens),
          'spectra',len(primary),'research Pareto', [x['key'] for x in winners],flush=True)


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='task',required=True)
    p0=sub.add_parser('prepare');p0.add_argument('--checkout',required=True,type=Path)
    p1=sub.add_parser('instrument');p1.add_argument('--checkout',required=True,type=Path);p1.add_argument('--registry',required=True,type=Path)
    p2=sub.add_parser('stimuli');p2.add_argument('--directory',required=True,type=Path);p2.add_argument('--stress32',action='store_true')
    p3=sub.add_parser('render');p3.add_argument('--checkout',required=True,type=Path);p3.add_argument('--registry',required=True,type=Path)
    p3.add_argument('--binary',required=True,type=Path);p3.add_argument('--input',required=True,type=Path)
    p3.add_argument('--receipts',required=True,type=Path);p3.add_argument('--packed',required=True,type=Path)
    p3.add_argument('--only',nargs='*');p3.add_argument('--jobs',type=int,default=2);p3.add_argument('--timeout',type=int,default=900)
    p4=sub.add_parser('spectrum');p4.add_argument('--packed',type=Path,required=True)
    p4.add_argument('--receipt',type=Path,required=True);p4.add_argument('--output',type=Path,required=True)
    p4.add_argument('--alternative',action='store_true');p4.add_argument('--allow-unsafe',action='store_true')
    p4.add_argument('--tone-hz',type=float,default=None)
    p4.add_argument('--window-start',type=float,default=None)
    p4.add_argument('--window-stop',type=float,default=None)
    p5=sub.add_parser('assess');p5.add_argument('--evidence',required=True,type=Path);p5.add_argument('--output',required=True,type=Path)
    p5.add_argument('--stimuli-manifest',required=True,type=Path)
    p5.add_argument('--screen-inputs',nargs='+',default=['hot-997','noise-safe','dc-step','silence'])
    p5.add_argument('--historical-r1-only',action='store_true',help='Produce historical R1-only result, NOT a stability-qualified shortlist')
    a=p.parse_args()
    if a.task=='prepare':prepare(a.checkout)
    elif a.task=='instrument':instrument(a.checkout,a.registry)
    elif a.task=='stimuli':stimuli(a.directory,a.stress32)
    elif a.task=='render':
        if a.jobs<1 or a.jobs>8 or a.timeout<1:p.error('Invalid jobs/timeout')
        render(a)
    elif a.task=='spectrum':spectrum(a)
    elif a.task=='assess':assess(a)


if __name__=='__main__':
    try:main()
    except (RuntimeError, ValueError, OSError, KeyError) as e:
        print('DSD1024-STUDY FAIL:',type(e).__name__,str(e),file=sys.stderr)
        raise SystemExit(2)
