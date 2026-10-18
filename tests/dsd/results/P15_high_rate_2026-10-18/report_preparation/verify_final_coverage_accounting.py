#!/usr/bin/env python3
"""Independent final-report set, identity, interval-cover, and boundary audit.

This reads raw receipts and uses standard-library set/rational arithmetic. It
does not import either reporting implementation and does not replay numerical
proofs. The canonical planner remains the repository's authoritative worklist.
"""
from collections import Counter, defaultdict
from fractions import Fraction
from hashlib import sha256
import argparse
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / 'tests/dsd'))
from p15_full_band_campaign import canonical_plan, SNAPSHOTS

BASE = ROOT / 'tests/dsd/results/P15_high_rate_2026-10-18'


def load(path):
    return json.loads(path.read_text())


def hashed(path):
    return sha256(path.read_bytes()).hexdigest()


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def manifest(directory):
    for line in (directory / 'SHA256SUMS').read_text().splitlines():
        expected, name = line.split('  ', 1)
        assert Path(name).name == name
        assert hashed(directory / name) == expected, name


def lattice(residue, period, upper):
    residue, period, upper = map(Fraction, (residue, period, upper))
    return {residue + k * period for k in range(
        math.ceil(-residue / period), math.floor((upper - residue) / period) + 1)}


