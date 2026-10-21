#!/usr/bin/env python3
"""P17 additive, deterministic HIGH-RATE CANDIDATE coefficient/latency records.

Reconstruction is deliberately an exact clock/normalized-frequency reuse of
already certified v1 FIR banks; P00-P16 bank headers are never rewritten.
The experimental SDM uses the unchanged unit-delay recurrence, mapped to an
explicit new sample clock. Same z-domain coefficients imply the same NTF/STF
as a function of cycles/sample and the same normalized state coordinates,
NOT a new high-rate stability, signal-band or interoperability certificate.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'tests/dsd/reference/p17_profiles.json'
HEADER = ROOT/'src/sdm_p17_candidates.h'
RATES = (22579200,45158400)
HALFBAND_TAPS = 57
LAST_TAPS = {'master64_256': 117, 'wideband': 257}

def extract_sdm256():
    text=(ROOT/'src/sdm.c').read_text()
    start=text.index('static const sdm_filter_t sdm_filters[] = {')
    start=text.index('{',start)
    depth=0; entries=[]; begin=None
    for i in range(start,len(text)):
        if text[i]=='{':
            if depth==1:begin=i
            depth+=1
        elif text[i]=='}':
            depth-=1
            if depth==1:
                entries.append(text[begin:i+1])
            if depth==0:break
    assert len(entries)>=10, 'SDM registry changed: review normalized mapping'
    entry=entries[9]  # 256kHz-family mastering exact-rate entry
    groups=[]; level=0; begin=None
    for i,char in enumerate(entry):
        if char=='{':
            if level==1:begin=i+1
            level+=1
        elif char=='}':
            if level==2:
                groups.append(entry[begin:i])
            level-=1
    assert len(groups)==2
    floats=[]
    for group in groups:
        tokens=[s.strip() for s in group.split(',') if s.strip()]
        floats.append([float(t) for t in tokens]+[0.]* (8-len(tokens)))
    assert len(floats[0])==len(floats[1])==8
    assert re.search(r'8\s*,\s*256\s*\*\s*44100\s*,\s*"sdm-8"',entry)
    return floats

def hexdigest(values):
    return hashlib.sha256(('\n'.join(x.hex() for x in values)+'\n').encode()).hexdigest()

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--check',action='store_true')
    args=ap.parse_args()
    a,g=extract_sdm256()
    assert all(x==0 for x in g[1::2])
    profiles={}
    for hz in RATES:
        factor=hz//176400
        for kind,R,P,S,last in (
            ('mastering',176400,40000,80000,'master64_256'),
            ('wideband',hz//32,2*(hz//32)//5,(hz//32)//2,'wideband')):
            D=hz//R
            assert D>0 and D&(D-1)==0
            stages=D.bit_length()-1
            banks=['halfband']*(stages-1)+[last]
            G=sum((HALFBAND_TAPS//2 if j<stages-1 else LAST_TAPS[last]//2)*(1<<j)
                  for j in range(stages))
            identity=f'decode.{kind}.v1.dsd{hz//44100}'
            profiles[identity]=dict(native_hz=hz,intermediate_hz=R,pass_hz=P,
                stop_hz=S,factor=D,stage_banks=banks,
                last_bank=last,delay_native_frames=G,
                phase_native_frames=G%D,discard_output_frames=G//D,
                stage_phases=[(G>>j)&1 for j in range(stages)],
                last_stage_input_hz=R*2,
                reconstruction_bank_reuse='certified immutable v1 bank at identical input clock (mastering) or identical normalized edges (wideband)',
                qualified=False,experimental_only=True)
    manifest=dict(schema='P17/highrate-profiles/1', generator='tests/dsd/generate_p17_profiles.py',
       source_revision='998b08dc', rates_hz=list(RATES),
       reconstruction=profiles,
       sdm_candidates={str(hz):dict(id=f'encode.mastering.v1.dsd{hz//44100}',
         rate_hz=hz,working_hz=176400,pass_hz=40000,stop_hz=80000,
         normalized_a_sha256=hexdigest(a),normalized_g_sha256=hexdigest(g),
         order=8,recurrence_clock_hz=hz,state_scale=1,
         prefilter='master64_256 at 176400 Hz; normalized P=40000/176400, S=80000/176400',
         normalized_coefficients_from='sdm_filters[9] (sdm-8 DSD256), same z-domain STF/NTF under sample-time scaling',
         basis='unit-delay discrete-time recurrence contains no clock-dependent terms; mapping z^-1 to the new native sample clock preserves normalized NTF/STF and state units, not a finite-stream stability guarantee',
         qualified=False,production_entry=False,experimental_only=True)
         for hz in RATES},
       qualified_highrate_writers=[],
       limitation='no DSD512/1024 independent licensed media, DAC/player evidence, sustained high-rate soak or production writer/transport qualification')
    header=['/* P17 experimental exact-rate SDM candidate records. Generated, do not edit. */',
      '/* Normalized z-domain recurrence reuse, not P17 full-rate qualification. */',
      '#ifndef LSX_SDM_P17_CANDIDATES_H','#define LSX_SDM_P17_CANDIDATES_H',
      'static const sdm_filter_t lsx_sdm_p17_candidates[2] = {']
    for hz in RATES:
        header.extend(['  {',
          '    {'+', '.join(x.hex() for x in a)+'},',
          '    {'+', '.join(x.hex() for x in g)+'},',
          f'    8, {hz}u, "sdm-8-p17-candidate", 0, 0, 0','  },'])
    header.extend(['};','#endif',''])
    expected=[(HEADER,'\n'.join(header)),(OUT,json.dumps(manifest,sort_keys=True,indent=2)+'\n')]
    if args.check:
        for path,content in expected:
            if not path.exists() or path.read_text()!=content:
                raise SystemExit('MISMATCH: '+str(path))
    else:
        for path,content in expected:path.write_text(content)
    print('P17 generator '+('CHECK' if args.check else 'GENERATED')+': PASS')
    return 0
if __name__=='__main__':raise SystemExit(main())
