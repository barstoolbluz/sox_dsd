#!/usr/bin/env python3
"""Source-bound read-only replay of archived P15 2026-10-16 physical receipts.

The benchmark and comparator audio/executables were intentionally stripped.
Recompute timing statistics and verify their exact digests, spectral verdict
metadata, command shape, host assertions, and cross-receipt identities.  Never
claim to have re-executed audio or benchmark on a physical host; qualification
is scoped to the pinned 2026-10-16 observations and remains non-promotional.
"""
from __future__ import annotations
from hashlib import sha256
import json
import math
from pathlib import Path
import re

from bench_p15_dsd256_ps_matched import (bootstrap_ratio,commands,
    admissible_host,ARMS,PROFILES,RATES,REPS,SCHEMA as BENCH_SCHEMA)
from p15_dsd256_comparator_2026 import (sources,SCHEMA as SPECTRAL_SCHEMA,
    INTERMEDIATE,NATIVE)

ROOT=Path(__file__).resolve().parents[2]
ARCHIVE=ROOT/'tests/dsd/results/P15_ps_matched_physical_2026-10-16'
# Input-archive receipts identified by source operator's October 16 handoff.
# These are evidence identifiers, not new generated/fabricated measurements.
SPECTRAL_SHA256='9af8aefb18e7dc3e557a789960401585f734e10b7cd23cc7b099f020d75b1a7a'
BENCH_SHA256='5c5f4a479601f833df68cc282730f7f76ed9f8b27875171c1bf903f25ab01511'
HEX64=re.compile(r'[0-9a-f]{64}\Z')


class ArchivedEvidenceError(ValueError):pass


def need(ok,why):
    if not ok:raise ArchivedEvidenceError(why)


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def read(path):
    need(path.is_file() and not path.is_symlink(),f'missing/linked archived file {path}')
    return json.loads(path.read_text())


def absent_audio_manifest(folder):
    """Confirm archived AUDIO_SHA256 identities, not nonexistent media bytes."""
    lines=(folder/'AUDIO_SHA256.txt').read_text().splitlines()
    pairs=[]
    for line in lines:
        match=re.fullmatch(r'([0-9a-f]{64})  ([A-Za-z0-9_.-]+)',line)
        need(match is not None,'malformed archived audio manifest')
        value,name=match.groups()
        need(not (folder/name).exists(),'unexpected bulk payload in archived review')
        pairs.append((name,value))
    hashes=dict(pairs)
    need(len(hashes)==len(pairs),'duplicate archived audio manifest entry')
    return hashes