def main(output):
    config_path = BASE / 'execution/FINAL_AGGREGATION_CONFIG_02.json'
    config = load(config_path)
    census_dir, report_dir = BASE / 'census_final_01', BASE / 'coverage_final_01'
    manifest(census_dir)
    manifest(report_dir)
    summary = load(report_dir / 'SUMMARY.json')
    reported_cells = load(report_dir / 'CELL_COVERAGE.json')
    complete = load(report_dir / 'COMPLETE_CELL_WITNESSES.json')
    boundaries = load(report_dir / 'BOUNDARY_COVERAGE.json')
    rows = [json.loads(line) for line in (census_dir / 'intervals.jsonl').read_text().splitlines()]
    jobs = canonical_plan()
    assert len(jobs) == len(rows) == 11516
    work = {digest(job): job for job in jobs}
    assert len(work) == len(jobs)
    source = summary['source_binding']
    for name, expected in source['source'].items():
        assert hashed(ROOT / name) == expected, name
    assert hashed(ROOT / 'docs/dsd/DSD_DESIGN.md') == source['design']
    admission_path = BASE / 'complete_cell/normative_readjudication_02/verification.json'
    admissions = {(r['receipt_path'], r['receipt_sha256']): r for r in load(admission_path)['receipts']}
    admitted = set()

    def admit(path, identity):
        key = (str(path.relative_to(ROOT)), hashed(path))
        item = admissions[key]
        assert item['canonical_work_sha256'] == identity
        assert item['normative_envelope_status'] == 'EXACT_NORMATIVE_ENVELOPE_VERIFIED'
        assert item['source_binding_status'] == 'CURRENT_SOURCE_AND_DESIGN_PINS_MATCH'
        admitted.add(key)

    original, prior, candidate, current = set(), set(), set(), set()
    for index, (job, row) in enumerate(zip(jobs, rows)):
        identity = digest(job)
        assert row['canonical_index'] == index and row['job'] == job and row['work_sha256'] == identity
        old = row['original']
        path = ROOT / old['path']
        assert hashed(path) == old['sha256']
        doc = load(path)
        assert doc['job'] == job and doc['binding'] == source
        assert doc['certificate']['status'] == old['status']
        if old['status'].startswith('PASS'):
            original.add(identity)
            prior.add(identity)
            admit(path, identity)
        for label, observations in row['observations'].items():
            if label.startswith('historical_') or label == 'third_pass_final_local':
                for observation in observations:
                    if observation['status'].startswith('PASS'):
                        path = ROOT / observation['path']
                        assert hashed(path) == observation['sha256']
                        prior.add(identity)
                        admit(path, identity)

    all_current, candidate_measured, current_receipts = set(), set(), {}
    statuses, label_statistics = Counter(), {}
    pair_hashes = {}
    for item in config['measurements']:
        code_dir = ROOT / item['proof_snapshot']
        code = load(code_dir / 'IDENTITY.json')['prover_code_sha256']
        for name, expected in code.items():
            assert hashed(code_dir / name) == expected
        indices, counts = set(), Counter()
        for path in sorted((ROOT / item['directory']).glob('*.json')):
            doc = load(path)
            index = doc['canonical_work_index']
            job = jobs[index]
            identity = digest(job)
            assert index not in indices
            indices.add(index)
            assert path.name == identity + '.json' and doc['job'] == job
            assert doc['binding'] == source and doc['prover_code_sha256'] == code
            for key in ('job', 'binding', 'prover_code_sha256', 'stage_snapshot_sha256', 'verified_operator_binding_sha256'):
                assert doc['experiment_identity'][key] == doc[key]
            for key, value in item['resources'].items():
                assert doc['experiment_identity']['resources'][key] == value
            assert doc['experiment_identity']['profiling_enabled'] is False
            pair = (job['intermediate_hz'], job['output_hz'])
            if pair not in pair_hashes:
                directory = SNAPSHOTS / f'{pair[0]}-{pair[1]}'
                pair_hashes[pair] = (hashed(directory / 'stage-snapshot.json'), hashed(directory / 'operator-binding.json'))
            assert (doc['stage_snapshot_sha256'], doc['verified_operator_binding_sha256']) == pair_hashes[pair]
            status = doc['certificate']['status']
            assert status in ('OPEN', 'PASS-LOCAL-BAND', 'PASS-LOCAL-STOP-SOURCE')
            counts[status] += 1
            statuses[status] += 1
            all_current.add(identity)
            if item['role'] == 'candidate':
                candidate_measured.add(identity)
            if status.startswith('PASS'):
                assert status == ('PASS-LOCAL-BAND' if job['mode'] == 'pass' else 'PASS-LOCAL-STOP-SOURCE')
                assert doc['certificate']['limits'] == {'passband_db': '0.0001', 'coherent_alias_db': '-160'}
                current.add(identity)
                if item['role'] == 'candidate':
                    candidate.add(identity)
                admit(path, identity)
            current_receipts[(item['label'], str(path.relative_to(ROOT)))] = (identity, status, hashed(path))
        assert indices == set(load(ROOT / item['plan'])['job_indices'])
        assert len(indices) == item['expected_receipts']
        label_statistics[item['label']] = dict(counts)
        assert dict(counts) == summary['label_statistics'][item['label']]['statuses']

    counts = dict(original_pass=len(original), prior_pass_included_here=len(prior),
        candidate_unique_pass=len(candidate), current_unique_pass=len(current),
        candidate_pass_new_vs_original=len(candidate - original),
        current_pass_new_vs_original=len(current - original),
        current_pass_new_vs_included_prior=len(current - prior),
        original_plus_current_pass=len(original | current),
        cumulative_explicit_evidence_pass=len(prior | current),
        cumulative_remaining=len(work.keys() - prior - current))
    assert all(summary[key] == value for key, value in counts.items())
    assert sum(statuses.values()) == config['expected_current_receipt_instances'] == 1450
    assert len(all_current) == config['planned_unique_canonical_jobs'] == 1148
    assert len(admitted) == summary['strict_readjudication']['contributing_pass_receipts']
    groups = defaultdict(set)
    for identity, job in work.items():
        groups[job['cell_id']].add(identity)
    found_complete = {cell for cell, identities in groups.items() if identities <= candidate}
    assert found_complete == set(complete) == set(summary['complete_candidate_cells']) == {
        'dsd256.mastering.pcm384000', 'dsd256.mastering_v2.pcm384000',
        'dsd256.wideband.pcm384000', 'dsd256.wideband.pcm192000'}
    for row in reported_cells:
        identities = groups[row['cell_id']]
        assert row['canonical_intervals'] == len(identities)
        assert row['candidate_pass'] == len(identities & candidate)
        assert row['candidate_unmeasured'] == len(identities - candidate_measured)
        assert row['candidate_open_without_any_pass'] == len((identities & candidate_measured) - candidate)
        assert row['original_pass'] == len(identities & original)
        assert row['newly_certified_candidate_vs_original'] == len((identities & candidate) - original)
        assert row['cumulative_explicit_evidence_pass'] == len(identities & (prior | current))
    complete_counts = {}
    for cell, value in complete.items():
        assert value['source_binding'] == source and value['qualified_release'] is False
        complete_counts[cell] = {}
        for mode, band in value['bands'].items():
            expected = sorted((work[w] for w in groups[cell] if work[w]['mode'] == mode), key=lambda j: Fraction(j['lo']))
            assert band['canonical_intervals'] == len(expected) == len(band['intervals'])
            cursor = Fraction(0)
            for job, interval in zip(expected, band['intervals']):
                identity = digest(job)
                assert interval['work_sha256'] == identity
                assert (interval['lo'], interval['hi']) == (job['lo'], job['hi'])
                assert Fraction(interval['lo']) == cursor
                cursor = Fraction(interval['hi'])
                ref = interval['witness']
                assert current_receipts[(ref['label'], ref['path'])] == (identity,
                    'PASS-LOCAL-BAND' if mode == 'pass' else 'PASS-LOCAL-STOP-SOURCE', ref['sha256'])
            upper = Fraction(expected[0]['effective_p']) if mode == 'pass' else Fraction(expected[0]['output_hz'], 2)
            assert cursor == Fraction(band['upper_hz']) == upper
            assert Fraction(band['lower_hz']) == 0
            complete_counts[cell][mode] = len(expected)

    metadata = {m['id']: m for m in load(census_dir / 'cells.json')}
    checked_events, boundary_summary = 0, []
    for reported in boundaries['candidate_pass']['cells']:
        cell = reported['cell_id']
        meta = metadata[cell]
        spacing = meta['output_hz']
        grids = []
        population = 1
        for stage in reversed(meta['topology']['stages']):
            grids.append((Fraction(stage['L'] * stage['input_hz'], 2) % spacing, spacing))
            spacing = math.gcd(spacing, stage['input_hz'])
            grids.append((Fraction(stage['input_hz'], 2) % spacing, spacing))
            population *= stage['M']
        assert population == reported['complete_path_count']
        assert meta['native_hz'] // spacing == reported['primitive_source_families']
        brief = {'cell_id': cell, 'bands': {}}
        for mode, band in reported['bands'].items():
            upper = Fraction(meta['effective_P_hz']) if mode == 'pass' else Fraction(meta['output_hz'], 2)
            intervals = [(Fraction(work[w]['lo']), Fraction(work[w]['hi'])) for w in groups[cell] & candidate if work[w]['mode'] == mode]
            assert band['canonical_intervals'] == len(intervals)
            assert band['dc_and_arbitrarily_near_zero'] == any(lo == 0 < hi for lo, hi in intervals)
            assert band['upper_normative_edge_and_left_limit'] == any(lo < upper == hi for lo, hi in intervals)
            events = {'routing': set().union(*(lattice(r, d, upper) for r, d in grids)),
                'source_nyquist_alias_relabeling': lattice(-Fraction(meta['native_hz'], 2) % spacing, spacing, upper)}
            if mode == 'stop':
                events['native_stop_membership'] = lattice(Fraction(meta['declared_S_hz']) % spacing, spacing, upper) | lattice(-Fraction(meta['declared_S_hz']) % spacing, spacing, upper)
            brief['bands'][mode] = {}
            for kind, points in events.items():
                assert points == {Fraction(event['hz']) for event in band[kind]['events']}
                all_sides = both = 0
                for event in band[kind]['events']:
                    point = Fraction(event['hz'])
                    at = any(lo <= point <= hi for lo, hi in intervals)
                    left = any(lo < point <= hi for lo, hi in intervals)
                    right = any(lo <= point < hi for lo, hi in intervals)
                    valid = at and (point == 0 or left) and (point == upper or right)
                    assert (event['point'], event['left_neighborhood'], event['right_neighborhood'], event['all_applicable_sides']) == (at, left, right, valid)
                    all_sides += valid
                    both += left and right
                    checked_events += 1
                assert (band[kind]['total'], band[kind]['with_all_applicable_sides'], band[kind]['with_both_sides']) == (len(points), all_sides, both)
                if cell in found_complete:
                    assert all_sides == len(points)
                brief['bands'][mode][kind] = {'total': len(points), 'with_all_applicable_sides': all_sides}
        boundary_summary.append(brief)
    result = dict(status='VERIFIED', numerical_proof_replayed=False,
        scope='Independent raw-receipt set accounting, source/operator/proof byte identities, complete rational canonical covers, and exact boundary-neighborhood audit; numerical inequality replay remains separate.',
        code_sha256=hashed(Path(__file__)), configuration_sha256=hashed(config_path),
        census_manifest_sha256=hashed(census_dir / 'SHA256SUMS'), report_manifest_sha256=hashed(report_dir / 'SHA256SUMS'),
        readjudication_sha256=hashed(admission_path), counts=counts,
        current_receipt_instances=sum(statuses.values()), current_receipt_statuses=dict(statuses),
        contributing_pass_receipts=len(admitted), candidate_open_without_pass=len(candidate_measured-candidate),
        candidate_unmeasured=len(work.keys()-candidate_measured),
        verified_source_files=len(source['source']), verified_operator_pairs=len(pair_hashes),
        complete_cell_counts=complete_counts, independently_checked_boundary_events=checked_events,
        boundary_summary=boundary_summary, label_statuses=label_statistics)
    with output.open('x') as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write('\n')
    print(json.dumps({key:result[key] for key in ('status','counts','current_receipt_instances','current_receipt_statuses','contributing_pass_receipts','candidate_open_without_pass','candidate_unmeasured','complete_cell_counts','independently_checked_boundary_events')}, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    main(parser.parse_args().output)
