#!/usr/bin/env python3
"""Generate/check the UNQUALIFIED DSD1024 v2 source-and-evidence binding.

This is a reproducible SHA-256 evidence manifest, not a signed certificate and
not permission to enable production DSD1024. It deliberately records unfinished
gates, including the prepared-host sustained soak and independent audio checks.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / 'tests/dsd/results/P19_DSD1024_CORRECTION'
OUT = ROOT / 'tests/dsd/reference/p19_dsd1024_v2_certificate.json'
sys.path.insert(0, str(ROOT / 'tests/dsd'))
import p17_qualify_guards as p17
import p19_qualify_dsd1024 as p19


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for data in iter(lambda: stream.read(8 << 20), b''):
            h.update(data)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(),
        parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def generate():
    # Recompute trained maxima and guarded adjudication from the frozen receipts.
    # These operations never re-run or overwrite an experiment.
    p19.verify(SimpleNamespace())
    require(p19.adjudicate(SimpleNamespace()) == 0, 'v2 holdout failure')
    frozen = read(p19.FROZEN)
    holdout = read(RESULTS / 'holdout-summary.json')
    require(frozen['training_case_count'] == 17 and frozen['rejected_case_count'] == 0,
            'incomplete original v2 training population')
    require(holdout['case_count'] == 36 and holdout['result'] == 'PASS',
            'incomplete or failed v2 holdout')
    statuses = [case['status'] for case in holdout['cases']]
    require(statuses.count('PASS') == 33 and
            statuses.count('OBSERVED_FULLSCALE_NOT_NOMINAL') == 2 and
            statuses.count('PASS_EXPECTED_INTERPOLATION_OVERLOAD') == 1,
            'incorrect holdout disposition')

    training_exe = RESULTS / 'executables/training-dsd_test_p10'
    guarded_exe = RESULTS / 'executables/guarded-dsd_test_p10'
    require(sha(training_exe) == frozen['executable_sha256'],
            'training executable missing or changed')
    require(sha(guarded_exe) == holdout['executable_sha256'],
            'guarded executable missing or changed')
    require(sha(guarded_exe) != sha(training_exe),
            'training and guarded builds require distinct snapshots')

    isa = read(RESULTS / 'cross-isa.json')
    require(isa['profile'] == p19.ID and isa['status'] == 'PASS' and
            isa['qualified'] is False and
            isa['binary_sha256'] == sha(guarded_exe) and
            isa['candidate_sha256'] == sha(ROOT / 'src/sdm_p19_candidates.h') and
            isa['guard_sha256'] == sha(ROOT / 'src/pcmdsd_v2_guards.h'),
            'cross-ISA provenance or result mismatch')
    expected = set(itertools.product(isa['tiers'], isa['test_case_indices']))
    require(tuple(isa['tiers']) == ('scalar','sse2','avx1','avx2','avx512') and
            tuple(isa['test_case_indices']) == (1,16,17,21,25) and
            len(isa['cases']) == len(expected) == 25 and
            {(r['tier'],r['index']) for r in isa['cases']} == expected and
            all(r['passed'] is True for r in isa['cases']),
            'missing or failed ISA qualification matrix cell')
    holdout_defs = p19.cases('holdout')
    for row in isa['cases']:
        require(row['case'] == holdout_defs[row['index']]['name'],
                'ISA case identity mismatch')
        if row['index'] == 25:
            require(row['failure'] == 2 and row['kernel_exit'] != 0,
                    'ISA overload not correctly classified')
        else:
            conf = holdout_defs[row['index']]
            from p10_corpus import stimulus
            _, spec = stimulus(conf)
            expected_frames = (spec['frames'] * p19.RATE + conf['source_hz']//2)//conf['source_hz']
            require(row['failure'] == 0 and row['kernel_exit'] == 0 and
                    row['frames'] == expected_frames and row['excursion28'] == 0,
                    'ISA accepted case differs from expected duration or faults')

    audio = read(RESULTS / 'audio-v1-v2-comparison.json')
    require(audio['candidate_qualified'] is False and
            audio['comparison_only'] is True and audio['native_hz'] == p19.RATE and
            audio['reference_coeff_sha256'] == sha(ROOT / 'src/dsd_coeffs.h') and
            set(audio['versions']) == {'v1','v2'}, 'audio diagnostic provenance mismatch')
    for version in ('v1','v2'):
        row = audio['versions'][version]
        require(row['renderer_sha256'] == sha(guarded_exe) and
                row['numeric_profile_id'] == 'encode.mastering.'+version+'.dsd1024' and
                row['output_native_frames'] == 72_253_440 and
                row['diagnostic']['clipping_count'] == 0 and
                row['excursions28'] == 0, 'audio diagnostic missing or failed '+version)

    historical = read(RESULTS / 'preimage/p17_qualification_certificates.json')
    current = read(ROOT / 'tests/dsd/reference/p17_qualification_certificates.json')
    require(set(historical['profiles']) == set(current['profiles']) and
            all(not v['qualified'] and not v['production_capability_enabled']
                for v in current['profiles'].values()),
            'P17 profile promoted or registry membership changed')
    require(historical['profiles']['encode.mastering.v1.dsd1024']['decision'].startswith('BLOCKED_') and
            current['profiles']['encode.mastering.v1.dsd1024']['decision'].startswith('BLOCKED_'),
            'v1 candidate cannot be relabeled stable')
    require(current['historical_p10_certificate_sha256'] == historical['historical_p10_certificate_sha256'],
            'qualified P10 certificate changed')
    for rel, expected_digest in (
        ('src/sdm_p17_candidates.h', 'ef7aab79738ae017d32132e25366ec453ca970e42ecb748c350a58badcd7acb6'),
        ('src/pcmdsd_guards.h', 'af8459f4a0b5512380e24b9c0ec66d575a0995d88fb57ae81ffeb2517982320b')):
        require(sha(ROOT / rel) == expected_digest, 'legacy immutable source changed: '+rel)
    profile_c = (ROOT / 'src/pcmdsd.c').read_text()
    require('"encode.mastering.v2.dsd1024",45158400,176400,40000,80000,' in profile_c and
            'lsx_pcmdsd_coeff_master64_256,61,lsx_pcmdsd_v2_guards,0,NULL' in profile_c,
            'v2 capability must remain disabled')

    smoke = {}
    for mode in ('original','nominal'):
        base = RESULTS / 'soak-smoke' / mode
        report = read(Path(str(base)+'-assessment.json'))
        require(report['status'] == 'PASS_SHORT_SMOKE_ONLY' and
                report['qualified'] is False and
                report['execution_verified'] is True and
                report['seconds'] == 1 and report['rate_hz'] == p19.RATE and
                report['sample_executable_sha256'] == sha(guarded_exe),
                'smoke execution does not meet its declared input gate')
        smoke[mode] = report['status']

    names = [
        'src/sdm.c','src/sdm.h','src/sdm_p17_candidates.h','src/sdm_p19_candidates.h',
        'src/pcmdsd.c','src/pcmdsd.h','src/pcmdsd_guards.h','src/pcmdsd_v2_guards.h',
        'src/pcmdsd_coeffs.h','src/dsd_coeffs.h',
        'tests/dsd/test_p10.c','tests/dsd/p10_corpus.py','tests/dsd/p17_qualify_guards.py',
        'tests/dsd/p19_qualify_dsd1024.py','tests/dsd/test_p19_cross_isa.py',
        'tests/dsd/p19_audio_compare.py','tests/dsd/p19_soak_run.py',
        'tests/dsd/p19_soak_assess.py','tests/dsd/generate_p19_candidate_certificate.py',
        'tests/dsd/generate_p17_qualification_certificates.py',
        'tests/dsd/reference/p17_guards.json',
        'tests/dsd/reference/p17_qualification_certificates.json',
        'src/dsd_p17_certificates.h',
        'tests/dsd/reference/p19_dsd1024_v2_guard.json',
        'tests/dsd/results/P19_DSD1024_CORRECTION/holdout-summary.json',
        'tests/dsd/results/P19_DSD1024_CORRECTION/cross-isa.json',
        'tests/dsd/results/P19_DSD1024_CORRECTION/audio-v1-v2-comparison.json'
    ]
    for folder in ('training','holdout','executables','preimage','soak-smoke'):
        names += [str(p.relative_to(ROOT)) for p in sorted((RESULTS / folder).rglob('*'))
                  if p.is_file()]
    sources = {name:sha(ROOT / name) for name in sorted(set(names))}
    record = dict(schema='P19/experimental-DSD1024-v2-certificate/1',
        profile=p19.ID, rate_hz=p19.RATE,qualified=False,
        production_capability_enabled=False,
        decision='NUMERICAL_CORRECTION_PASS__HIGH_RATE_WRITE_UNQUALIFIED',
        method='separate seventh-order CLANS7 at native DSD1024 clock; v1 retained, low-rate unchanged',
        gates=dict(training='PASS_17_OF_17',heldout='PASS_36_OF_36',
            cross_isa='PASS_25_OF_25',frozen_guards='PASS_SOURCE_BOUND',
            audio_diagnostic='PASS_DIAGNOSTIC_ONLY',
            prepared_host_sustained_3600s='UNRUN',independent_media='UNRUN',
            independent_reference_audio='UNRUN',highrate_writer_interop='NOT_CLAIMED',
            production_enable='DISABLED'),
        soak_smoke=smoke,guard_bounds=frozen['bounds'],
        training_executable_sha256=sha(training_exe),
        guarded_executable_sha256=sha(guarded_exe),
        previous_p17_certificate_sha256=sha(RESULTS/'preimage/p17_qualification_certificates.json'),
        source_and_evidence_sha256=sources,
        note='Reproducible digest of experimental evidence, not cryptographic provenance authentication')
    digest = hashlib.sha256(canonical(record)).hexdigest()
    return json.dumps({'certificate_sha256':digest,'record':record},
                      indent=2,sort_keys=True,allow_nan=False)+'\n'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    try:
        actual=generate()
        if args.check:
            require(OUT.is_file() and OUT.read_text()==actual,
                    'P19 certificate missing/stale/mutated')
            print('P19 certificate PASS_CHECK: v2 remains unqualified')
        else:
            OUT.write_text(actual)
            print('P19 certificate GENERATED: v2 remains unqualified')
        return 0
    except (RuntimeError,KeyError,ValueError,FileNotFoundError,AssertionError) as ex:
        print('P19 certificate FAIL:',ex,file=sys.stderr)
        return 1

if __name__=='__main__':
    raise SystemExit(main())
