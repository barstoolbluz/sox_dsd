#!/usr/bin/env python3
"""Rebuild/check an UNQUALIFIED, source-bound P20 DSD512 candidate record.

The SHA-256 digest is an integrity binding, not a signature or permission to
activate production writing. The original 3,600-second DSD512-v1 failure is
operator evidence; a corrected v2 sustained qualification is still required.
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
RESULTS = ROOT / 'tests/dsd/results/P20_DSD512_CORRECTION'
OUT = ROOT / 'tests/dsd/reference/p20_dsd512_v2_certificate.json'
sys.path.insert(0, str(ROOT / 'tests/dsd'))
import p20_qualify_dsd512 as p20
import p17_qualify_guards as p17


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as source:
        for b in iter(lambda: source.read(4 << 20), b''):
            h.update(b)
    return h.hexdigest()


def load(path):
    return json.loads(Path(path).read_text(),
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def rel(path):
    return str(Path(path).relative_to(ROOT))


def generate():
    training_bin = RESULTS / 'executables/training-dsd_test_p10'
    guarded_bin = RESULTS / 'executables/guarded-dsd_test_p10'
    runner_preimage = RESULTS / 'preimage/p20-training-runner.py'
    require(training_bin.is_file() and guarded_bin.is_file(), 'archived experimental binaries missing')
    p20.verify(SimpleNamespace(unit=guarded_bin))
    require(p20.adjudicate(SimpleNamespace(unit=guarded_bin)) == 0,
            'guarded P20 holdout failed')
    frozen = load(p20.FROZEN)
    holdout = load(RESULTS / 'holdout-summary.json')
    require(frozen['profile'] == p20.ID and frozen['qualified'] is False and
            frozen['rate_hz'] == p20.RATE and frozen['training_case_count'] == 17 and
            frozen['rejected_case_count'] == 0 and
            frozen['holdout_used_to_set_bounds'] is False and
            sha(training_bin) == frozen['executable_sha256'],
            'P20 training provenance/guard proof invalid')
    require(holdout['profile'] == p20.ID and holdout['qualified'] is False and
            holdout['result'] == 'PASS' and holdout['case_count'] == 36 and
            holdout['frozen_guard_sha256'] == sha(p20.FROZEN) and
            holdout['executable_sha256'] == sha(guarded_bin) and
            sha(training_bin) != sha(guarded_bin),
            'P20 guarded holdout not source-bound or incomplete')
    statuses = [x['status'] for x in holdout['cases']]
    require(statuses.count('PASS') == 33 and
            statuses.count('OBSERVED_FULLSCALE_NOT_NOMINAL') == 2 and
            statuses.count('PASS_EXPECTED_INTERPOLATION_OVERLOAD') == 1,
            'P20 holdout disposition differs from frozen P17 partitions')
    for split, binary, runner in (('training', training_bin, runner_preimage),
                                  ('holdout', guarded_bin,
                                   ROOT/'tests/dsd/p20_qualify_dsd512.py')):
        rows = p20.full_split(split)
        require(len(rows) == (17 if split == 'training' else 36),
                'incomplete '+split)
        expected_codes = {
            'src/sdm_p20_candidates.h': sha(ROOT/'src/sdm_p20_candidates.h'),
            'tests/dsd/p10_corpus.py': sha(ROOT/'tests/dsd/p10_corpus.py'),
            'tests/dsd/p17_qualify_guards.py': sha(ROOT/'tests/dsd/p17_qualify_guards.py'),
            'tests/dsd/p20_qualify_dsd512.py': sha(runner),
        }
        for path, rec in rows:
            require(rec['schema'] == 'P20/v2-DSD512-case/1' and
                    rec['profile'] == p20.ID and rec['split'] == split and
                    rec['code_sha256'] == expected_codes and
                    rec['executable_sha256'] == sha(binary) and
                    rec['complete'] is True and
                    rec['output_bytes'] >= 0 and
                    rec['render']['profile'] == p20.ID,
                    'case provenance incomplete or inconsistent: '+rel(path))
        reference = (frozen['training_receipts_sha256'] if split == 'training'
                     else holdout['case_receipts_sha256'])
        require(set(reference) == {rel(path) for path, _ in rows} and
                all(reference[rel(path)] == sha(path) for path, _ in rows),
                'receipt was changed after freeze: '+split)

    isa = load(RESULTS/'cross-isa.json')
    require(isa['profile'] == p20.ID and isa['qualified'] is False and
            isa['status'] == 'PASS' and isa['binary_sha256'] == sha(guarded_bin) and
            isa['candidate_sha256'] == sha(ROOT/'src/sdm_p20_candidates.h') and
            isa['guard_sha256'] == sha(ROOT/'src/pcmdsd_p20_guards.h'),
            'ISA experiment provenance mismatch')
    expected = set(itertools.product(('scalar','sse2','avx1','avx2','avx512'),
                                      (1,16,17,21,25)))
    require(isa['tiers'] == ['scalar','sse2','avx1','avx2','avx512'] and
            isa['test_case_indices'] == [1,16,17,21,25] and
            len(isa['cases']) == 25 and
            {(r['tier'],r['index']) for r in isa['cases']} == expected and
            all(r['passed'] is True and r['excursion28'] == 0 for r in isa['cases']),
            'ISA case matrix incomplete or failed')
    case_defs = p20.cases('holdout')
    for row in isa['cases']:
        require(row['case'] == case_defs[row['index']]['name'] and
                0 <= row['min_ones28'] <= row['max_ones28'] <= 28,
                'ISA case identity/counters unexpected')
        if row['index'] == 25:
            require(row['failure'] == 2 and row['kernel_exit'] != 0,
                    'expected overload did not reject')
        else:
            require(row['failure'] == row['kernel_exit'] == 0 and row['frames'] > 0,
                    'accepted ISA case faulted')
    oracle = load(RESULTS/'bitstream-oracle.json')
    require(oracle['profile'] == p20.ID and oracle['qualified'] is False and
            len(oracle['cases']) == 4 and
            {r['case'] for r in oracle['cases']} ==
            {'tone-997--6','dc-positive','dc-negative','limited'},
            'independent packed-bit oracle cases missing')
    for row in oracle['cases']:
        match = [v for v in isa['cases'] if v['tier'] == 'scalar' and v['case'] == row['case']]
        require(len(match) == 1, 'missing scalar oracle match')
        counters = row['verified_monitor']
        require(counters['min_ones28'] == match[0]['min_ones28'] and
                counters['max_ones28'] == match[0]['max_ones28'] and
                row['native_frames'] == match[0]['frames'] and
                counters['windows28'] == row['native_frames'] - 27,
                'independent packed bit analysis mismatched monitor')
    require(next(x for x in oracle['cases'] if x['case']=='dc-negative')
            ['verified_monitor']['min_ones28'] == 6,
            'non-nominal extrema must not be concealed')

    audio = load(RESULTS/'audio-v1-v2-comparison.json')
    require(audio['native_hz'] == p20.RATE and
            audio['candidate_qualified'] is False and
            audio['comparison_only'] is True and
            audio['reference_coeff_sha256'] == sha(ROOT/'src/dsd_coeffs.h') and
            set(audio['versions']) == {'v1','v2'},
            'reconstruction diagnostic not independently source-bound')
    for name in ('v1','v2'):
        row = audio['versions'][name]
        require(row['renderer_sha256'] == sha(guarded_bin) and
                row['numeric_profile_id'] == 'encode.mastering.'+name+'.dsd512' and
                row['output_native_frames'] == 36_126_720 and
                row['diagnostic']['clipping_count'] == 0 and
                row['excursions28'] == 0,
                'invalid diagnostic for '+name)
    noise_penalty_db = (audio['versions']['v2']['diagnostic']['residual_dbfs_rms'] -
                        audio['versions']['v1']['diagnostic']['residual_dbfs_rms'])
    require(noise_penalty_db > 0, 'recorded audio comparison changed unexpectedly')

    smoke = {}
    for mode,seconds in (('original',1),('nominal',300)):
        prefix = RESULTS/'soak-smoke'/mode
        assessment = load(Path(str(prefix)+'-assessment.json'))
        execution = load(Path(str(prefix)+'-execution.json'))
        raw = load(Path(str(prefix)+'-result.json'))
        require(assessment['status'] == 'PASS_SHORT_SMOKE_ONLY' and
                assessment['qualified'] is False and
                assessment['execution_verified'] is True and
                assessment['seconds'] == execution['seconds'] == seconds and
                assessment['sample_executable_sha256'] == sha(guarded_bin) and
                assessment['raw_report_sha256'] == sha(Path(str(prefix)+'-result.json')) and
                assessment['execution_receipt_sha256'] == sha(Path(str(prefix)+'-execution.json')) and
                execution['runner_sha256'] == sha(ROOT/'tests/dsd/p20_soak_run.py') and
                execution['candidate_sha256'] == sha(ROOT/'src/sdm_p20_candidates.h') and
                execution['source_sha256'] == sha(ROOT/'tests/dsd/test_p10.c') and
                execution['executable_sha256'] == sha(guarded_bin) and
                execution['frozen_guard_sha256'] == sha(p20.FROZEN) and
                execution['exit_code'] == 0 and
                raw['profile'] == p20.ID and
                raw['processed_native_frames'] == seconds*p20.RATE and
                raw['excursions28'] == 0,
                'soak smoke source identity or counters mismatch: '+mode)
        require(all(sha(prefix.parent/name) == digest
                    for name,digest in assessment['snapshot_sha256'].items()) and
                execution['final_snapshot_sha256'] == sha(Path(str(prefix)+'-final.state')),
                'soak snapshot digest mismatch: '+mode)
        smoke[mode] = dict(status=assessment['status'],seconds=seconds,
                           frames=raw['processed_native_frames'],
                           population_min=raw['min_ones28'],
                           population_max=raw['max_ones28'],
                           longest_run=raw['longest_run'])

    historical = load(RESULTS/'preimage/p17_qualification_certificates.json')
    current = load(ROOT/'tests/dsd/reference/p17_qualification_certificates.json')
    require(historical == current and
            all(not p['qualified'] and not p['production_capability_enabled']
                for p in current['profiles'].values()),
            'frozen P17 registry/promotions changed')
    require(current['profiles']['encode.mastering.v1.dsd512']['qualified'] is False,
            'known failing v1 remains unqualified')
    for file_name, digest in (
        ('src/sdm_p17_candidates.h',
         'ef7aab79738ae017d32132e25366ec453ca970e42ecb748c350a58badcd7acb6'),
        ('src/pcmdsd_guards.h',
         'af8459f4a0b5512380e24b9c0ec66d575a0995d88fb57ae81ffeb2517982320b')):
        require(sha(ROOT/file_name) == digest, 'frozen historical implementation edited: '+file_name)
    profile_src=(ROOT/'src/pcmdsd.c').read_text()
    sdm_src=(ROOT/'src/sdm.c').read_text()
    require('"encode.mastering.v2.dsd512",22579200,176400,40000,80000,'
            in profile_src and
            'lsx_pcmdsd_coeff_master64_256,61,lsx_pcmdsd_p20_guards,0,NULL' in profile_src and
            '"encode.mastering.v1.dsd512", &lsx_sdm_p17_candidates[0], 176400'
            in sdm_src and
            '"encode.mastering.v2.dsd512", &lsx_sdm_p20_dsd512, 176400'
            in sdm_src,
            'candidate identity, v1 integrity, or production gate mismatch')
    p18 = load(ROOT/'tests/dsd/reference/p18_fixture_matrix.json')
    require(p18['high_rate_capability'] == 'DISABLED' and
            all(x['reader'] == 'REFUSED_UNQUALIFIED' and
                x['writer'] == 'REFUSED_UNQUALIFIED' for x in p18['cases']) and
            all(x['transport'] == 'REFUSED_UNQUALIFIED' for x in p18['dop_cases']),
            'P18 high-rate capability evidence changed')

    operator_result = ROOT/'tests/dsd/results/P19_OPERATOR_QUALIFICATION_2026-10-22/soak/d512-v2-result.json'
    failure = load(operator_result)
    require(failure['profile'] == 'encode.mastering.v1.dsd512' and
            failure['processed_native_frames'] == p20.RATE*3600 and
            failure['min_ones28'] == 6 and failure['failure'] == 0 and
            failure['excursions28'] == 0 and failure['min_ones28'] < 7,
            'operator-provided P19 v1 failure could not be read consistently')

    names = [
        'src/sdm.c','src/sdm.h','src/sdm_p17_candidates.h',
        'src/sdm_p19_candidates.h','src/sdm_p20_candidates.h',
        'src/pcmdsd.c','src/pcmdsd.h','src/pcmdsd_guards.h',
        'src/pcmdsd_v2_guards.h','src/pcmdsd_p20_guards.h',
        'src/pcmdsd_coeffs.h','src/dsd_coeffs.h',
        'tests/dsd/test_p10.c','tests/dsd/p10_corpus.py',
        'tests/dsd/p17_qualify_guards.py','tests/dsd/p20_qualify_dsd512.py',
        'tests/dsd/p20_soak_run.py','tests/dsd/p20_soak_assess.py',
        'tests/dsd/test_p20_cross_isa.py','tests/dsd/test_p20_bitstream_oracle.py',
        'tests/dsd/p20_audio_compare.py','tests/dsd/generate_p20_candidate_certificate.py',
        'tests/dsd/generate_p19_candidate_certificate.py',
        'tests/dsd/reference/p17_guards.json',
        'tests/dsd/reference/p17_qualification_certificates.json',
        'tests/dsd/reference/p18_fixture_matrix.json',
        'tests/dsd/reference/p19_dsd1024_v2_certificate.json',
        'tests/dsd/reference/p20_dsd512_v2_guard.json',
        rel(operator_result),
    ]
    for folder in ('training','holdout','executables','preimage','soak-smoke'):
        names.extend(rel(path) for path in (RESULTS/folder).rglob('*') if path.is_file())
    for file_name in ('holdout-summary.json','cross-isa.json',
                      'bitstream-oracle.json','audio-v1-v2-comparison.json'):
        names.append(rel(RESULTS/file_name))
    evidence_sha256 = {name:sha(ROOT/name) for name in sorted(set(names))}
    record = dict(schema='P20/experimental-DSD512-v2-certificate/1',
        profile=p20.ID,rate_hz=p20.RATE,qualified=False,
        production_capability_enabled=False,
        decision='EXPERIMENTAL_CORRECTION_PASS__SUSTAINED_AND_AUDIO_UNQUALIFIED',
        method='Independent DSD512 CLANS-7 recurrence and frozen 17-case training guards; v1 unchanged',
        gates=dict(training='PASS_17_OF_17',holdout='PASS_36_OF_36',
                   cross_isa='PASS_25_OF_25',
                   independent_packed_bit_check='PASS_4_OF_4',
                   frozen_guards='PASS_SOURCE_BOUND',
                   source_rebuild_and_regressions='SEE_HANDOFF_TEST_LOG',
                   prepared_host_sustained_3600s='UNRUN_FOR_V2',
                   independent_media='UNRUN_FOR_V2',
                   audio_diagnostic='OBSERVED_V2_NOISE_INCREASE_NOT_RELEASE_ADJUDICATION',
                   independent_reference_audio='UNRUN',
                   highrate_writer_interop='NOT_CLAIMED',
                   production_enable='DISABLED'),
        soak_smoke=smoke,
        audio_synthetic_v2_minus_v1_residual_db=round(noise_penalty_db,6),
        operator_v1_observed_min_ones28=6,
        training_executable_sha256=sha(training_bin),
        guarded_executable_sha256=sha(guarded_bin),
        preimage_p17_certificate_sha256=sha(RESULTS/'preimage/p17_qualification_certificates.json'),
        preimage_p19_certificate_sha256=sha(RESULTS/'preimage/p19_dsd1024_v2_certificate.json'),
        source_and_evidence_sha256=evidence_sha256,
        limitations=('No one-hour P20 soak; no commercial P20 encoded media; reconstructed audio '
                     'is a synthetic diagnostic, not an independent quality adjudication. '
                     'No production format or DoP capability is authorized.'))
    digest = hashlib.sha256(canonical(record)).hexdigest()
    return json.dumps({'certificate_sha256':digest,'record':record},
                      sort_keys=True,indent=2,allow_nan=False)+'\n'


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    group=ap.add_mutually_exclusive_group(required=True)
    group.add_argument('--write',action='store_true')
    group.add_argument('--check',action='store_true')
    options=ap.parse_args()
    try:
        actual=generate()
        if options.check:
            require(OUT.is_file() and OUT.read_text()==actual,
                    'P20 candidate certificate stale, absent or modified')
            print('P20 PASS_CHECK: experimental only, writer disabled')
        else:
            if OUT.exists():
                require(OUT.read_text()==actual,
                        'refuse overwrite of P20 certificate with differing contents')
            else:
                OUT.parent.mkdir(parents=True,exist_ok=True)
                OUT.write_text(actual)
            print('P20 GENERATED: experimental only, writer disabled')
        return 0
    except (RuntimeError,KeyError,ValueError,FileNotFoundError,AssertionError,TypeError) as err:
        print('P20 CERTIFICATE FAIL: '+str(err),file=sys.stderr)
        return 1

if __name__=='__main__':
    raise SystemExit(main())