def review(folder=ARCHIVE):
    folder=Path(folder)
    spectral_dir=folder/'comparator';bench_dir=folder/'bench'
    for path in (folder,spectral_dir,bench_dir):
        need(path.is_dir() and not path.is_symlink(),'missing/linked evidence directory')
    need({p.name for p in spectral_dir.iterdir()}=={
        'AUDIO_SHA256.txt','RECEIPT.json','profile-mastering.json',
        'profile-decode.mastering.v2.dsd256.json'},'archived spectral payload differs')
    need({p.name for p in bench_dir.iterdir()}=={'AUDIO_SHA256.txt','RECEIPT.json'},
         'archived benchmark payload differs')
    sfile=spectral_dir/'RECEIPT.json';bfile=bench_dir/'RECEIPT.json'
    need(digest(sfile)==SPECTRAL_SHA256 and digest(bfile)==BENCH_SHA256,
         'archived physical evidence SHA-256 identity differs')
    spec=read(sfile);bench=read(bfile)
    source=sources()
    need(spec.get('schema')==SPECTRAL_SCHEMA and
         spec.get('source_sha256')==source and
         spec.get('status')=='SPECTRALLY_MATCHED_DIAGNOSTIC' and
         spec.get('spectrally_matched_on_fixture') is True and
         spec.get('selftest_wrong_cutoff') is False and
         spec.get('qualified_release') is False and
         spec.get('initial_intermediate_hz')==INTERMEDIATE,
         'spectral verdict/source/scope invalid')
    need(spec.get('executable_sha256')==bench.get('executable_sha256') and
         len(spec.get('executable_sha256',{}))==2 and
         all(HEX64.fullmatch(x) for x in spec['executable_sha256'].values()),
         'benchmark and spectral binary identities differ')
    need(bench.get('source_sha256')==source and
         bench.get('schema')==BENCH_SCHEMA and
         bench.get('status')=='MEASURED_PHYSICAL_UNADJUDICATED' and
         bench.get('qualified_release') is False and
         bench.get('spectral_receipt_sha256')==SPECTRAL_SHA256,
         'physical benchmark binding or status invalid')
    spectral_audio=absent_audio_manifest(spectral_dir)
    timing_audio=absent_audio_manifest(bench_dir)
    need(spectral_audio.get('noise-dsd256.dsf')==spec.get('native_sha256'),
         'native source audio digest drift')
    need(timing_audio=={'input-6ch.dsf':bench.get('six_channel_native_sha256'),
                       'input-6ch.wav':bench.get('six_channel_pcm_sha256')},
         'six-channel fixture digest disagreement')
    need(set(spec.get('file_sha256',{}))==set(spectral_audio)|{
        'profile-'+p+'.json' for p,_,_ in PROFILES},'incomplete spectral payload digests')
    for name,expected in spec['file_sha256'].items():
        need(spectral_audio.get(name,digest(spectral_dir/name) if
            (spectral_dir/name).is_file() else None)==expected,
             'spectral payload digest mismatch: '+name)
    need(spec['fixture_seconds']>=1.5 and spec['fixture_seconds']<=30,
         'spectral fixture duration out of bounds')
    rows=spec.get('rows')
    need(type(rows) is list and len(rows)==4,'incomplete spectral grid')
    spectral_cells={}
    for row in rows:
        profile=row.get('profile');rate=row.get('rate')
        expected=next(((p,s) for name,p,s in PROFILES if name==profile),None)
        need(expected is not None and rate in RATES,'unknown spectral profile/rate')
        p,s=expected;identity=profile+'@'+str(rate)
        need(identity not in spectral_cells,'duplicate spectral cell')
        v=row.get('verification',{})
        need(row.get('pass_hz')==p and row.get('stop_hz')==s and
             row.get('initial_intermediate_hz')==INTERMEDIATE and
             row.get('proposed_control')==f'sinc -a 180 -t {s-p} -{(p+s)//2}' and
             row.get('reported_id') in (profile,'decode.mastering.v1.dsd256') and
             row.get('decoder_wav_sha256')==spec['file_sha256']['decoder-'+row['label']+'.wav'] and
             row.get('control_wav_sha256')==spec['file_sha256']['control-'+row['label']+'.wav'],
             'spectral cell P/S, command or source mismatch')
        need(v.get('matched') is True and v.get('transition_excluded_fraction')==0 and
             v.get('comparison_band_hz')==[1000.,float(p)] and
             v.get('agreement_limit_db')==1.0 and
             type(v.get('compared_bins')) is int and v['compared_bins']>=1000 and
             type(v.get('max_abs_difference_db')) in (float,int) and
             math.isfinite(v['max_abs_difference_db']) and
             0<=v['max_abs_difference_db']<1.0,
             'comparator full upper passband edge or spectral decision invalid')
        spectral_cells[identity]=v['max_abs_difference_db']
    need(set(spectral_cells)=={p+'@'+str(r) for p,_,_ in PROFILES for r in RATES},
         'spectral comparator grid missing cell')
    host=bench.get('host')
    need(type(host) is dict and admissible_host(host,bench.get('pinned_cpu')) and
         host.get('governor')=='performance' and
         bench.get('physical_host_admissible') is True,
         'not a documented physical prepared-host observation')
    need(bench.get('target')==2.0 and bench.get('repetitions')==REPS and
         bench.get('warmups',0)>=1 and bench.get('fixture_seconds')==2 and
         bench.get('bootstrap')=={'iterations':10000,'seed':20261016},
         'benchmark method changed')
    need(set(bench.get('rows',{}))==set(spectral_cells),
         'bench and comparator cell identities differ')
    comparisons={}
    for profile,p,s in PROFILES:
        for rate in RATES:
            ident=f'{profile}@{rate}';row=bench['rows'][ident]
            sox=row.get('commands',{}).get('decoder',[None])[0]
            need(isinstance(sox,str) and sox.startswith('/'),
                 'missing source-bound timed executable command')
            need(row.get('commands')==commands(Path(sox),Path('<fixture>'),
                      profile,rate,p,s,Path('<output>')) and
                 (row.get('pass_hz'),row.get('stop_hz'),row.get('rate'))==(p,s,rate),
                 'timed control changed from spectral P/S control')
            durations=row.get('seconds')
            need(type(durations) is dict and set(durations)==set(ARMS),
                 'missing timed arm')
            for arm in ARMS:
                samples=durations[arm]
                need(type(samples) is list and len(samples)==REPS and all(
                    type(x) in (float,int) and math.isfinite(x) and x>0 for x in samples),
                    'invalid timed samples')
            need(set(row.get('comparisons',{}))==set(ARMS[1:]),
                 'comparison arm missing')
            for arm in ARMS[1:]:
                observed=bootstrap_ratio(durations[arm],durations['decoder'])
                need(observed==row['comparisons'][arm] and
                     observed['exceeds_two_at_lower_bound'] and
                     observed['ci95'][0]>2,
                     'saved raw timing repetitions do not reproduce 2x')
                comparisons[ident+'~'+arm]=observed['ci95'][0]
    return dict(status='PASS-SCOPED-ARCHIVED-PHYSICAL-EVIDENCE',
        qualified_release=False,spectral_receipt_sha256=SPECTRAL_SHA256,
        benchmark_receipt_sha256=BENCH_SHA256,physical_host_asserted=True,
        physical_host_retested=False,source_hashes_verified=True,
        absent_bulk_inputs_and_executables=True,raw_timing_arrays_recomputed=True,
        matched_control_frequency_range_hz='1000 Hz through each profile P, including upper edge',
        spectral_cells_verified=len(spectral_cells),
        largest_reported_comparator_difference_db=max(spectral_cells.values()),
        performance_comparisons_verified=len(comparisons),
        minimum_95pct_bootstrap_speedup_lower_bound=min(comparisons.values()),
        evidence_scope=('An immutable archived physical observation with mathematical timing '
          'replay and source/digest/metadata verification. Source WAV/DSF samples and measured '
          'binaries were omitted, so no independent audio FFT or timed execution replay. '
          'Does NOT establish composite SRC compliance, global audio quality, or promotion.'))


if __name__=='__main__':
    print(json.dumps(review(),indent=2,sort_keys=True))
