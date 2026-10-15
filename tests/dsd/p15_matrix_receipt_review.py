#!/usr/bin/env python3
"""Offline P15 v1 (54/270/96) or v2 (27/135/48) cross-host review.

Read-only: rechecks the original session binding and per-cell raw data, then
counts *observed* tests across separately captured physical/virtual hosts.
This does NOT ratify a numerical tolerance, all-frequency spectral extrema,
or any physical performance/default-promotion claim. A checksum is not a
trusted signature. Source/binary provenance must be reviewed independently.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import wave

import numpy as np

from p15_matrix_contract import (REQUIRED_TIERS, CROSS_ISA_DETAIL_ENDPOINTS, MATRICES,
                                 make_plan, write_json_atomic)
from p15_matrix_instrument import ROOT, schema_for_matrix, errors, file_hash, impulse_positions
from p15_graph_integration import dsf_payload
from p15_src_spectral import tone_fit, DB_RIPPLE_LIMIT, ALIAS_DB_LIMIT


def check_metric(measured: np.ndarray, expected: np.ndarray, receipt: dict,
                 label: str) -> None:
    observed = errors(measured, expected)
    if set(observed) != set(receipt):
        raise ValueError(label+' missing/extra numerical statistic')
    for key,value in observed.items():
        declared=receipt[key]
        if type(declared) not in (float,int) or not math.isfinite(declared) or not math.isclose(
            value, declared, rel_tol=2e-9, abs_tol=1e-16):
            raise ValueError(label+' statistic does not match raw vectors: '+key)


def f64_hash(arr: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(arr,dtype='<f8').tobytes()).hexdigest()


def check_cell(directory: Path, cell: dict, session: dict) -> dict:
    ident=cell['id']
    row_path=directory/'cells'/(ident+'.json')
    if not row_path.is_file() or not row_path.with_suffix('.sha256').is_file():
        raise ValueError('missing cell row/digest: '+ident)
    if row_path.with_suffix('.sha256').read_text().strip()!=file_hash(row_path):
        raise ValueError('cell digest mismatch: '+ident)
    row=json.loads(row_path.read_text())
    if row.get('schema')!=session['schema'] or row.get('id')!=ident or row.get('qualified') is not False:
        raise ValueError('invalid row identity or unauthorized qualification: '+ident)
    for field in ('native_hz','pcm_hz','profile'):
        if row.get(field)!=cell[field]:
            raise ValueError('wrong cell parameters: '+ident+'/'+field)
    if row.get('frames_native')!=session['frames']:
        raise ValueError('session frame count not bound to row: '+ident)
    final=(session['frames']*cell['pcm_hz']+cell['native_hz']//2)//cell['native_hz']
    if row.get('output_count_exact')!=final or row.get('output_frames_measured')!=final:
        raise ValueError('wrong output frames: '+ident)
    if row.get('status') not in ('DEVELOPMENT_SAMPLE_ONLY',
        'MEASURED_PENDING_INDEPENDENT_SPECTRAL_REVIEW','FAILED_SAMPLED_SRC_ENVELOPE'):
        raise ValueError('unexpected scalar row status: '+ident)

    proof=row.get('raw_receipt')
    if not isinstance(proof,dict) or proof.get('file')!='arrays/'+ident+'.npz':
        raise ValueError('missing or incorrect raw evidence locator: '+ident)
    raw_path=directory/proof['file']
    if not raw_path.is_file() or file_hash(raw_path)!=proof.get('sha256'):
        raise ValueError('raw evidence digest mismatch: '+ident)
    try:
        with np.load(raw_path,allow_pickle=False) as npz:
            if set(npz.files)!=set(proof.get('contents',[])):
                raise ValueError('raw evidence inventory mismatch: '+ident)
            raw={name:npz[name] for name in npz.files}
    except (OSError,KeyError) as exc:
        raise ValueError('unreadable raw evidence: '+ident) from exc
    wanted={'program_signal','program_reference','source_bits','fir_signal',
            'fir_reference','baseline'}
    if not wanted<=raw.keys():
        raise ValueError('missing mandatory numerical vectors: '+ident)
    bits=raw['source_bits']
    if (bits.dtype!=np.uint8 or bits.shape!=(session['frames'],) or
        np.any(bits>1)):
        raise ValueError('invalid native 0/1 chronology: '+ident)
    if hashlib.sha256(bits.tobytes()).hexdigest()!=row['scalar_program']['receipt'][
        'source_bit_chronology_sha256']:
        raise ValueError('source chronology digest mismatch: '+ident)
    signal=raw['program_signal']
    reference=raw['program_reference']
    if signal.shape!=(final,) or reference.shape!=(final,) or signal.dtype!=np.float64:
        raise ValueError('bad scalar numerical vectors: '+ident)
    if f64_hash(signal)!=row['scalar_program']['receipt']['binary64_sha256']:
        raise ValueError('scalar output digest mismatch: '+ident)
    check_metric(signal,reference,row['scalar_program']['metric'],ident+'/program')
    check_metric(raw['fir_signal'],raw['fir_reference'],row['isolated_fir']['metric'],
                 ident+'/fir')
    if f64_hash(raw['fir_signal'])!=row['isolated_fir']['receipt']['binary64_sha256']:
        raise ValueError('FIR output digest mismatch: '+ident)
    if raw['baseline'].shape!=(final,):
        raise ValueError('invalid numeric baseline length: '+ident)
    for pulse in row['pulses']:
        at=pulse['native_impulse_frame']
        prefix='impulse_'+str(at)
        if prefix+'_measured' not in raw or prefix+'_reference' not in raw:
            raise ValueError('missing independent impulse vectors: '+ident)
        check_metric(raw[prefix+'_measured'],raw[prefix+'_reference'],
                     {key:pulse[key] for key in errors(signal,reference)},
                     ident+'/'+prefix)
    tiers={}
    for tier in row.get('cross_isa',[]):
        name=tier.get('tier')
        if name not in REQUIRED_TIERS[1:] or name in tiers:
            raise ValueError('duplicate/invalid forced ISA entry: '+ident)
        status=tier.get('status')
        if status not in ('MEASURED','UNSUPPORTED_ON_THIS_HOST'):
            raise ValueError('unrecognized forced ISA status: '+ident)
        tiers[name]=status
        if status!='MEASURED':
            continue
        program='isa_'+name+'_program';fir='isa_'+name+'_fir'
        if program not in raw or fir not in raw:
            raise ValueError('missing measured forced ISA raw vector: '+ident+'/'+name)
        if raw[program].shape!=signal.shape or f64_hash(raw[program])!=tier[
            'receipt']['binary64_sha256']:
            raise ValueError('forced ISA output/hash mismatch: '+ident+'/'+name)
        check_metric(raw[program],signal,tier['same_cell_scalar_composite'],
                     ident+'/'+name+'/composite')
        check_metric(raw[fir],raw['fir_signal'],tier['scalar_relative_fir'],
                     ident+'/'+name+'/FIR')
        if f64_hash(raw[fir])!=tier['fir_receipt']['binary64_sha256']:
            raise ValueError('forced FIR digest mismatch: '+ident+'/'+name)
        if tier.get('detailed_cross_isa')!=(cell['pcm_hz'] in CROSS_ISA_DETAIL_ENDPOINTS):
            raise ValueError('incorrect selected detailed ISA worklist: '+ident+'/'+name)
        if tier['detailed_cross_isa']:
            seen=set()
            for pulse in tier['impulse_detail']:
                at=pulse['native_impulse_frame']
                if at in seen or at not in impulse_positions(session['frames']):
                    raise ValueError('duplicate/unexpected detailed ISA impulse: '+ident+'/'+name)
                seen.add(at)
                key='isa_'+name+'_impulse_'+str(at)
                if key not in raw:
                    raise ValueError('missing detailed ISA impulse evidence: '+ident+'/'+name)
                check_metric(raw[key],raw['impulse_'+str(at)+'_reference'],
                             pulse['independent_reference'],ident+'/'+name+'/independent_impulse')
                check_metric(raw[key],raw['impulse_'+str(at)+'_measured'],
                             pulse['same_cell_scalar'],ident+'/'+name+'/scalar_impulse')
            if seen!=set(impulse_positions(session['frames'])):
                raise ValueError('incomplete detailed ISA impulse coverage: '+ident+'/'+name)
        elif tier.get('impulse_detail'):
            raise ValueError('unexpected detailed ISA data for unselected cell: '+ident+'/'+name)
    if set(tiers)!=set(session['tiers'])-{'scalar'}:
        raise ValueError('session requested tiers differ from cell: '+ident)

    spectral=row.get('production_src_spectral',{})
    src_raw_verified=False
    if session['src_exporter_sha256'] is not None:
        if spectral.get('result_file')!='src-spectral/'+ident+'.json':
            raise ValueError('missing production SRC receipt: '+ident)
        src_path=directory/spectral['result_file']
        if not src_path.is_file() or file_hash(src_path)!=spectral.get('sha256'):
            raise ValueError('SRC receipt digest mismatch: '+ident)
        src=json.loads(src_path.read_text())
        if src.get('status')!=spectral.get('status') or src.get('passed')!=spectral.get('passed'):
            raise ValueError('SRC summary does not match receipt: '+ident)
        if src.get('status')=='IDENTITY_BYPASS':
            if row['intermediate_hz']!=cell['pcm_hz']:
                raise ValueError('unjustified SRC bypass: '+ident)
            src_raw_verified=True  # no resampler or raw tone invocation exists
        else:
            actual=all(x['pass_ripple'] for x in src['passband']) and all(
                x['pass_alias'] for x in src['aliases'])
            if actual!=src.get('passed') or not src['passband']:
                raise ValueError('incorrect SRC observed pass criteria: '+ident)
            tone_cache={}
            for p in src['passband']+src['aliases']:
                receipt=p['receipt']
                if session['capture_src_raw']:
                    raw_receipt=receipt.get('raw_f64')
                    if not isinstance(raw_receipt,dict):
                        raise ValueError('missing requested raw SRC: '+ident)
                    rel=raw_receipt.get('file','')
                    if not rel.startswith('src-raw/'+ident+'/') or Path(rel).name not in (
                        {f'pass-{i:03}.f64' for i in range(7)} |
                        {f'alias-{i:03}.f64' for i in range(3)}):
                        raise ValueError('invalid SRC raw name: '+ident)
                    file=directory/rel
                    if not file.is_file() or file_hash(file)!=raw_receipt['sha256'] or \
                        file.stat().st_size!=raw_receipt['bytes']:
                        raise ValueError('tampered/missing SRC raw: '+ident)
                    if rel not in tone_cache:
                        tone_cache[rel]=np.fromfile(file,dtype='<f8')
                    original=tone_cache[rel]
                    if original.size!=receipt['output_frames'] or \
                        not np.all(np.isfinite(original)) or \
                        f64_hash(original)!=receipt['binary64_sha256']:
                        raise ValueError('SRC raw binary64 chronology differs: '+ident)
                    is_pass='tone_hz' in p
                    fitted=tone_fit(original,cell['pcm_hz'],
                                    p['tone_hz'] if is_pass else p['output_alias_hz'],
                                    remove=() if is_pass or p['kind']=='input-image-folding'
                                    else (p['source_hz'],))
                    for field,value in fitted.items():
                        claimed=p['measured'][field]
                        if not math.isclose(value,claimed,rel_tol=2e-8,abs_tol=1e-12):
                            raise ValueError('reported SRC tone fit differs from raw F64: '+ident+'/'+field)
                    if is_pass:
                        if p['pass_ripple']!=(abs(fitted['amplitude_db_relative_to_input'])<=DB_RIPPLE_LIMIT):
                            raise ValueError('reported SRC passband decision differs from raw F64: '+ident)
                    elif p['pass_alias']!=(fitted['amplitude_db_relative_to_input']<=ALIAS_DB_LIMIT):
                        raise ValueError('reported SRC alias decision differs from raw F64: '+ident)
            if session['capture_src_raw']:
                src_raw_verified=True
    elif spectral.get('status')!='UNRUN':
        raise ValueError('unrequested private SRC observation: '+ident)
    graph=row.get('production_graph',{})
    if session['graph_executable_sha256'] is not None and graph.get('status')!='PASS':
        raise ValueError('missing actual SoX graph proof: '+ident)
    if session['graph_executable_sha256'] is None and graph.get('status')!='UNRUN':
        raise ValueError('unrequested actual SoX graph observation: '+ident)
    graph_raw_verified=False
    if session.get('capture_graph_raw'):
        wanted={'source.dsf','one_thread_tiny_chunks.wav',
                'two_threads_large_chunks.wav','clipped-with-warning.wav'}
        files={}
        for proof in graph.get('raw_graph',[]):
            rel=proof.get('file','')
            if not rel.startswith('graph-raw/'+ident+'/') or Path(rel).name not in wanted or \
                Path(rel).name in files:
                raise ValueError('invalid/duplicate raw graph path: '+ident)
            file=directory/rel
            if not file.is_file() or file.stat().st_size!=proof.get('bytes') or \
                file_hash(file)!=proof.get('sha256'):
                raise ValueError('missing/changed raw graph file: '+ident)
            files[file.name]=file
        if set(files)!=wanted:
            raise ValueError('incomplete raw SoX graph capture: '+ident)
        source_bits=raw.get('graph_six_channel_bits')
        source_f64=raw.get('graph_six_channel_f64')
        if (source_bits is None or source_f64 is None or
            source_bits.shape!=(session['frames'],6) or
            source_f64.shape!=(final,6) or source_bits.dtype!=np.uint8 or
            np.any(source_bits>1) or not np.array_equal(source_bits[:,0],bits) or
            not np.array_equal(source_bits[:,5],source_bits[:,0]) or
            not np.array_equal(source_f64[:,0],signal)):
            raise ValueError('raw graph native chronology/F64 shape differs: '+ident)
        if files['source.dsf'].read_bytes()!=dsf_payload(source_bits,cell['native_hz']):
            raise ValueError('raw graph DSF differs from claimed native bits: '+ident)
        for result in graph['graph_results']:
            mode=result['mode']
            if mode not in ('one_thread_tiny_chunks','two_threads_large_chunks'):
                raise ValueError('unknown graph partition mode: '+ident)
            audio=files[mode+'.wav']
            if file_hash(audio)!=result['output_pcm_sha256']:
                raise ValueError('graph WAV SHA contradicts actual raw WAV: '+ident)
            with wave.open(str(audio),'rb') as wav:
                if (wav.getframerate()!=cell['pcm_hz'] or wav.getnchannels()!=6 or
                    wav.getsampwidth()!=4 or wav.getnframes()!=final):
                    raise ValueError('graph WAV metadata does not match source: '+ident)
                output=np.frombuffer(wav.readframes(final),dtype='<i4').reshape(final,6).astype(np.int64)
            pcm=np.rint(np.clip(source_f64,-1.,1.)*(2**31-1)).astype(np.int64)
            lsb=int(np.max(np.abs(output-pcm),initial=0))
            if lsb>1 or lsb!=result['maximum_int32_lsb_delta']:
                raise ValueError('raw graph WAV vs native F64 discrepancy: '+ident)
        with wave.open(str(files['clipped-with-warning.wav']),'rb') as wav:
            if wav.getnchannels()!=1 or wav.getsampwidth()!=4:
                raise ValueError('bad clipping-warning WAV layout: '+ident)
            samples=np.frombuffer(wav.readframes(wav.getnframes()),dtype='<i4')
            if not np.any(np.abs(samples.astype(np.int64))>=2**31-1):
                raise ValueError('clipping-warning WAV has no saturated sample: '+ident)
        graph_raw_verified=True
    return dict(
        scalar_measured=row['status']!='FAILED_SAMPLED_SRC_ENVELOPE',
        sampled_src=spectral.get('status') in ('SAMPLED_PASS','IDENTITY_BYPASS'),
        graph=graph.get('status')=='PASS',
        src_raw_verified=src_raw_verified,
        graph_raw_verified=graph_raw_verified,
        full_duration=session['frames']>=262144 and session['src_frames']>=131072,
        tiers=tiers,
        observed_failure=row['status'].startswith('FAILED'),
        native_hz=cell['native_hz'],pcm_hz=cell['pcm_hz'],profile=cell['profile'])


def review(paths: list[Path], matrix: str = 'v1') -> dict:
    if not paths:
        raise ValueError('at least one session is required')
    plan=make_plan(matrix)
    expected={cell['id']:cell for cell in plan['scalar_cells']}
    expected_plan=hashlib.sha256(json.dumps(plan,sort_keys=True).encode()).hexdigest()
    trusted_inputs=None
    sessions=[]
    coverage={ident:[] for ident in expected}
    for i,path in enumerate(paths,1):
        path=path.resolve()
        file=path/'session.json'
        if not file.is_file():
            raise ValueError(f'session {i}: missing original session binding')
        session=json.loads(file.read_text())
        if (session.get('schema')!=schema_for_matrix(matrix) or session.get('worklist_sha256')!=expected_plan or
            session.get('mode') not in ('full','development-subset') or
            not isinstance(session.get('tiers'),list) or not session['tiers'] or
            session['tiers'][0]!='scalar'):
            raise ValueError(f'session {i}: incompatible binding/plan')
        worklist=path/'worklist.json'
        if not worklist.is_file() or json.loads(worklist.read_text())!=json.loads(json.dumps(plan)):
            raise ValueError(f'session {i}: missing/altered original worklist')
        inputs={k:v for k,v in session.get('reference_inputs',{}).items()
                if not k.startswith('src/.libs/')}
        for relative,sha in inputs.items():
            if not relative or relative.startswith('/') or '..' in Path(relative).parts or \
                not (ROOT/relative).is_file() or file_hash(ROOT/relative)!=sha:
                raise ValueError(f'session {i}: source/reference hash mismatch')
        if not inputs or (trusted_inputs is not None and trusted_inputs!=inputs):
            raise ValueError(f'session {i}: conflicting/empty source/reference lineage')
        trusted_inputs=inputs
        if len(session['cells'])!=len(set(session['cells'])) or not set(session['cells'])<=set(expected):
            raise ValueError(f'session {i}: unexpected selected cell IDs')
        for ident in session['cells']:
            coverage[ident].append((i,check_cell(path,expected[ident],session)))
        sessions.append(dict(label=f'session-{i:03}',session_sha256=file_hash(file),
            binary_sha256=session['production_exporter_sha256'],
            selected_cells=len(session['cells']),
            measured_cells=sum(1 for items in coverage.values()
                               for index,_ in items if index==i),
            requested_tiers=session['tiers'],
            mode=session['mode'],
            runtime=session['runtime']))
    required_fir_isa={(x['cell'],x['tier']) for x in plan['release_forced_isa_functional']
                      if x['tier']!='scalar'}
    required_detail={(x['cell'],x['tier']) for x in plan['selected_cross_isa_detail']}
    observed_fir_isa=set();observed_detail=set()
    complete_cells=set();src_cells=set();src_raw_cells=set()
    graph_cells=set();graph_raw_cells=set();failed=set()
    for ident,entries in coverage.items():
        for index,item in entries:
            if item['observed_failure']:
                failed.add(ident)
            if item['scalar_measured'] and item['full_duration']:
                complete_cells.add(ident)
            if item['sampled_src'] and item['full_duration']:
                src_cells.add(ident)
            if item['src_raw_verified'] and item['full_duration']:
                src_raw_cells.add(ident)
            if item['graph'] and item['full_duration']:
                graph_cells.add(ident)
            if item['graph_raw_verified'] and item['full_duration']:
                graph_raw_cells.add(ident)
            for tier,status in item['tiers'].items():
                key=(ident,tier)
                if status=='MEASURED' and item['full_duration']:
                    observed_fir_isa.add(key)
                    if item['pcm_hz'] in CROSS_ISA_DETAIL_ENDPOINTS:
                        observed_detail.add(key)
    required=len(plan['scalar_cells'])
    required_isa=len(required_fir_isa)
    required_detail_count=len(required_detail)
    covered=(len(complete_cells)==required and len(src_cells)==required and
             len(graph_cells)==required and len(observed_fir_isa)==required_isa and
             len(observed_detail)==required_detail_count and not failed)
    return dict(schema=('P15/cross-host-instrument-coverage/1' if matrix=='v1'
                        else 'P15/cross-host-v2-instrument-coverage/1'),
                status='OBSERVATION_COVERAGE_COMPLETE_NOT_RELEASE_CERTIFICATE' if covered else
                       'INCOMPLETE_OR_FAILED_OBSERVATIONS',
                release_gate_closed=False,qualified=False,
                qualification_note='Even complete observation coverage requires independent full composite spectral extrema/coherent-alias proof, justified complete SRC numerical tolerance, physical/corpus gates and external provenance review.',
                sessions=sessions,session_count=len(sessions),
                scalar_full_duration_cells=len(complete_cells),expected_scalar_cells=required,
                sampled_src_full_duration_cells=len(src_cells),
                src_raw_verified_full_duration_cells=len(src_raw_cells),
                graph_full_duration_cells=len(graph_cells),
                graph_raw_verified_full_duration_cells=len(graph_raw_cells),
                forced_isa_full_duration_jobs=len(observed_fir_isa),expected_forced_isa_jobs=required_isa,
                selected_detailed_isa_jobs=len(observed_detail),expected_detailed_jobs=required_detail_count,
                failed_scalar_cells=sorted(failed),
                remaining_scalar_cells=sorted(set(expected)-complete_cells),
                remaining_forced_isa=[dict(cell=a,tier=b) for a,b in sorted(required_fir_isa-observed_fir_isa)],
                remaining_detailed_isa=[dict(cell=a,tier=b) for a,b in sorted(required_detail-observed_detail)],
                full_local_observation_coverage=covered,
                reviewer_sha256=file_hash(Path(__file__)),
                worklist_sha256=expected_plan,
                source_reference_sha256=hashlib.sha256(json.dumps(trusted_inputs,sort_keys=True).encode()).hexdigest())


def main() -> int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--matrix',choices=MATRICES,default='v1',
                    help='review only the separately recorded selected v1 or v2 matrix')
    ap.add_argument('--session',type=Path,required=True,action='append',
                    help='one measured result directory; repeat for each host, in stable order')
    ap.add_argument('--output',type=Path,required=True,
                    help='new JSON path (do not place inside an input session)')
    ap.add_argument('--require-coverage',action='store_true',
                    help='exit 2 until the selected matrix *observation coverage* is complete; not a release certificate')
    args=ap.parse_args()
    try:
        result=review(args.session, args.matrix)
        if any(args.output.resolve().is_relative_to(p.resolve()) for p in args.session):
            raise ValueError('write the cross-host review outside its input session directories')
        if args.output.exists():
            raise ValueError('review output already exists; use a new path')
        write_json_atomic(args.output,result)
        print(json.dumps({k:v for k,v in result.items() if k in
            ('status','session_count','scalar_full_duration_cells','sampled_src_full_duration_cells',
             'graph_full_duration_cells','forced_isa_full_duration_jobs','selected_detailed_isa_jobs',
             'release_gate_closed')},sort_keys=True))
        return 2 if args.require_coverage and not result['full_local_observation_coverage'] else 0
    except (OSError,KeyError,TypeError,ValueError,AssertionError) as exc:
        print('P15 receipt review ERROR: '+str(exc),file=sys.stderr)
        return 1


if __name__=='__main__':
    raise SystemExit(main())
