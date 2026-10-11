#!/usr/bin/env python3
"""Check an explicit P10 reviewer certificate against source and retained receipts.

This is a verifier, not a certificate issuer or production-profile activator.
The privately held music and physical hardware cannot be re-executed here;
validation of their operator records is necessarily receipt-level.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from qualify_p10_ratification import assess

ROOT = Path(__file__).resolve().parents[2]
CERTIFICATE = ROOT / 'tests/dsd/results/P10_certification_2026-10-11/certification.json'
NATIVE_HZ = (2822400, 5644800, 11289600)
PROFILE_IDS = tuple(f'encode.mastering.v1.dsd{rate // 44100}' for rate in NATIVE_HZ)


def read(relative):
    return json.loads((ROOT / relative).read_text())


def digest(relative):
    return hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check(path=CERTIFICATE):
    certificate = json.loads(Path(path).read_text())
    require(certificate['schema'] == 'P10/explicit-reviewer-certification/1', 'wrong certificate schema')
    require(certificate['decision'] == 'CERTIFIED', 'not a positive certification')
    require(certificate['certified_profiles'] == list(PROFILE_IDS), 'unexpected certified profiles')
    require(certificate['kernel_family'] == 'scalar guarded P10 composite', 'unqualified kernel family')
    require(certificate['p10_phase'] == 'CLOSED' and certificate['p11'] == 'PERMITTED',
            'invalid phase disposition')
    require(certificate['p15_default_activation'] == 'NOT_AUTHORIZED',
            'certificate must not activate release defaults')
    require(certificate['production_profile_flags_modified'] is False,
            'positive evidence must not imply CLI activation')

    for path, claimed in certificate['input_sha256'].items():
        require(digest(path) == claimed, 'certificate evidence changed: ' + path)

    assessed = assess()
    require(assessed['status'] == 'PASS' and not assessed['remaining_release_gates'],
            'P10 gate collector is not passing')
    require(len(assessed['gates']) == 10 and
            all(g['status'] == 'PASS' for g in assessed['gates'].values()),
            'not all required criteria PASS')
    require(assessed['criteria_sha256'] == digest('tests/dsd/reference/p10_ratification_criteria.json'),
            'criteria mismatch')
    require(assessed['qualified'] is False and assessed['promotion'] == 'BLOCKED',
            'historical gate collector unexpectedly promotes profiles')
    baseline = read('tests/dsd/results/P10_gate_assessment_2026-10-11/assessment.json')
    require(assessed == baseline, 'versioned PASS gate assessment differs from recomputation')

    prepared = read('tests/dsd/results/P10_hotfix_throughput_2026-10-11/bench-read.json')
    require(prepared['status'] == 'pass' and not prepared['host_unqualified'] and
            not prepared['errors'] and prepared['pairs'] == 40 and prepared['warmups'] == 3,
            'new prepared-host performance receipt not admitted')
    summaries = prepared['summaries']
    require(len(summaries) == 16, 'read/repack benchmark incomplete')
    for name, row in summaries.items():
        require(row['status'] == 'pass' and row['samples'] == 40 and
                math.isfinite(row['measurement_noise']) and row['measurement_noise'] < .02 and
                row['regression_percent'] < 5., 'read/repack performance gate: '+name)
        if '-repack-' in name:
            require(row['arms_agree'] is True and
                    row['output_sha256']['baseline'] == row['output_sha256']['candidate'],
                    'read/repack output hash differs: '+name)

    folder = 'tests/dsd/results/P10_realworld_corpus_2026-10-10/'
    pcm = read(folder + 'pcm-corpus.json')
    sources = read(folder + 'pcm-sources.json')
    unity = read(folder + 'pcm-unity.json')
    require(pcm['configuration']['sox_sha256'] == prepared['candidate_sha256'],
            'PCM source and new prepared-host binaries differ')
    require(len(pcm['entries']) == 17 and len(sources) == len(unity) == 51,
            'PCM corpus missing independent entries')
    entries = {e['excerpt_wav_sha256']: e for e in pcm['entries']}
    require(len(entries) == 17 and len({e['release'] for e in entries.values()}) == 17,
            'PCM corpus release/recording identities not independent')
    require(all(e['flac_crc_test_passed'] is True and e['streaminfo_md5_present'] is True and
                len(e['source_streaminfo_md5']) == 32 for e in entries.values()),
            'PCM input decode integrity evidence missing')
    targets = {(e['excerpt_wav_sha256'], t['native_hz']): (e, t)
               for e in pcm['entries'] for t in e['targets']}
    require(len(targets) == 51, 'PCM target measurements missing or duplicated')
    for source, render in zip(sorted(sources, key=lambda r: (r['excerpt_sha256'], r['native_hz'])),
                              sorted(unity, key=lambda r: (r['excerpt_sha256'], r['native_hz']))):
        key = (source['excerpt_sha256'], source['native_hz'])
        require(key in targets and key == (render['excerpt_sha256'], render['native_hz']),
                'PCM manifest-to-render identity mismatch')
        entry, target = targets[key]
        require(source['release'] == entry['release'] == render['release'] and
                source['source_rate_hz'] == entry['source_rate_hz'] == render['source_rate_hz'],
                'PCM provenance/rate mismatch')
        require(render['reconstruction_reference'] == target['reconstructed_reference'] == 'sacd',
                'incorrect ordinary-PCM reconstruction reference')
        require(render['admitted'] is True and target['admitted'] is True and
                target['status'] == 'pass' and target['frames_exact'] is True and
                render['output_frames'] == target['output_frames_per_channel'] and
                render['per_channel'] == target['per_channel'] and
                render['output_bytes'] == target['output_bytes'] and
                target['windows_per_channel'] == render['output_frames']-27,
                'PCM per-source frame or bit-window evidence differs')
        require(len(target['output_dsf_sha256']) == 64 and
                abs(render['rms_delta_db']) <= .25 and
                abs(render['peak_delta_db']) <= .5,
                'PCM output digest or reference levels unacceptable')

    profiles = read('tests/dsd/reference/p10_profiles.json')
    require(profiles['default_promotion'] is False and
            all(p['qualified'] is False for p in profiles['profiles']),
            'P15 activation/profile registry must remain untouched')
    return dict(status='PASS', profiles=list(PROFILE_IDS), gates=len(assessed['gates']),
                corpus='PASS', prepared_host='PASS',
                caveat='Receipt validation, not re-rendering privately held audio or attesting a hardware host')


def main():
    try:
        result = check()
    except (OSError, KeyError, TypeError, ValueError, AssertionError) as exc:
        print(json.dumps(dict(status='FAIL', reason=str(exc)), sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
