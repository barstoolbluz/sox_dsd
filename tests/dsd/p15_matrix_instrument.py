#!/usr/bin/env python3
"""Execute P15's 54-cell *independent* F64 decoder metrology.

Not a release sign-off. Numerical receipts contain complete finite-stage high
precision references, genuine one-bit source/output, linearly isolated
impulses, selected high-precision witnesses and optional cross-ISA comparisons.
Every cell is retained separately for partial reruns. Explicitly distinguish
measurement acceptance, proposal-only tolerances and externally reviewed
spectral/physical/codec obligations. See P15_MATRIX_INSTRUMENT.md.

Examples (from an unmodified configured build):
  make -C test dsd_test_p15_instrument dsd_test_p07_reference
  python3 tests/dsd/p15_matrix_instrument.py \\
    --probe test/dsd_test_p15_instrument \\
    --src-probe test/dsd_test_p07_reference \\
    --results /path/to/new/results --tier scalar
  python3 tests/dsd/p15_matrix_instrument.py ... --resume
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
import os
import platform
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

import numpy as np
import scipy
import mpmath

from p15_matrix_contract import (NATIVE_RATES, PCM_RATES, PROFILES,
                                 REQUIRED_TIERS, CROSS_ISA_DETAIL_ENDPOINTS,
                                 cell_key, make_plan, write_json_atomic)
import p15_numerical_reference as ref
from p15_src_spectral import evaluate as evaluate_src_spectral
from p15_graph_integration import measure as measure_graph

ROOT = Path(__file__).resolve().parents[2]
SPEC = 'P15/independent-3x9x2-instrument/1'
PROBE_RE = re.compile(r'^P15_PROBE_OK native=(\d+) pcm=(\d+) profile=([a-z]+) '
                      r'tier=([a-z0-9]+) channels=(\d+) input=(\d+) output=(\d+) chunk=(\d+) level=(preserve|sacd)$')
# These two error thresholds are P07's *selected* empirically tested composite
# comparison envelopes, NOT a new section 8.6 bound and NOT certified for every
# P15 configuration. Above them FAIL; below them REQUIRE REVIEW until bounded,
# predeclared and independently adjudicated for the actual full matrix.
P07_COMPOSITE_INTERIOR_LIMIT = 2e-9
P07_COMPOSITE_ENDPOINT_LIMIT = 0.0085


def file_hash(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open('rb') as f:
        for data in iter(lambda:f.read(1<<20),b''):
            hasher.update(data)
    return hasher.hexdigest()


def bits_digest(bits: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(bits,dtype=np.uint8).tobytes()).hexdigest()



def inherited_fir_certificate() -> dict:
    """Verify the P06 adaptive high-precision certificate matches exact banks.

    This *reuses* a narrower already-certified mathematical property only:
    native FIR cascade P/S/coherent alias. It cannot certify new SRC output
    choices. The current coefficient values, stage lists and profile limits
    must be the ones P06 certified; reject a stale certificate outright.
    """
    path=ROOT/'tests/dsd/results/P06/numeric/filter-certificate.json'
    if not path.is_file():
        raise ValueError('required P06 FIR spectral certificate is absent')
    certificate=json.loads(path.read_text())
    meta,_=ref.bank_data()
    if certificate.get('schema')!='sox-ng/p06-certificate/1' or \
        certificate.get('summary')!={'banks_passed':4,'failed':0,'profiles_passed':6}:
        raise ValueError('P06 certificate schema or acceptance status mismatch')
    if set(certificate['banks'])!=set(meta['banks']) or \
        set(certificate['profiles'])!=set(meta['profiles']):
        raise ValueError('P06 certified bank/profile set changed')
    for bank,data in meta['banks'].items():
        c=certificate['banks'][bank]
        if c['sha256']!=data['rounded_hex_sha256'] or c['taps']!=data['length'] \
            or not c['passes']:
            raise ValueError('P06 FIR bank does not match certificate: '+bank)
    for profile,data in meta['profiles'].items():
        c=certificate['profiles'][profile]
        for field in ('native_hz','intermediate_hz','factor','pass_hz','stop_hz',
                      'delay_native_frames','phase_native_frames'):
            if c[field]!=data[field]:
                raise ValueError('P06 profile changed since certificate: '+profile+'/'+field)
        if c['stage_banks']!=data['stage_banks'] or not c['passes'] \
            or c['pass_ripple_db']>1e-4 or c['stop_max_db']>-160 or \
            c['coherent_alias_sum_db']>-160:
            raise ValueError('P06 per-profile P/S/alias acceptance differs: '+profile)
    return dict(status='P06_NATIVE_FIR_CERTIFICATE_VERIFIED',
                path='tests/dsd/results/P06/numeric/filter-certificate.json',
                sha256=file_hash(path),six_profiles=6,four_banks=4,
                scope='native FIR only, not final SRC nor new P15 54-cell graph')


def native_bits(frames: int, rate: int, channels: int = 1) -> np.ndarray:
    """Genuine 0/1 first-order encoded synthetic tones, not floating DSD.

    Each channel has distinct deterministic amplitude/frequency; the builder
    does not depend on NumPy's RNG version and never passes synthetic floating
    values to the production decoder as native samples.
    """
    if frames < 0 or channels < 1 or channels > 8 or rate not in NATIVE_RATES:
        raise ValueError('unsupported stimulus configuration')
    times = np.arange(frames,dtype=np.float64)/rate
    out = np.empty((frames,channels),dtype=np.uint8)
    for ch in range(channels):
        desired = (0.22*np.sin(2*np.pi*(997.3+123*ch)*times) +
                   0.055*np.cos(2*np.pi*(4231.7+93*ch)*times))
        error = 0.0
        for t,x in enumerate(desired):
            error += float(x)
            bit = 1 if error >= 0. else 0
            out[t,ch] = bit
            error += -1. if bit else 1.
    return out


def run_probe(binary: Path, *, native: int, pcm: int, profile: str, tier: str,
              stimulus: np.ndarray, chunk: int, level: str = 'preserve',
              timeout: int = 180) -> tuple[np.ndarray,dict]:
    b = np.asarray(stimulus,dtype=np.uint8)
    if b.ndim!=2 or b.shape[1]>8 or b.shape[1]<1 or b.shape[0]>50000000 or np.any(b>1):
        raise ValueError('invalid native one-bit chronology')
    expected = (b.shape[0]*pcm+native//2)//native
    args = [str(binary.resolve()),str(native),str(pcm),profile,tier,
            str(b.shape[1]),str(b.shape[0]),str(chunk),level]
    run = subprocess.run(args,input=np.ascontiguousarray(b).tobytes(),
                         stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout,
                         env={**os.environ,'LC_ALL':'C','OMP_NUM_THREADS':'1'})
    diagnostics = run.stderr.decode('utf-8',errors='replace').strip()
    if run.returncode:
        raise RuntimeError(f'probe exit={run.returncode} stderr={diagnostics[-500:]}')
    lines = diagnostics.splitlines()
    if len(lines)!=1 or not (m:=PROBE_RE.fullmatch(lines[0])):
        raise RuntimeError('probe did not return a single validated P15_PROBE_OK receipt')
    items=m.groups()
    must=(native,pcm,profile,tier,b.shape[1],b.shape[0],expected,chunk,level)
    got=(int(items[0]),int(items[1]),items[2],items[3],int(items[4]),
         int(items[5]),int(items[6]),int(items[7]),items[8])
    if got!=must:
        raise RuntimeError(f'probe selected unexpected configuration: {got} != {must}')
    if len(run.stdout)!=expected*b.shape[1]*8:
        raise RuntimeError('wrong binary64 sample count')
    values=np.frombuffer(run.stdout,dtype='<f8').copy().reshape(expected,b.shape[1])
    if not np.all(np.isfinite(values)):
        raise RuntimeError('nonfinite decoded sample')
    return values,dict(output_frames=expected,channels=b.shape[1],
                       binary64_sha256=hashlib.sha256(run.stdout).hexdigest(),
                       source_bit_chronology_sha256=bits_digest(b),
                       forced_tier_verified=items[3]==tier,level=items[8],
                       exit_code=run.returncode)


def errors(actual: np.ndarray, expected: np.ndarray) -> dict:
    got=np.asarray(actual,dtype=np.longdouble).ravel()
    wanted=np.asarray(expected,dtype=np.longdouble).ravel()
    if got.shape!=wanted.shape or not np.all(np.isfinite(got)) or not np.all(np.isfinite(wanted)):
        raise AssertionError('reference/count/nonfinite discrepancy')
    if not len(got):
        return dict(frames=0,max_abs=0.,rms_abs=0.,interior_max_abs=0.,
                    first_abs=0.,last_abs=0.,ref_peak=0.)
    diff=np.abs(got-wanted)
    edge=max(1,len(got)//10)
    core=diff[edge:-edge] if 2*edge<len(got) else diff
    return dict(frames=len(got),max_abs=float(np.max(diff)),
                rms_abs=float(np.sqrt(np.mean(diff*diff))),
                interior_max_abs=float(np.max(core)),
                first_abs=float(diff[0]),last_abs=float(diff[-1]),
                ref_peak=float(np.max(np.abs(wanted))))


def impulse_positions(frames: int) -> tuple[int,...]:
    if frames<=0:
        return tuple()
    return tuple(sorted(set((0,frames//2,frames-1))))




def one_bit_program_metrology(measured: np.ndarray, pcm_hz: int,
                              native_hz: int) -> dict:
    """Program/noise characterization on actual one-bit first-order sequence.

    This intentionally does not turn a shaped-noise floor into FIR stopband
    attenuation. Fit BOTH known tones and DC, report residual power and
    measured amplitudes without inventing a universal music/SDM THD+N limit.
    """
    out=np.asarray(measured,dtype=np.float64)
    if out.ndim!=1 or len(out)<64 or not np.all(np.isfinite(out)):
        raise ValueError('insufficient one-bit output for program measurement')
    cut=min(len(out)//5, max(1,int(0.001*pcm_hz)))
    if 2*cut>len(out)-48:
        cut=max(1,len(out)//10)
    frames=np.arange(cut,len(out)-cut,dtype=np.float64)
    samples=out[cut:-cut]
    freqs=(997.3,4231.7)
    columns=[np.ones(len(frames))]
    for f in freqs:
        angle=2*np.pi*f*frames/pcm_hz
        columns.extend((np.sin(angle),np.cos(angle)))
    basis=np.column_stack(columns)
    coefficients,_,rank,_=np.linalg.lstsq(basis,samples,rcond=None)
    if rank!=5:
        raise AssertionError('program fit is rank deficient')
    residual=samples-basis@coefficients
    amplitudes=[float(math.hypot(coefficients[1+2*i],coefficients[2+2*i]))
                for i in range(2)]
    return dict(one_bit_input=True,fit_frequency_hz=freqs,
                source_profile='deterministic first-order 0/1 modulated two-tone',
                nominal_analog_peak_amplitudes=[0.22,0.055],
                measured_peak_amplitudes=amplitudes,
                per_tone_gain_delta_db=[20*math.log10(max(a/v,1e-300))
                    for a,v in zip(amplitudes,(0.22,0.055))],
                dc=float(coefficients[0]),
                residual_rms=float(np.sqrt(np.mean(residual*residual))),
                residual_rms_dbfs=20*math.log10(max(float(np.sqrt(np.mean(residual*residual)))*
                    math.sqrt(2),1e-300)),
                peak_binary64=float(np.max(np.abs(out))),
                finite_sample_count=int(len(out)),
                note='measured one-bit program residual; not the -160 dB filter alias ceiling')


def phase_alignment(measured: np.ndarray, reference: np.ndarray, pcm_hz: int,
                    effective_pass_hz: float) -> dict:
    """Compare center-impulse phase against independent finite-chain reference.

    Delay is estimated by a fitted phase slope over 5–80% of actual P_effective;
    do not replace this by a peak-index coincidence test. Distinct SRC
    transition-band windows can differ in magnitude without a timing defect.
    """
    m=np.asarray(measured,dtype=np.float64)
    r=np.asarray(reference,dtype=np.float64)
    if m.ndim!=1 or r.shape!=m.shape or len(m)<32:
        raise ValueError('too little paired native impulse audio for phase fit')
    fft_len=1<<17
    freq=np.fft.rfftfreq(fft_len,1.0/pcm_hz)
    A=np.fft.rfft(m,n=fft_len)
    B=np.fft.rfft(r,n=fft_len)
    acceptable=(freq>=.05*effective_pass_hz)&(freq<=.8*effective_pass_hz)&(
              np.abs(B)>.01*np.max(np.abs(B)))
    if np.count_nonzero(acceptable)<50:
        raise AssertionError('insufficient independent reference phase coverage')
    phase=np.unwrap(np.angle(A[acceptable]/B[acceptable]))
    slope,intercept=np.polyfit(freq[acceptable],phase,deg=1)
    residual=np.max(np.abs(phase-(slope*freq[acceptable]+intercept)))
    delay=-slope*pcm_hz/(2*np.pi)
    return dict(relative_group_delay_pcm_frames=float(delay),
                max_phase_residual_radians=float(residual),
                phase_offset_radians=float(intercept),
                band_hz=[float(.05*effective_pass_hz),float(.8*effective_pass_hz)],
                aligned_to_subsample_0_005=bool(abs(delay)<=.005),
                alias_free_samples=len(m),frequency_bins=int(np.count_nonzero(acceptable)))


def finite_count_edges(probe: Path, cell: dict, family: str) -> list[dict]:
    native,pcm,profile=cell['native_hz'],cell['pcm_hz'],cell['profile']
    meta,_=ref.bank_data()
    D=meta['profiles'][family]['factor']
    counts=sorted({0,1,2,3,D-1,D,D+1,127,257})
    rows=[]
    for count in counts:
        b=np.ones((count,1),dtype=np.uint8)
        got,receipt=run_probe(probe,native=native,pcm=pcm,profile=profile,
                              tier='scalar',stimulus=b,chunk=3)
        _,wanted=ref.reference(b[:,0],family,native,pcm)
        e=errors(got[:,0],wanted)
        if e['frames']!=(count*pcm+native//2)//native:
            raise AssertionError('finite tiny-stream count diverges from native rational clock')
        rows.append(dict(native_frames=count,output_frames=e['frames'],
                         measured_receipt=receipt,numerical_discrepancy=e))
    return rows


def absolute_path_free(data) -> bool:
    """Shallow evidence redaction check, not a general filesystem path parser."""
    if isinstance(data,str):
        return not data.startswith('/') and not re.search(r'[A-Za-z]:\\',data)
    if isinstance(data,list):
        return all(absolute_path_free(x) for x in data)
    if isinstance(data,dict):
        return all(absolute_path_free(v) for v in data.values())
    return True


def make_one_cell(probe: Path, cell: dict, frames: int, src_probe: Path | None = None,
                  *, tiers: tuple[str,...]=('scalar',), arrays: Path | None = None) -> dict:
    """Run actual binary64 scalar cell; ISA comparisons are supplementary."""
    native=cell['native_hz']; pcm=cell['pcm_hz'];profile=cell['profile']
    family=('master' if profile=='mastering' else 'wide')+str(native//44100)
    manifest,_=ref.bank_data()
    front_meta=manifest['profiles'][family]
    rate=front_meta['intermediate_hz']
    bits=native_bits(frames,native)
    raw=dict()
    def run(stimulus,*,tier='scalar',chunk=31):
        got,meta=run_probe(probe,native=native,pcm=pcm,profile=profile,
                           tier=tier,stimulus=stimulus,chunk=chunk)
        return got[:,0],meta
    signal, signal_receipt = run(bits)
    base=np.zeros((frames,1),dtype=np.uint8)
    baseline,base_receipt = run(base)
    _, program_reference=ref.reference(bits[:,0],family,native,pcm)
    program_metrics=errors(signal,program_reference)
    one_bit_measure=(one_bit_program_metrology(signal,pcm,native)
                     if len(signal)>=64 else
                     dict(status='UNRUN_SHORT_DEVELOPMENT_CAPTURE',
                          available_pcm_frames=len(signal),required_frames=64,
                          note='Not evidence of gain/noise stability'))
    # The existing P06 75-digit FIR oracle is required for every native/rate
    # pair. We run it through the public no-SRC profile, once per cell here
    # to make isolated FIR errors distinguishable from SRC filter differences.
    fir_out,fir_receipt=run_probe(probe,native=native,pcm=rate,profile=profile,
                        tier='scalar',stimulus=bits,chunk=127)
    fir_expected=ref.front_end(bits[:,0],family)
    fir_metrics=errors(fir_out[:,0],fir_expected)
    fir_bound=ref.fir_roundoff_bound(family)
    count_edges=finite_count_edges(probe,cell,family)
    fir_mp=ref.front_mp_witness(bits[:,0],family,
                    (0,len(fir_expected)//2,len(fir_expected)-1))
    if fir_metrics['max_abs']>fir_bound:
        raise AssertionError(f'FIR high-precision bound exceeded: {fir_metrics["max_abs"]} > {fir_bound}')
    impulses=[]
    center_phase=None
    raw.update(program_signal=signal,program_reference=np.asarray(program_reference,dtype='<f8'),
               baseline=baseline,source_bits=bits[:,0],fir_signal=fir_out[:,0],
               fir_reference=np.asarray(fir_expected,dtype='<f8'))
    for at in impulse_positions(frames):
        changed=base.copy()
        changed[at,0]=1
        perturbed,receipt=run(changed)
        isolated=(perturbed.astype(np.longdouble)-baseline.astype(np.longdouble))*.5
        _,ideal=ref.reference(bits[:,0],family,native,pcm,impulse_at=at)
        metric=errors(isolated,ideal)
        metric.update(native_impulse_frame=at,receipt=receipt,
                      isolated_impulse_peak=float(np.max(np.abs(isolated))) if len(isolated) else 0.,
                      nominal_peak_output_frame=int(np.argmax(np.abs(ideal))) if len(ideal) else None,
                      actual_peak_output_frame=int(np.argmax(np.abs(isolated))) if len(isolated) else None)
        if at==frames//2 and len(isolated)>=32:
            center_phase=phase_alignment(isolated,ideal,pcm,
                  min(front_meta['pass_hz'],.475*min(rate,pcm))
                  if rate!=pcm else front_meta['pass_hz'])
            metric['relative_phase']=center_phase
            if not center_phase['aligned_to_subsample_0_005']:
                raise AssertionError('scalar end-to-end phase is not aligned to '
                                     'independent centered finite reference')
        impulses.append(metric)
        raw['impulse_'+str(at)+'_measured']=np.asarray(isolated,dtype='<f8')
        raw['impulse_'+str(at)+'_reference']=np.asarray(ideal,dtype='<f8')
    # SRC high-precision witnesses at start, center and final compensated
    # output, including the finite intermediate sequence and end zero padding.
    src_witness=ref.polyphase_mp_witness(fir_expected,rate,pcm,
                  len(signal), (0,len(signal)//2,len(signal)-1))
    # Component/source counts, channel independence and data partition checks.
    # The 6th channel deliberately duplicates the 1st and must agree exactly.
    multiple=native_bits(frames,native,6)
    multiple[:,5]=multiple[:,0]
    multi_small,multi_a=run_probe(probe,native=native,pcm=pcm,profile=profile,
                 tier='scalar',stimulus=multiple,chunk=37)
    multi_large,multi_b=run_probe(probe,native=native,pcm=pcm,profile=profile,
                 tier='scalar',stimulus=multiple,chunk=4096)
    if not np.array_equal(multi_small,multi_large):
        raise AssertionError('six-channel output changed with chunk partition')
    if not np.array_equal(multi_small[:,0],multi_small[:,5]):
        raise AssertionError('cloned one-bit channels disagree')
    if not np.array_equal(multi_small[:,0],signal):
        raise AssertionError('mono versus six-channel source mismatch')
    # The real six-channel int32 graph is independently reviewable against
    # these exact F64 samples, not merely an uninspectable output-file hash.
    raw['graph_six_channel_f64']=np.asarray(multi_small,dtype='<f8')
    raw['graph_six_channel_bits']=np.asarray(multiple,dtype=np.uint8)
    # Six sources are independent first-order encoded 0/1 sequences; check
    # channel c against a separate mono stream, not just clone equality.
    channel_2,mono_2=run(multiple[:,2:3],chunk=113)
    if not np.array_equal(multi_small[:,2],channel_2):
        raise AssertionError('channel isolation failure: channel 2')
    for nc in (2,5):
        member=multiple[:,:nc]
        small,ma=run_probe(probe,native=native,pcm=pcm,profile=profile,
                           tier='scalar',stimulus=member,chunk=1 if nc==5 else 17)
        large,mb=run_probe(probe,native=native,pcm=pcm,profile=profile,
                           tier='scalar',stimulus=member,chunk=8192)
        if not np.array_equal(small,large) or not np.array_equal(small,multi_small[:,:nc]):
            raise AssertionError(f'{nc}-channel partition/ownership mismatch')
    doubled,double_receipt=run_probe(probe,native=native,pcm=pcm,profile=profile,
                             tier='scalar',stimulus=bits,chunk=59,level='sacd')
    if not np.array_equal(doubled[:,0],signal*2):
        raise AssertionError('public decoder SACD level is not exactly twice preserve')
    cross_isa=[]
    for tier in tiers:
        if tier=='scalar':
            continue
        try:
            other,other_receipt=run(bits,tier=tier,chunk=97)
            other_large,large_receipt=run(bits,tier=tier,chunk=4096)
            if not np.array_equal(other,other_large):
                raise AssertionError(tier+' forced-tier count/partition instability')
            # Retain the measured bits, not only their hashes/statistical
            # reductions. An independent reviewer must be able to recompute
            # the detailed tier comparisons without rerunning that machine.
            raw['isa_'+tier+'_program']=np.asarray(other,dtype='<f8')
            # Only the isolated FIR can legitimately use the §8.6 FIR
            # roundoff bound. The downstream private SRC is not entitled
            # to that tolerance merely because it shares its native FIR.
            tier_fir,tier_fir_receipt=run_probe(probe,native=native,pcm=rate,
                        profile=profile,tier=tier,stimulus=bits,chunk=101)
            fir_relative=errors(tier_fir[:,0],fir_out[:,0])
            if fir_relative['max_abs']>fir_bound:
                raise AssertionError(f'{tier} independent FIR error exceeded 8.6: '
                                     f'{fir_relative["max_abs"]} > {fir_bound}')
            raw['isa_'+tier+'_fir']=np.asarray(tier_fir[:,0],dtype='<f8')
            e=errors(other,signal)
            detail=pcm in CROSS_ISA_DETAIL_ENDPOINTS
            impulse_detail=[]
            if detail:
                other_base,_=run(base,tier=tier,chunk=163)
                for at in impulse_positions(frames):
                    changed=base.copy();changed[at,0]=1
                    other_plus,_=run(changed,tier=tier,chunk=173)
                    derived=(other_plus.astype(np.longdouble)-other_base.astype(np.longdouble))*.5
                    raw['isa_'+tier+'_impulse_'+str(at)]=np.asarray(derived,dtype='<f8')
                    ideal=raw['impulse_'+str(at)+'_reference']
                    comparison=dict(native_impulse_frame=at,
                                    independent_reference=errors(derived,ideal),
                                    same_cell_scalar=errors(derived,
                                      raw['impulse_'+str(at)+'_measured']))
                    if at==frames//2 and len(derived)>=32:
                        phase=phase_alignment(derived,
                            raw['impulse_'+str(at)+'_measured'],pcm,
                            min(front_meta['pass_hz'],.475*min(rate,pcm))
                            if rate!=pcm else front_meta['pass_hz'])
                        comparison['scalar_relative_phase']=phase
                        if not phase['aligned_to_subsample_0_005']:
                            raise AssertionError(tier+' nonaligned relative impulse group delay')
                    impulse_detail.append(comparison)
            cross_isa.append(dict(tier=tier,status='MEASURED',
                                  detailed_cross_isa=detail,receipt=other_receipt,
                                  large_chunk_receipt=large_receipt,
                                  same_cell_scalar_composite=e,
                                  composite_tolerance='REQUIRES_SEPARATE_NUMERICAL_ENVELOPE',
                                  scalar_relative_fir=fir_relative,
                                  fir_receipt=tier_fir_receipt,
                                  impulse_detail=impulse_detail,
                                  count_and_chunk_invariant=True))
        except RuntimeError as exc:
            if 'UNSUPPORTED tier=' in str(exc):
                cross_isa.append(dict(tier=tier,status='UNSUPPORTED_ON_THIS_HOST',
                                      reason='real kernel dispatch rejected tier'))
            else:
                raise
    # Candidate P07 end-to-end output discrepancy limits are observational
    # only. One failed candidate bound must be diagnosed, not auto-ratified.
    empiric_ok=(program_metrics['interior_max_abs']<=P07_COMPOSITE_INTERIOR_LIMIT and
                program_metrics['max_abs']<=P07_COMPOSITE_ENDPOINT_LIMIT)
    row=dict(schema=SPEC,id=cell['id'],native_hz=native,pcm_hz=pcm,
             profile=profile,intermediate_hz=rate,frames_native=frames,
             output_count_exact=(frames*pcm+native//2)//native,
             output_frames_measured=len(signal),
             native_fir_certificate='tests/dsd/results/P06/numeric/filter-certificate.json',
             effective_passband_hz=min(front_meta['pass_hz'],
                  .475*min(rate,pcm)) if rate!=pcm else front_meta['pass_hz'],
             scalar_program=dict(receipt=signal_receipt,metric=program_metrics,
                                 stimulus='genuine first-order one-bit encoded two-tone'),
             scalar_baseline=base_receipt,one_bit_program=one_bit_measure,
             isolated_fir=dict(receipt=fir_receipt,roundoff_bound=fir_bound,
                               metric=fir_metrics,mp_witness=fir_mp),
             pulses=impulses,center_impulse_phase=center_phase,
             finite_tiny_streams=count_edges,
             src_reference=ref.src_design_metadata(rate,pcm),
             fractional_src_mp_witness=src_witness,
             channel_and_partition=dict(status='PASS',tested_channels=[1,2,5,6],
                 same_bit_output_two_partitions=True,clone_identity=True,
                 mono_vs_six_same=True,independent_channel_2=True,
                 first_run=multi_a,second_run=multi_b,mono_channel_2=mono_2),
             sacd_level=dict(status='PASS',twice_preserve_binary64_exact=True,
                             receipt=double_receipt),
             cross_isa=cross_isa,reference_type=cell['reference_type'],
             p07_selected_example_limits=dict(interior_abs=P07_COMPOSITE_INTERIOR_LIMIT,
                   full_endpoint_abs=P07_COMPOSITE_ENDPOINT_LIMIT,
                   measured_within_P07_example_limits=empiric_ok,
                   authorization='NOT a per-cell P15 combined-stage certificate'),
             properties=dict(
                exact_output_count='PASS',finite_end_behavior='PASS',
                zero_and_tiny_native_counts='PASS',
                finite_startup_and_drain='MEASURED',
                delay_phase_and_linear_impulses='MEASURED',
                effective_bandwidth='POLICY_VALUE_NOT_INDEPENDENTLY_FULL_SPECTRAL_CERTIFIED',
                passband_and_stopband_response='NATIVE_FIR_PASS_INHERITED_P06; SRC_SAMPLED_ONLY',
                coherent_alias_families='NATIVE_FIR_PASS_INHERITED_P06; SRC_IMAGES_SAMPLED_ONLY',
                high_precision_fir='PASS',
                combined_fractional_src_error='MEASURED_REQUIRES_ADJUDICATED_ENVELOPE',
                one_bit_gain_noise=('MEASURED_SEPARATELY_NOT_CERTIFIED'
                    if len(signal)>=64 else 'UNRUN_SHORT_DEVELOPMENT_CAPTURE'),
                level_preserve_vs_sacd='PASS',
                channel_buffer_invariance='PASS',
                real_threaded_graph_invariance='REQUIRES_CLI_INTEGRATION_EVIDENCE',
                graph_clipping_policy='REQUIRES_CLI_INTEGRATION_EVIDENCE'),
             status=('MEASURED_PENDING_INDEPENDENT_SPECTRAL_REVIEW'
                     if frames>=262144 else 'DEVELOPMENT_SAMPLE_ONLY'),
             qualified=False)
    if arrays is not None:
        arrays.mkdir(parents=True,exist_ok=True)
        dest=arrays/(cell['id']+'.npz')
        # Write complete raw numerical vectors with reproducible input hashes.
        with tempfile.NamedTemporaryFile(dir=arrays,prefix=dest.name+'.',suffix='.tmp',delete=False) as f:
            tmp=Path(f.name)
            try:
                np.savez_compressed(f,**raw)
                f.flush()
                os.fsync(f.fileno())
            except BaseException:
                tmp.unlink(missing_ok=True)
                raise
        os.replace(tmp,dest)
        row['raw_receipt']=dict(file='arrays/'+dest.name,
                                sha256=file_hash(dest),
                                contents=sorted(raw))
    if not absolute_path_free(row):
        raise AssertionError('machine-specific path leaked into metrology receipt')
    return row


def write_digest_atomic(target: Path) -> None:
    """Bind a complete cell record, separately from its raw/spectral hashes.

    This detects accidental/manual corruption but is NOT an external
    cryptographic signature or authorization for changing release status.
    """
    sibling=target.with_suffix('.sha256')
    fd,name=tempfile.mkstemp(dir=target.parent,prefix=target.name+'.',suffix='.digest.tmp')
    try:
        with os.fdopen(fd,'w',encoding='ascii') as f:
            f.write(file_hash(target)+'\n')
            f.flush();os.fsync(f.fileno())
        os.replace(name,sibling)
    finally:
        if os.path.exists(name):os.unlink(name)


def execute(options: argparse.Namespace) -> int:
    output=options.results.resolve()
    if np.finfo(np.longdouble).eps >= np.finfo(np.float64).eps:
        raise ValueError('this host has no extra-precision longdouble; install an independent mpmath long-file engine before certifying')
    if not options.probe.is_file():
        raise ValueError('build the P15 binary64 C probe first')
    if options.src_probe and not options.src_probe.is_file():
        raise ValueError('selected private SRC probe is missing')
    if options.sox and not options.sox.is_file():
        raise ValueError('optional SoX graph executable is missing')
    if options.capture_src_raw and not options.src_probe:
        raise ValueError('--capture-src-raw requires --src-probe')
    if options.capture_graph_raw and not options.sox:
        raise ValueError('--capture-graph-raw requires --sox')
    if options.require_all_observations:
        if (options.src_probe is None or options.sox is None or
            options.frames < 262144 or options.src_frames < 131072 or
            any(x is not None for x in (options.native,options.pcm,options.profile))):
            raise ValueError('--require-all-observations requires all 54 cells, '
                '--src-probe, --sox, >=262144 native frames and >=131072 SRC frames')
    front_certificate=inherited_fir_certificate()
    plan=make_plan()
    cells=[x for x in plan['scalar_cells'] if
           (options.native is None or x['native_hz']==options.native) and
           (options.pcm is None or x['pcm_hz']==options.pcm) and
           (options.profile is None or x['profile']==options.profile)]
    if not cells:
        raise ValueError('no matrix rows match filters')
    if output.exists() and any(output.iterdir()) and not options.resume:
        raise ValueError('results directory nonempty: use --resume or a new directory')
    output.mkdir(parents=True,exist_ok=True)
    # Prevent two resumptions from concurrently replacing the same cell files.
    # POSIX advisory lock is held by the open handle through the whole run.
    lock_fp=(output/'.p15-instrument.lock').open('a+b')
    try:
        fcntl.flock(lock_fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock_fp.close()
        raise ValueError('another P15 matrix writer holds the results directory lock')
    try:
        cellsdir=output/'cells';arraysdir=output/'arrays';spectradir=output/'src-spectral'
        cellsdir.mkdir(exist_ok=True)
        spectradir.mkdir(exist_ok=True)
        refs=ref.reference_input_hashes()
        refs['tests/dsd/p15_matrix_instrument.py']=file_hash(Path(__file__))
        refs['tests/dsd/p15_matrix_contract.py']=file_hash(ROOT/'tests/dsd/p15_matrix_contract.py')
        refs['tests/dsd/certify_filters.py']=file_hash(ROOT/'tests/dsd/certify_filters.py')
        refs['tests/dsd/reference/fixtures.py']=file_hash(ROOT/'tests/dsd/reference/fixtures.py')
        refs['tests/dsd/p15_src_spectral.py']=file_hash(ROOT/'tests/dsd/p15_src_spectral.py')
        refs['tests/dsd/test_p15_instrument.c']=file_hash(ROOT/'tests/dsd/test_p15_instrument.c')
        refs['tests/dsd/p15_graph_integration.py']=file_hash(ROOT/'tests/dsd/p15_graph_integration.py')
        refs['tests/dsd/test_p07_reference.c']=file_hash(ROOT/'tests/dsd/test_p07_reference.c')
        for name in ('src/dsd_decode.c','src/dsd_public.c','src/rate.c','src/dsd_dispatch.c',
                     'src/dsd_kernels_scalar.c','src/dsd_plan.c'):
            refs[name]=file_hash(ROOT/name)
        archive=ROOT/'src/.libs/libsox_ng.a'
        if archive.is_file():
            refs['src/.libs/libsox_ng.a']=file_hash(archive)
        runtime=dict(python=platform.python_version(),machine_arch=platform.machine(),
                     numpy=np.__version__,scipy=scipy.__version__,
                     mpmath=mpmath.__version__,
                     longdouble_epsilon=float(np.finfo(np.longdouble).eps),
                     public_f64_byteorder=sys.byteorder)
        bind=dict(runtime=runtime,schema=SPEC,mode='full' if options.frames>=262144 else 'development-subset',
                  frames=options.frames,src_frames=options.src_frames,tiers=list(options.tiers),
                  capture_src_raw=options.capture_src_raw,
                  capture_graph_raw=options.capture_graph_raw,
                  cells=[c['id'] for c in cells],
                  reference_inputs=refs,verified_p06_fir_certificate=front_certificate,
                  production_exporter_sha256=file_hash(options.probe),
                  src_exporter_sha256=file_hash(options.src_probe) if options.src_probe else None,
                  graph_executable_sha256=file_hash(options.sox) if options.sox else None,
                  worklist_sha256=hashlib.sha256(
                      json.dumps(plan,sort_keys=True).encode()).hexdigest())
        target=output/'session.json'
        if options.resume and not target.is_file():
            raise ValueError('cannot resume missing original session.json; '
                             'use a new directory and acquire fresh evidence')
        if target.exists():
            existing=json.loads(target.read_text())
            if existing!=bind:
                raise ValueError('resume binding mismatch (source/config/binary or selected cells changed)')
        else:
            write_json_atomic(target,bind)
        worklist=output/'worklist.json'
        if options.resume:
            # The Python worklist contains tuples for immutable test sets;
            # canonical JSON represents these as arrays.
            if not worklist.is_file() or json.loads(worklist.read_text())!=json.loads(json.dumps(plan)):
                raise ValueError('resume missing or altered original worklist.json')
        else:
            write_json_atomic(worklist,plan)
        failures=[];measured=0;completed=[]
        for i,cell in enumerate(cells,1):
            target=cellsdir/(cell['id']+'.json')
            if target.exists() and options.resume:
                digest=target.with_suffix('.sha256')
                if not digest.is_file() or digest.read_text().strip()!=file_hash(target):
                    raise ValueError('tampered/missing signed-off cell content hash: '+cell['id'])
                stored=json.loads(target.read_text())
                if stored.get('qualified') is not False or stored.get('status') not in (
                    'MEASURED_PENDING_INDEPENDENT_SPECTRAL_REVIEW',
                    'DEVELOPMENT_SAMPLE_ONLY','FAILED_SAMPLED_SRC_ENVELOPE'):
                    raise ValueError('resumed row contains an unauthorized release status')
                receipt=stored.get('raw_receipt')
                if not isinstance(receipt,dict) or \
                    receipt.get('file')!='arrays/'+cell['id']+'.npz':
                    raise ValueError('missing/invalid raw receipt relative locator')
                rfile=output/receipt['file']
                if not rfile.is_file() or file_hash(rfile)!=receipt['sha256']:
                    raise ValueError('tampered/missing raw numerical receipt: '+cell['id'])
                spectrum=stored.get('production_src_spectral',{})
                if options.src_probe and not spectrum.get('result_file'):
                    raise ValueError('missing required SRC measurement receipt: '+cell['id'])
                if options.sox and stored.get('production_graph',{}).get('status')!='PASS':
                    raise ValueError('missing required real graph measurement receipt: '+cell['id'])
                if options.capture_graph_raw:
                    for receipt in stored.get('production_graph',{}).get('raw_graph',[]):
                        name=receipt.get('file','')
                        if not name.startswith('graph-raw/'+cell['id']+'/') or \
                            Path(name).name not in {'source.dsf',
                                'one_thread_tiny_chunks.wav','two_threads_large_chunks.wav',
                                'clipped-with-warning.wav'}:
                            raise ValueError('invalid graph raw receipt locator: '+cell['id'])
                        file=output/name
                        if not file.is_file() or file_hash(file)!=receipt.get('sha256') or \
                            file.stat().st_size!=receipt.get('bytes'):
                            raise ValueError('tampered/missing raw graph recording: '+cell['id'])
                    if len(stored.get('production_graph',{}).get('raw_graph',[]))!=4:
                        raise ValueError('missing requested graph raw recordings: '+cell['id'])
                if spectrum.get('result_file'):
                    if spectrum.get('result_file')!='src-spectral/'+cell['id']+'.json':
                        raise ValueError('invalid SRC receipt relative locator')
                    sp=output/spectrum['result_file']
                    if not sp.is_file() or file_hash(sp)!=spectrum['sha256']:
                        raise ValueError('tampered/missing private SRC spectrum: '+cell['id'])
                    sampled=json.loads(sp.read_text())
                    for sampled_row in sampled.get('passband',[])+sampled.get('aliases',[]):
                        raw=sampled_row.get('receipt',{}).get('raw_f64')
                        if raw is None:
                            if options.capture_src_raw and sampled['status']!='IDENTITY_BYPASS':
                                raise ValueError('missing requested SRC raw evidence')
                            continue
                        sub='src-raw/'+cell['id']+'/'
                        if not raw.get('file','').startswith(sub) or \
                            Path(raw['file']).name not in {'pass-%03d.f64'%i for i in range(7)} | \
                            {'alias-%03d.f64'%i for i in range(3)}:
                            raise ValueError('invalid per-tone raw receipt locator')
                        b=output/raw['file']
                        if not b.is_file() or b.stat().st_size!=raw.get('bytes') or file_hash(b)!=raw['sha256']:
                            raise ValueError('tampered/missing SRC raw tone: '+cell['id'])
                if stored.get('schema')!=SPEC or stored.get('id')!=cell['id']:
                    raise ValueError('wrong existing row: '+cell['id'])
                if {t.get('tier') for t in stored.get('cross_isa',[])}!=set(options.tiers)-{'scalar'}:
                    raise ValueError('missing/changed forced ISA observation: '+cell['id'])
                print(f'RESUME {i}/{len(cells)} {cell["id"]}',flush=True)
                measured+=1
                completed.append(stored)
                if stored.get('status','').startswith('FAILED'):
                    failures.append(dict(cell=cell['id'],type='PreviousNumericalFailure',error=stored['status']))
                continue
            print(f'RUN {i}/{len(cells)} {cell["id"]}',flush=True)
            try:
                row=make_one_cell(options.probe,cell,options.frames,options.src_probe,
                             tiers=options.tiers,arrays=arraysdir)
                if options.src_probe:
                    spectrum=spectradir/(cell['id']+'.json')
                    # Orphaned results from a partially committed cell are
                    # untrusted: re-measure rather than adopt them on resume.
                    sampled=evaluate_src_spectral(options.src_probe,row['intermediate_hz'],
                              cell['pcm_hz'],row['effective_passband_hz'],frames=options.src_frames,
                              raw_dir=(output/'src-raw'/cell['id']) if options.capture_src_raw else None,
                              raw_prefix=('src-raw/'+cell['id']) if options.capture_src_raw else None)
                    write_json_atomic(spectrum,sampled)
                    row['production_src_spectral']=dict(
                        status=sampled['status'],passed=sampled['passed'],
                        result_file='src-spectral/'+spectrum.name,
                        sha256=file_hash(spectrum),checks=sampled['checks'])
                    row['properties']['src_selected_passband_images']=(
                        'SAMPLED_PASS_NOT_COMPLETE_EXTREMA' if sampled['passed'] else 'SAMPLED_FAIL')
                    if not sampled['passed']:
                        row['status']='FAILED_SAMPLED_SRC_ENVELOPE'
                else:
                    row['production_src_spectral']=dict(status='UNRUN',
                        reason='--src-probe not supplied')
                    row['properties']['src_selected_passband_images']='UNRUN'
                if options.sox:
                    b=native_bits(options.frames,cell['native_hz'],6)
                    b[:,5]=b[:,0]  # same chronology as saved six-channel F64 reference
                    got,_=run_probe(options.probe,native=cell['native_hz'],pcm=cell['pcm_hz'],
                                    profile=cell['profile'],tier='scalar',stimulus=b,chunk=71)
                    report=measure_graph(options.sox,cell['native_hz'],cell['pcm_hz'],
                                         cell['profile'],b,reference_f64=got,
                                         raw_dir=(output/'graph-raw'/cell['id']) if options.capture_graph_raw else None,
                                         raw_prefix=('graph-raw/'+cell['id']) if options.capture_graph_raw else None)
                    row['production_graph']=report
                    row['properties']['real_threaded_graph_invariance']='PASS'
                    row['properties']['graph_clipping_policy']='PASS'
                else:
                    row['production_graph']=dict(status='UNRUN',
                        reason='--sox not supplied for real multithreaded graph/clip tests')
                write_json_atomic(target,row)
                write_digest_atomic(target)
                measured+=1
                completed.append(row)
                print(f'MEASURED {cell["id"]}: independent composite max '
                      f'{row["scalar_program"]["metric"]["max_abs"]:.5g}',flush=True)
                if row['status'].startswith('FAILED'):
                    failures.append(dict(cell=cell['id'],type='NumericalEnvelope',error=row['status']))
            except Exception as error:
                failures.append(dict(cell=cell['id'],type=type(error).__name__,error=str(error)[:800]))
                print(f'FAIL {cell["id"]}: {type(error).__name__}: {str(error)[:400]}',
                      file=sys.stderr,flush=True)
                write_json_atomic(cellsdir/(cell['id']+'.failure.json'),failures[-1])
                if options.stop_on_fail:
                    break
        src_observed=sum(x.get('production_src_spectral',{}).get('status') in
                         ('SAMPLED_PASS','IDENTITY_BYPASS') for x in completed)
        graph_observed=sum(x.get('production_graph',{}).get('status')=='PASS'
                           for x in completed)
        tier_measured=sum(t.get('status')=='MEASURED' for x in completed
                          for t in x.get('cross_isa',[]))
        tier_unsupported=sum(t.get('status')=='UNSUPPORTED_ON_THIS_HOST'
                            for x in completed for t in x.get('cross_isa',[]))
        all_observed=(len(cells)==54 and measured==54 and not failures and
                      src_observed==54 and graph_observed==54 and
                      options.frames>=262144 and options.src_frames>=131072)
        summary=dict(schema=SPEC,status='INCOMPLETE' if failures or measured<len(cells)
                     else ('DEVELOPMENT_SAMPLE_ONLY' if options.frames<262144 or options.src_frames<131072
                           else ('MEASURED_PENDING_INDEPENDENT_SPECTRAL_REVIEW' if all_observed
                                 else 'INCOMPLETE_OBSERVATIONS')),
                     qualified=False,
                     requested_cells=len(cells),measured_cells=measured,
                     failed_cells=len(failures),unmeasured_cells=len(cells)-measured,
                     expected_scalar_full_matrix=54,
                     all_54_rows_sampled=len(cells)==54 and measured==54 and not failures,
                     sampled_src_rows=src_observed,real_graph_rows=graph_observed,
                     measured_forced_isa_jobs=tier_measured,
                     unsupported_forced_isa_jobs=tier_unsupported,
                     all_required_local_observations_present=all_observed,
                     complete_54_cell_matrix=False,
                     release_gate_closed=False,
                     note='This instrument does not substitute for full spectral extrema/coherent-alias certification, a justified combined-stage SRC numerical envelope, real graph-thread and clipping evidence, or independent review.',
                     failures=failures)
        write_json_atomic(output/'summary.json',summary)
        print(json.dumps({k:v for k,v in summary.items() if k!='failures'},sort_keys=True),flush=True)
        return 1 if failures else (2 if options.require_qualified or
                 (options.require_all_observations and not all_observed) else 0)
    
    finally:
        fcntl.flock(lock_fp.fileno(),fcntl.LOCK_UN)
        lock_fp.close()

def main() -> int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--probe',type=Path,required=True)
    ap.add_argument('--src-probe',type=Path,
                    help='built P07 private SRC exporter with P15 --tone extension')
    ap.add_argument('--sox',type=Path,help='built SoX CLI for actual thread/buffer/clip graph checks')
    ap.add_argument('--capture-src-raw',action='store_true',
                    help='persist every binary64 SRC tone vector as SHA-bound little-endian raw evidence; may require substantial disk space')
    ap.add_argument('--capture-graph-raw',action='store_true',
                    help='retain original DSF, two raw graph WAVs and clipped-warning WAV for independent int32 graph review')
    ap.add_argument('--results',type=Path,required=True)
    ap.add_argument('--src-frames',type=int,default=131072,
                    help='SRC independent tone/alias analysis input length')
    ap.add_argument('--frames',type=int,default=262144,
                    help='262144 full capture; shorter runs are diagnostic')
    ap.add_argument('--tier',dest='tiers',action='append',choices=REQUIRED_TIERS,
                    help='additionally force this tier; default scalar; repeat for full ISA grid')
    ap.add_argument('--native',type=int,choices=NATIVE_RATES)
    ap.add_argument('--pcm',type=int,choices=PCM_RATES)
    ap.add_argument('--profile',choices=PROFILES)
    ap.add_argument('--resume',action='store_true')
    ap.add_argument('--stop-on-fail',action='store_true')
    ap.add_argument('--require-all-observations',action='store_true',
                    help='exit nonzero unless 54 full-length scalar/SRC/real-graph measurement rows are present (still NOT a release certificate)')
    ap.add_argument('--require-qualified',action='store_true',
                    help='return 2 unless a separately adjudicated release certificate exists; measurement alone never suffices')
    opt=ap.parse_args()
    opt.tiers=tuple(dict.fromkeys(['scalar']+(opt.tiers or [])))
    if not 8192<=opt.frames<=50000000:
        ap.error('--frames must be between 8192 and 50000000')
    if not 8192<=opt.src_frames<=4000000:
        ap.error('--src-frames must be between 8192 and 4000000')
    try:
        return execute(opt)
    except (ValueError,OSError) as exc:
        print(f'P15 instrument ERROR: {exc}',file=sys.stderr)
        return 1

if __name__=='__main__':
    raise SystemExit(main())
