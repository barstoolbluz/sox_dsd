#!/usr/bin/env python3
"""Adjudicate P15 closeout receipts without altering historical evidence.

A successful run means this bounded evidence audit completed, not that P15 is
release-qualified. The documented gate scopes are review decisions, not
automatic numerical threshold relaxation or new hardware measurements.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import sys
import tempfile

from adjudicate_p10_p15_corpus import run as compare_corpus
from check_p15_avx1_receipt import inspect_receipt

ROOT = Path(__file__).resolve().parents[2]
RESULTS = Path('tests/dsd/results')
MATRIX = RESULTS / 'P15_matrix_metrology_2026-10-14'
AVX1 = RESULTS / 'P15_avx1_physical_2026-10-13'
TARGET = RESULTS / 'P15_audit_prepared_host_2026-10-13'
SOAKS = RESULTS / 'P15_soaks_every_profile_isa_2026-10-13'
CORPUS = RESULTS / 'P15_corpus_independent_material_2026-10-13'
TIERS = ('scalar', 'sse2', 'avx1', 'avx2', 'avx512')
RATES = (2822400, 5644800, 11289600)
PCM_RATES = (44100, 48000, 88200, 96000, 176400, 192000,
             352800, 384000, 705600)
PROFILES = ('mastering', 'wideband')
GATE_IDS = (
    'P15-full-3x9x2-numerical-release-matrix',
    'P15-physical-Intel-AVX512-performance',
    'P15-physical-older-AVX-performance',
    'P15-2x-six-channel-DSD256-controlled-reference-target',
    'P15-current-full-release-soaks-every-profile-ISA',
    'P15-current-independent-codec-and-hardware-corpus',
)


def load(path: Path):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


def digest(path: Path) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def check(condition: bool, explanation: str):
    if not condition:
        raise ValueError(explanation)


def check_source_hashes(session: dict):
    for name, expected in session['reference_inputs'].items():
        # This compiled static archive is intentionally not in a source tree.
        if name == 'src/.libs/libsox_ng.a':
            continue
        check(digest(Path(name)) == expected, 'measured session source differs: ' + name)


def matrix_review() -> dict:
    base = MATRIX / 'scalar-full'
    first = load(base / 'session.json')
    check(first['mode'] == 'full' and first['frames'] == 262144,
          'matrix full-duration session absent')
    check_source_hashes(first)
    expected = {f'dsd{native//44100}.{profile}.pcm{pcm}'
                for native in RATES for profile in PROFILES for pcm in PCM_RATES}
    absent_vectors = 0
    full_ledger = {}
    tier_ledgers = {}
    forced = 0
    detailed = 0
    identical_binary64 = 0
    cross_isa_max_delta = 0.0
    for name in ('scalar-full', *(f'isa/{tier}' for tier in TIERS)):
        folder = MATRIX / name
        session = load(folder / 'session.json')
        check_source_hashes(session)
        check(set(session['cells']) == expected, 'matrix worklist incomplete: ' + name)
        check(session['frames'] == first['frames'] and
              session['worklist_sha256'] == first['worklist_sha256'],
              'matrix session differs: ' + name)
        cells = folder / 'cells'
        actual = {p.stem for p in (ROOT / cells).glob('*.json')}
        check(actual == expected, 'matrix cell files incomplete: ' + name)
        for ident in sorted(expected):
            path = cells / (ident + '.json')
            check((ROOT / path.with_suffix('.sha256')).read_text().strip() == digest(path),
                  'matrix cell digest mismatch: ' + name + '/' + ident)
            row = load(path)
            check(row['id'] == ident and row['qualified'] is False and
                  row['status'] == 'MEASURED_PENDING_INDEPENDENT_SPECTRAL_REVIEW',
                  'incorrect matrix status/identity: ' + name + '/' + ident)
            check(row['output_frames_measured'] == row['output_count_exact'],
                  'matrix count mismatch: ' + name + '/' + ident)
            check(row['production_src_spectral']['status'] in ('SAMPLED_PASS', 'IDENTITY_BYPASS'),
                  'sampled SRC failed or unmeasured: ' + name + '/' + ident)
            if name == 'scalar-full':
                check(row['production_graph']['status'] == 'PASS',
                      'missing claimed graph evidence: ' + ident)
                check(row['isolated_fir']['metric']['max_abs'] <= row['isolated_fir']['roundoff_bound'],
                      'observed native FIR error exceeds predeclared FIR-only bound')
                full_ledger[ident] = row['scalar_program']['receipt']['binary64_sha256']
                tier_ledgers[ident] = {}
            else:
                check(row['scalar_program']['receipt']['binary64_sha256'] ==
                      full_ledger[ident],
                      'forced session scalar baseline differs: ' + name + '/' + ident)
            if name != 'scalar-full' and name != 'isa/scalar':
                tier = name.split('/')[1]
                entry = row['cross_isa']
                check(len(entry) == 1 and entry[0]['tier'] == tier and
                      entry[0]['status'] == 'MEASURED',
                      'ISA missing or unmeasured: ' + name + '/' + ident)
                tier_ledgers[ident][tier] = entry[0]['receipt']['binary64_sha256']
                forced += 1
                detailed += int(entry[0]['detailed_cross_isa'])
                identical_binary64 += int(entry[0]['receipt']['binary64_sha256'] ==
                                          full_ledger[ident])
                cross_isa_max_delta = max(cross_isa_max_delta,
                                          entry[0]['same_cell_scalar_composite']['max_abs'])
            # Cell digests verify *written summaries*, not absent raw waveforms.
            check(row['raw_receipt']['file'] == 'arrays/' + ident + '.npz',
                  'incorrect raw vector locator: ' + name + '/' + ident)
            absent_vectors += int(not (ROOT / folder / row['raw_receipt']['file']).is_file())
    check(forced == 216 and detailed == 96,
          'missing forced ISA or detailed cell obligations')
    # The historical README claimed full-binary64 identity. The actual
    # four tier hashes differ from scalar, within lawful roundoff.
    check(identical_binary64 == 0, 'cross-ISA hash ledger changed; reassess the observation')
    check(all(len(set((full_ledger[ident], *tier_ledgers[ident].values()))) == 4
              and tier_ledgers[ident]['avx1'] == tier_ledgers[ident]['avx2']
              for ident in expected),
          'four distinct binary64 tier hashes not supported across all matrix cells')
    check(absent_vectors == 324,
          'raw arrays newly present; rerun the full independent matrix verifier')
    check(load(base / 'summary.json')['release_gate_closed'] is False,
          'instrument illegitimately marks matrix release-qualified')
    return dict(measured_scalar_cells=54, forced_isa_jobs=270,
                detailed_cross_isa_comparisons=96, equal_binary64_forced_pairs=identical_binary64,
                max_recorded_cross_isa_binary64_difference=cross_isa_max_delta,
                missing_npz_vectors=absent_vectors, required_src_graph_raw_files_in_archive=False,
                independent_full_composite_spectral_certificate=False,
                independent_complete_src_roundoff_envelope=False,
                note='All 324 written cell rows have valid digests; raw vectors are omitted. The claim of 54/54 full-binary64 bit identity is false: none of 216 forced-tier hashes matches scalar, though residuals are tiny and permitted.')


def older_avx_review() -> dict:
    review = inspect_receipt(ROOT / AVX1)
    check(not review['problems'], 'older AVX receipt inadmissible: ' + '; '.join(review['problems']))
    data = load(AVX1 / 'kernel/kernel-timing.json')
    medians = {}
    for mode in ('fir-single', 'fir-block', 'sdm'):
        median = {}
        for tier in ('scalar', 'sse2', 'avx1'):
            vals = [row['cpu_ns_per_frame'] for row in data['raw']
                    if row['mode'] == mode and row['tier'] == tier and row['exit'] == 0]
            check(len(vals) == 15 and all(math.isfinite(x) and x > 0 for x in vals),
                  'older AVX incomplete raw timings: ' + mode + '/' + tier)
            median[tier] = round(statistics.median(vals), 3)
        medians[mode] = median
    return dict(host_model=review['host']['model'], physical_older_avx_reported=True,
                no_avx2_reported=True, repetitions_per_case=15, controlled_clock_mhz=3000,
                kernel_cpu_ns_per_frame_median=medians,
                limitation='Physical AVX1-only kernel timing and forced correctness; no new ISA preference or universal end-to-end performance claim.')


def target_review() -> dict:
    data = load(TARGET / 'bandwidth-matched.json')
    check(not data['errors'] and data['target'] == 2.0 and
          data['reps'] == 9 and data['warmups'] == 2,
          'reported DSD256 benchmark metadata invalid')
    check(data['speedup_vs_unmatched'] >= 2 and data['speedup_vs_matched'] >= 2,
          'recorded benchmark does not exceed target')
    log = (ROOT / TARGET / 'dsd256-2x-target.log').read_text()
    check('95% CI [3.77x, 3.84x]' in log and '95% CI [3.92x, 3.97x]' in log,
          'DSD256 target log does not match reported confidence intervals')
    # The directory contains a console transcription and summary, not the
    # 15 individual observations/commands/inputs used to derive the intervals.
    return dict(logged_lower_95_percent_ci=[3.77, 3.92],
                bandwidth_matched_reference_reported=True,
                matched_control_repetitions=9,
                individual_target_timing_samples_in_archive=False,
                fixed_host_and_exact_command_receipt_in_archive=False,
                note='Promising reported speedup, but no raw 15-pair timing record to audit the CI or verify the staged bandwidth-matched comparator.')


def soaks_review() -> dict:
    summary = load(SOAKS / 'summary.json')
    check(isinstance(summary, list) and len(summary) == 15,
          'missing or duplicate P15 soak summary records')
    guards = load(Path('tests/dsd/reference/p10_guards.json'))['profiles']
    observed = set()
    absent_states = 0
    absent_exec = 0
    for row in summary:
        family, native = row['family'], row['native_hz']
        key = (family, native)
        check(family in TIERS and native in RATES and key not in observed,
              'soak identity invalid or duplicated')
        observed.add(key)
        name = SOAKS / family / ('soak-' + str(native))
        config = load(Path(str(name) + '-configuration.json'))
        report = load(Path(str(name) + '-result.json'))
        expected = 3600 * native
        check(config['seconds'] == 3600 and config['segment_seconds'] == 60 and
              config['fixture_version'] == 'nominal-v2', 'incorrect soak config')
        check(report['native_hz'] == native and report['mode'] == 'soak-nominal-v2' and
              report['status'] == 3 and report['failure'] == 0 and
              report['first_bad_frame'] is None and report['nonfinite_states'] == 0 and
              report['committed_native_frames'] == expected and
              report['processed_native_frames'] == expected and
              report['monitor_overloads_nominal_half'] == 0 and
              report['windows28'] == expected - 27 and
              report['input_frames'] == 3600 * config['source_hz'],
              'soak counters/status invalid: ' + str(key))
        check(report['profile'] == f'encode.mastering.v1.dsd{native//44100}',
              'incorrect soak profile: ' + str(key))
        max_state = report['max_abs_state']
        bounds = guards[str(native)]['bounds']
        check(len(max_state) == len(bounds) == 8 and
              all(math.isfinite(a) and a <= b for a,b in zip(max_state,bounds)),
              'soak guard limit exceeded: ' + str(key))
        if native == RATES[0]:
            check(report['excursions28'] == 0 and
                  4 <= report['min_ones28'] <= report['max_ones28'] <= 24,
                  'DSD64 soak bit population invalid')
        states = list((ROOT / SOAKS / family).glob(f'soak-{native}-*.state'))
        if len(states) != 61:
            absent_states += 1
        if not (ROOT / Path(str(name) + '-execution.json')).is_file():
            absent_exec += 1
    check(observed == {(tier,rate) for tier in TIERS for rate in RATES},
          'soak matrix incomplete')
    return dict(clean_reported_hour_long_encode_runs=15,
                complete_61_state_snapshot_sets=15-absent_states,
                execution_receipts_present_for=15-absent_exec,
                one_hour_decode_soak_new_requirement=False,
                note='The 15 clean reported encoder observations are valuable; their continuation-state hashes and executable receipts are missing. Do not add an unmandated 1-hour decoder soak.')


def corpus_review() -> dict:
    comp = compare_corpus(ROOT / RESULTS / 'P10_realworld_corpus_2026-10-10',
                          ROOT / CORPUS / 'dsd')
    check(comp['status'] == 'PASS-BOUNDED-DRIFT' and not comp['errors'] and
          comp['summary']['records_compared'] == 40,
          'independent DSD material no longer matches accepted comparison scope')
    for native in RATES:
        rows = load(CORPUS / 'pcm' / str(native) / 'pcm-unity.json')
        check(len(rows) == 17, 'external PCM corpus size changed: '+str(native))
        for row in rows:
            check(row['admitted'] is True and row['frames_exact'] is True and
                  (native != RATES[0] or row['population_within_4_24'] is True) and
                  row['encode_exit'] == 0 and
                  row['output_frames'] == row['expected_frames'] and
                  row['output_rate'] == native,
                  'invalid present-version PCM corpus row: '+str(native))
    return dict(independent_dsd_source_excerpts=18,
                independent_pcm_source_recordings=17,
                pcm_encode_rate_observations=51,
                recorded_dsd_source_arm_comparisons=40,
                distinct_changed_dsd_extrema_fields=comp['summary']['changed_numeric_fields'],
                original_private_audio_distributed=False,
                physical_player_or_dac_verified=False,
                scope='Software-only source-material/DSF/FLAC evidence. No independent DAC, player, digital transport or device-compatibility claim.')


def report() -> dict:
    check(load(RESULTS/'P15/release/release-manifest.json')['status'] == 'BLOCKED',
          'historical P15 release inventory unexpectedly changed')
    measurements = dict(matrix=matrix_review(), older_avx=older_avx_review(),
                        dsd256_target=target_review(), soaks=soaks_review(),
                        independent_corpus=corpus_review())
    dispositions = (
        ('OPEN', 'Full SRC spectral extrema/coherent-image proof and comparable numerical tolerance missing; independent raw vector validation blocked by omitted files.'),
        ('UNRUN', 'No physical Intel AVX-512 pinned performance receipt. Client-CPU availability does not remove the release requirement.'),
        ('PASS-SCOPED', 'Authentic-looking, coherent Ivy Bridge AVX1-only 15-repeat kernel throughput/correctness records. No AVX1 preference promoted.'),
        ('UNVERIFIED', 'Reported 95% CI clears target, but no raw timed samples, exact benchmark commands or auditable matched staged control.'),
        ('PARTIAL', '15 one-hour encoder measurements clean; required 61-state snapshot sets and executable receipts absent. No extra 1-hour decoder criterion invented.'),
        ('PASS-SCOPED', 'Present-version independent DSD/PCM source material passes recorded criteria; physical device certification not required for software-only claims under DSD_DESIGN section 13, and is not asserted.'),
    )
    gates = [dict(id=ident, status=status, reason=reason)
             for ident,(status,reason) in zip(GATE_IDS,dispositions)]
    required = [gate['id'] for gate in gates if gate['status'] not in ('PASS','PASS-SCOPED')]
    return dict(schema='P15/closeout-adjudication/1', decision_date='2026-10-14',
                source_archive_sha256='6e7739527e3b976ead736db91cebd578c7908a02a00c49f348fabdb22863726c',
                baseline_ledger='tests/dsd/results/P15/release/release-manifest.json',
                baseline_ledger_sha256=digest(RESULTS/'P15/release/release-manifest.json'),
                gates=gates, evidence=measurements, mandatory_unclosed=required,
                release_status='BLOCKED', default_promotion_authorized=False,
                p16_authorized=False,
                policy='Legacy defaults retained; no new ISA auto preference, device compatibility claim or P16 implementation.',
                note='A passing audit is evidence integrity, not permission to activate an unfinished release.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--require-qualified',action='store_true')
    args = parser.parse_args()
    try:
        obj = report()
        out = args.output.resolve()
        out.parent.mkdir(parents=True,exist_ok=True)
        payload = json.dumps(obj,indent=2,sort_keys=True,allow_nan=False)+'\n'
        temp_name = None
        try:
            with tempfile.NamedTemporaryFile('w',encoding='utf-8',
                                             dir=out.parent,
                                             prefix='.'+out.name+'.',
                                             suffix='.tmp',delete=False) as stream:
                temp_name = stream.name
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name,out)
        finally:
            if temp_name is not None and os.path.exists(temp_name):
                os.unlink(temp_name)
    except (OSError,ValueError,KeyError,TypeError,AssertionError) as exc:
        print('P15 closeout review: '+str(exc),file=sys.stderr)
        return 1
    print(json.dumps(dict(status=obj['release_status'],mandatory_unclosed=obj['mandatory_unclosed'],
                          output=args.output.name),sort_keys=True))
    return 2 if args.require_qualified and obj['mandatory_unclosed'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
