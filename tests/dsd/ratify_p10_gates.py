#!/usr/bin/env python3
"""Independent P10 release-gate adjudication of retained hardware/corpus data.

Reads, validates and cross-checks immutable receipts. It never executes a
candidate, rewrites source material, or promotes a mastering profile. External
recordings are not redistributed; receipt validation is not an independent
re-render of the unavailable copyrighted audio.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import re

from soak_p10 import configuration

ROOT = Path(__file__).resolve().parents[2]
TESTS = ROOT / 'tests/dsd'
CRITERIA = TESTS / 'reference/p10_ratification_criteria.json'
HARDWARE = TESTS / 'results/P10_soak_1hour_sse2_2026-10-10'
CORPUS = TESTS / 'results/P10_realworld_corpus_2026-10-10'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def sha256_string(s):
    return isinstance(s, str) and re.fullmatch('[0-9a-f]{64}', s) is not None


def finite(v):
    return type(v) in (int, float) and math.isfinite(v)


def gate(status, criteria, evidence, reasons=None, checks=None, **extra):
    return dict(status=status, criteria=criteria, evidence=evidence,
        reasons=reasons or [], checks=checks or {}, **extra)


def check_hardware(base=HARDWARE, criteria=None):
    base = Path(base)
    criteria = (criteria or read(CRITERIA))['one_hour_hardware']
    sources = criteria['native_hz']
    if not base.exists():
        return gate('UNRUN', 'one_hour_hardware', str(base), ['No recorded one-hour run'])
    failures = []
    summary_path = base/'soak.json'
    if not summary_path.is_file():
        return gate('FAIL', 'one_hour_hardware', str(base), ['Missing soak summary'])
    try:
        summary = read(summary_path)
        assert isinstance(summary['profiles'], list) and len(summary['profiles']) == len(sources)
        assert {p['configuration']['native_hz'] for p in summary['profiles']} == set(sources)
        assert summary['qualified'] is False
        rows = {p['configuration']['native_hz']:p for p in summary['profiles']}
        bounds = read(TESTS/'reference/p10_guards.json')['profiles']
        source_hash = digest(TESTS/'test_p10.c')
        executable_hashes = set()
        all_snapshots = 0
        for native in sources:
            tag = f'soak-{native}'
            cfg = read(base/f'{tag}-configuration.json')
            execution = read(base/f'{tag}-execution.json')
            report_path = base/f'{tag}-result.json'
            report = read(report_path)
            row = rows[native]
            expected = native * criteria['seconds']
            assert cfg == configuration(native, criteria['seconds'],
                criteria['segment_seconds'], criteria['fixture']), tag+' configuration changed'
            assert row['configuration']==cfg, tag+' summary configuration differs'
            assert row['execution']==execution, tag+' summary execution differs'
            assert row['raw']==report and row['evidence_sha256']==digest(report_path), tag+' stale receipt'
            assert execution['exit_code']==0 and execution['fixture']==criteria['fixture']
            assert execution['source_generator_sha256']==source_hash
            assert execution['architecture']=='x86_64' and sha256_string(execution['binary_sha256'])
            assert execution['command'] == ['test/dsd_test_p10', '--soak-nominal-v2',
                str(native), str(criteria['seconds']), str(criteria['segment_seconds']),
                f'<results>/{tag}']
            executable_hashes.add(execution['binary_sha256'])
            assert report['schema']=='P10/candidate-render/1'
            assert report['qualification']=='UNQUALIFIED'
            assert report['profile']==f'encode.mastering.v1.dsd{native//44100}'
            assert report['mode']=='soak-nominal-v2' and report['status']==3
            assert report['source_hz']==cfg['source_hz'] and report['native_hz']==native
            assert report['input_frames']==cfg['source_hz']*criteria['seconds']
            assert report['processed_native_frames']==expected and report['committed_native_frames']==expected
            assert report['first_bad_frame'] is None and report['failure']==0
            assert report['nonfinite_states']==0 and report['monitor_overloads_nominal_half']==0
            assert finite(report['peak']) and 0 <= report['peak'] <= .5+1./(2**31-1)
            assert report['windows28']==expected-27 and report['longest_run']>=1
            limits = bounds[str(native)]['bounds']
            maxima = report['max_abs_state']
            assert len(limits)==len(maxima)==8
            assert all(finite(v) and 0<=v<=lim for v,lim in zip(maxima,limits))
            if native==2822400:
                assert report['excursions28']==0 and report['min_ones28']>=4 and report['max_ones28']<=24
            assert report['excursions28']>=0 and 0<=report['min_ones28']<=report['max_ones28']<=28
            assert row['completed_audio_seconds']==criteria['seconds']
            assert row['state_bound_crossed'] is False
            assert not (base/f'{tag}-failure.state').exists()
            checks = row['admission_checks']
            # The historical summary is intentionally NOT rewritten. Its FAIL
            # is exactly the prior 1800-equality check, never a numeric failure.
            assert all(checks[k] is True for k in (
                'admitted_peak', 'clean_terminal_status', 'complete_snapshots',
                'complete_window_monitor', 'exact_native_duration',
                'observed_half_guard', 'original_configuration',
                'reproducible_binary', 'source_and_native_identity', 'stable_state'))
            if native==2822400: assert checks['dsd64_28bit_population'] is True
            expected_false = not checks['release_sequence']
            assert set(k for k,v in checks.items() if v is False)==({'release_sequence'} if expected_false else set())
            assert (row['status'], summary['status']) == (('FAIL','FAIL') if expected_false else ('PASS','PASS'))
            names = [f'{tag}-{i:04d}.state' for i in range(1,61)]+[f'{tag}-final.state']
            attest = row['snapshots']
            assert len(attest)==61 and {s['file'] for s in attest}==set(names)
            assert {s['file'] for s in attest} == {p.name for p in base.glob(f'{tag}-*.state')}
            assert all(sha256_string(s['sha256']) and digest(base/s['file'])==s['sha256'] for s in attest)
            last_input=last_native=last_windows=-1
            for name in names:
                data = (base/name).read_text().splitlines()
                assert data[0]=='P10-continuation-v1'
                state = dict(x.split('=',1) for x in data[1:])
                inp, out, windows = [int(state[x]) for x in ('input','native','windows')]
                assert last_input <= inp <= report['input_frames']
                assert last_native < out <= expected
                assert last_windows < windows and windows == max(0,out-27)
                if native==2822400: assert int(state['excursions'])==0
                for i in range(8):
                    v = float.fromhex(state[f'maximum{i}'])
                    assert finite(v) and 0<=v<=limits[i]
                last_input,last_native,last_windows=inp,out,windows
            assert last_input==report['input_frames'] and last_native==expected
            assert last_windows==report['windows28']
            assert all(math.isclose(float.fromhex(state[f'maximum{i}']), maxima[i], rel_tol=1e-14)
                for i in range(8)), tag+' final maxima disagree'
            all_snapshots+=len(names)
        assert len(executable_hashes)==1, 'different binaries across native rates'
        # Operator's hardware declaration is retained as provenance, not a
        # cryptographically attestable property of the machine.
        text=(base/'README.md').read_text()
        assert 'Threadripper 7970X' in text and 'taskset' in text
    except (OSError, KeyError, TypeError, ValueError, AssertionError, IndexError, ZeroDivisionError) as exc:
        failures.append(str(exc) or 'record did not meet one-hour criterion')
    return gate('FAIL' if failures else 'PASS', 'one_hour_hardware',
        'tests/dsd/results/'+base.name+'/', failures,
        {'rates':sources,'seconds_per_rate':criteria['seconds'],
         'continuation_snapshots':0 if failures else all_snapshots,
         'kernel_family':'scalar (x86_64 baseline build, not an SSE2 mastering kernel)',
         'hardware_provenance':'operator-reported Threadripper 7970X'})


def row_key(row):
    return (row['native_hz'], row['source'], row['excerpt_sha256'])


def check_complete(row, native, rules, domain):
    """Check externally rendered output, not merely a cached PASS bool."""
    seconds = row['excerpt_seconds']
    expected = seconds*native
    assert row['admitted'] is True and row['encode_exit']==0
    assert row['expected_frames']==expected and row['output_frames']==expected
    assert row['frames_exact'] is True and row['output_rate']==native
    assert row['output_channels']>=1 and row['output_bytes']>0
    channels = row['per_channel']
    assert len(channels)==row['output_channels']
    assert row['windows28']==sum(c['windows'] for c in channels)
    assert all(c['windows']==max(0,expected-27) for c in channels)
    assert all(0<=c['min_ones']<=c['max_ones']<=28 and
        finite(c['ones_fraction']) and 0<=c['ones_fraction']<=1 for c in channels)
    assert row['min_ones28']==min(c['min_ones'] for c in channels)
    assert row['max_ones28']==max(c['max_ones'] for c in channels)
    if native==2822400:
        assert row['population_within_4_24'] is True
        assert row['min_ones28']>=4 and row['max_ones28']<=24
    for k in ('peak_db','rms_db'):
        assert finite(row['source_excerpt_level'][k]) and finite(row['remodulated_level'][k])
    assert finite(row['peak_delta_db']) and finite(row['rms_delta_db'])
    deltas = rules['source_level_calibration']
    expected_db = 0. if domain=='DSD_NATIVE' else 0.  # PCM output reconstructed with SACD reference.
    assert abs(row['rms_delta_db']-expected_db)<=deltas['rms_delta_tolerance_db']
    assert abs(row['peak_delta_db']-expected_db)<=deltas['peak_delta_tolerance_db']
    # Stored levels have hundredth-dB resolution on DSD runs. Don't require
    # more significant digits than the original measurements provide.
    assert abs(row['rms_delta_db']-(row['remodulated_level']['rms_db']-
        row['source_excerpt_level']['rms_db']))<=0.02
    assert abs(row['peak_delta_db']-(row['remodulated_level']['peak_db']-
        row['source_excerpt_level']['peak_db']))<=0.02


def validate_domain(base, rules, domain):
    prefix='corpus' if domain=='DSD_NATIVE' else 'pcm'
    manifest=base/('sources.json' if domain=='DSD_NATIVE' else 'pcm-sources.json')
    unity=base/('corpus-unity.json' if domain=='DSD_NATIVE' else 'pcm-unity.json')
    ladder=base/('corpus-ladder.json' if domain=='DSD_NATIVE' else 'pcm-ladder.json')
    if not (manifest.is_file() or unity.is_file() or ladder.is_file()):
        return dict(status='UNRUN',sources=0,admitted=0,reason='no '+domain+' source/run records')
    try:
        source_rows=read(manifest); results=read(unity)
        assert isinstance(source_rows,list) and isinstance(results,list)
        assert len(source_rows)==len(results)
        originals={row_key(s):s for s in source_rows}
        renders={row_key(r):r for r in results}
        assert len(originals)==len(renders)==len(results), 'missing or duplicate source excerpts'
        assert originals.keys()==renders.keys(), 'source identities differ from results'
        counts={str(n):dict(sources=0,admitted=0,explicit_rejections=0) for n in rules['native_hz']}
        genres=set(); rate_families=set(); rejected={}
        for key, source in originals.items():
            native,name,ex_sha=key
            assert native in rules['native_hz']
            assert sha256_string(ex_sha) and source['excerpt_seconds']>=rules['minimum_excerpt_seconds']
            assert isinstance(source['release'],str) and source['release'].strip()
            assert isinstance(source['genre'],str) and source['genre'].strip()
            assert isinstance(source['origin'],str) and source['origin'].strip()
            assert finite(source['original_bytes']) and source['original_bytes']>0
            assert source.get('source_domain', domain)==domain
            row=renders[key]
            for field in ('genre','release'):
                assert row[field]==source[field]
            assert row['excerpt_seconds']==source['excerpt_seconds']
            assert row['explicit_gain_db']==0
            assert row['native_hz']==native
            if domain=='DSD_NATIVE':
                assert row['working_hz']==(88200 if native==2822400 else 176400)
                assert name.lower().endswith(('.dsf','.dff'))
            else:
                hz=source['source_rate_hz']
                assert row['source_rate_hz']==hz and hz in (44100,48000,88200,96000,176400,192000,352800,384000,705600)
                assert row['reconstruction_reference']=='sacd'
                rate_families.add('44100-family' if hz%44100==0 else '48000-family')
            genres.add(source['genre']);counts[str(native)]['sources']+=1
            if row['admitted']:
                check_complete(row,native,rules,domain)
                counts[str(native)]['admitted']+=1
            else:
                assert row['encode_exit']!=0
                assert 'interpolation overload' in row['encode_stderr_tail'] and 'failure 2' in row['encode_stderr_tail']
                counts[str(native)]['explicit_rejections']+=1
                rejected[key]=row
        min_release=rules['minimum_distinct_external_recordings_per_domain_and_native_rate']
        for native in rules['native_hz']:
            subset=[r for r in source_rows if r['native_hz']==native]
            assert len({s['source'] for s in subset})>=min_release, 'too few independent recordings at '+str(native)
            assert counts[str(native)]['sources']>=min_release
        assert len(genres)>=rules['minimum_genres_per_domain']
        if domain=='PCM_AUDIO':
            assert set(rules['pcm_rate_family_coverage'])<=rate_families
        if rejected:
            ladder_rows=read(ladder)
            assert isinstance(ladder_rows,list) and len(ladder_rows)==len(rejected)
            ladder_map={row_key(r):r for r in ladder_rows}
            assert len(ladder_map)==len(rejected) and ladder_map.keys()==rejected.keys()
            for key,row in ladder_map.items():
                assert row['excerpt_seconds']==originals[key]['excerpt_seconds']
                assert row['ladder_exhausted'] is False
                attempts=row['ladder_attempts']
                assert len(attempts)>=2 and attempts[0]['gain_db']==0
                assert attempts[0]['admitted'] is False and attempts[-1]['admitted'] is True
                assert all(not r['admitted'] and finite(r['gain_db']) for r in attempts[:-1])
                assert all(attempts[i+1]['gain_db']<attempts[i]['gain_db'] for i in range(len(attempts)-1))
                assert row['explicit_gain_db']==row['admitting_gain_db']==attempts[-1]['gain_db']<0
                check_complete(row,key[0],rules,domain)
        if domain=='DSD_NATIVE':
            oracle=read(base/'reader-self-check.json')
            assert oracle['bit_identical_to_oracle'] is True and oracle['frames']>0
        return dict(status='PASS',sources=len(source_rows),
            admitted=sum(v['admitted'] for v in counts.values()),
            rejected=len(rejected),genres=len(genres),by_rate=counts)
    except (OSError, KeyError, TypeError, ValueError, AssertionError, IndexError, ZeroDivisionError) as exc:
        return dict(status='FAIL',sources=0,admitted=0,
            reason=str(exc) or 'corpus evidence failed independently checked criterion')


def check_corpus(base=CORPUS, criteria=None):
    base=Path(base)
    rules=(criteria or read(CRITERIA))['independent_corpus']
    if not base.exists():
        return gate('UNRUN','independent_corpus','tests/dsd/results/'+base.name+'/',
            ['No independent source/run evidence'])
    coverage={domain:validate_domain(base,rules,domain) for domain in rules['required_domains']}
    values=[x['status'] for x in coverage.values()]
    if 'FAIL' in values: status='FAIL'
    elif all(x=='PASS' for x in values):status='PASS'
    elif 'PASS' in values:status='PARTIAL'
    else:status='UNRUN'
    missing=[k for k,v in coverage.items() if v['status']!='PASS']
    reasons=[] if not missing else ['Missing or inadequate independent input-domain coverage: '+', '.join(missing)]
    return gate(status,'independent_corpus','tests/dsd/results/'+base.name+'/',
        reasons,coverage)
