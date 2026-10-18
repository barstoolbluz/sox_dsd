#!/usr/bin/env python3
"""Independent receipt aggregation for DSD256 mastering -> 384 kHz.

This stdlib-only verifier checks exhaustive canonical coverage, immutable
dependencies and outward certificate summaries. It does NOT rerun interval
arithmetic, reconstruct leaf proof trees, or qualify production arithmetic.
Its deliberately fixed identities make changed proof inputs fail closed.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import sys
import tempfile

CELL = 'dsd256.mastering.pcm384000'
PROFILE = 'master256'
SCHEMA = 'P15/full-frequency-cover-campaign/1'
DESIGN = 'docs/dsd/DSD_DESIGN.md'
PAIR = 'tests/dsd/results/P15_SRC_STAGE_BOUND_OPT_2026-10-17/176400-384000'
DESIGN_SHA = '458537dbe9a2ea1e687b68f998f43a90de10c369b604f809c78cf80c2389b94b'
SNAPSHOT_SHA = '695e24eb9ba49b187ccb061fc057fef8218e3e1311e472b3145b33a80c7b63df'
OPERATOR_SHA = '6fb7c42785350cfdf93824ec60fe1e3baa5ab5c1ece7232a2b7569f3af42b172'
HARNESS_SHA = '1dbaf498e8127facf0bab4a72916a1bba5f7d3785f8d1babb028e071a68bcd57'
PLAN_SHA = '6f9a3d3721c5ccef8ee919c87087181a5d9deb93dc2375e7dae9d8d4468fcd5c'
CELL_PLAN_SHA = 'ae32a98f83f2ad7c3433b1644928ee60dfdb54aad1fabe9c5598025728917433'
PROVER = {
    'p15_full_band_campaign.py': '17aba94177d11f42b1497e7ce60b546e875f5c1d865204e04ef4503e7fc7cf56',
    'p15_numerical_reference.py': '60ddaa4c26b9399471545c3e5211418bb7c918232d4eb5449c1abea067d33115',
    'p15_src_bound_operator.py': 'ab9a77c81937f4ed5f68ee2d5f592a2ab2bb39a38b5772187103053b557d0c44',
    'p15_src_branch_bound.py': '034771fec42e7b0c47ab25f39530cb2fd9bd304cedd0e4f194fef977d12726b2',
    'p15_src_capture_matrix.py': '7cd12f856d45c0a6f4267ac73e787691ca97ec17144e864c7b8c08fa22f06e74',
    'p15_src_complete_aliases.py': '6637df52a083bfbc99a9429317a8a88d5aa3c76b378d30b1e72c35a16215323c',
    'p15_src_continuum_bounds.py': 'fbc867b42a19f59ab5a85010b29423c1a2fd1e7a7dbe51b892c43d76488d5e5f',
    'p15_src_difference_upper.py': '50ff557922360e74e815e434ebda4f914fbd64e1e01a06ce7afe5e64bd7fd627',
    'p15_src_fixed_interval.py': 'ef71ef4d89adfc24d911b16349dcf9113102f2ee1fef0279435b714fde9cb823',
    'p15_src_full_chain.py': 'bbd5c8e430fa3b93cebbbc0baa362ae2482aabcad1045b96292dd5f2eae8b679',
    'p15_src_halfband_majorant.py': '3d71e72a802440d9ab94cbfac59b1668a016723d179948ce20f11e383e979550',
    'p15_src_interval_recurrence.py': '75387f9c5f425103f64812f80e144fac2e3342ebbbf30e6f42e6ebd6107101c5',
    'p15_src_stagewise_alias_proof.py': '7a2d88d158174ed65e5c067a451b4a96f5c7848cb4e946f15f4ee83f414b0bde',
    'p15_src_stagewise_continuum.py': '5d263e0a8a5424895e305a593110d2c2be9c7250aff118ffbe748d8f5909b250',
    'p15_src_symmetric_interval.py': 'fd72181ca2db3e0b0bfd3464c2de2742090f1636954c3856e5ecbc7881c24368',
}
NORMATIVE_BANDS = {
    'master64': (20000, 40000), 'master128': (30000, 60000),
    'master256': (40000, 80000), 'wide64': (35280, 44100),
    'wide128': (70560, 88200), 'wide256': (141120, 176400),
    'decode.mastering.v2.dsd64': (25000, 40000),
    'decode.mastering.v2.dsd128': (48000, 60000),
    'decode.mastering.v2.dsd256': (66000, 80000),
}
COUNTERS = ('fully_proven_subintervals', 'nodes_examined', 'exact_branch_splits',
            'fir_interval_evaluations', 'cheap_difference_majorants_used',
            'exact_path_enumerations', 'max_alias_path_population',
            'interval_subdivisions')
POPULATION_COUNTERS = ('trie_nodes', 'frontier_insertions',
                       'frontier_expansions', 'subtree_caps_used')


class Invalid(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise Invalid(message)


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                             allow_nan=False).encode()).hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()


def read_file(path):
    require(not path.is_symlink() and path.is_file(), 'missing/unsafe file: ' + str(path))
    return path.read_bytes()


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key: ' + key)
            result[key] = value
        return result
    def nonfinite(value):
        raise Invalid('nonfinite JSON number: ' + value)
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)


def load(path):
    return strict_json(read_file(path))


def pinned(path, expected):
    raw = read_file(path)
    require(sha256(raw).hexdigest() == expected, 'SHA-256 mismatch: ' + str(path))
    return raw


def dependencies(root):
    """Fixed operator binding pins all 35 source inputs; no imports needed."""
    operator = strict_json(pinned(root / PAIR / 'operator-binding.json', OPERATOR_SHA))
    snapshot = strict_json(pinned(root / PAIR / 'stage-snapshot.json', SNAPSHOT_SHA))
    require(operator['schema'] == 'P15/stage-source-binding/1' and
            operator['status'] == 'SOURCE_BOUND_UNCERTIFIED' and
            operator['qualified'] is False, 'operator binding disposition')
    require((operator['input_hz'], operator['output_hz'], operator['U'], operator['V'],
             operator['reduced_U'], operator['reduced_V'], operator['period_multiple']) ==
            (176400, 384000, 320, 147, 320, 147, 1), 'operator clock/phase identity')
    require(operator['snapshot_sha256'] == SNAPSHOT_SHA, 'operator snapshot identity')
    require(snapshot['input_hz'] == 176400 and snapshot['output_hz'] == 384000 and
            snapshot['stage_count'] == 2, 'snapshot topology')
    source = operator['source_sha256']
    require(type(source) is dict and len(source) == 35, 'source dependency population')
    files = dict(source)
    files.update({DESIGN: DESIGN_SHA,
                  PAIR + '/operator-binding.json': OPERATOR_SHA,
                  PAIR + '/stage-snapshot.json': SNAPSHOT_SHA,
                  'tests/dsd/p15_high_rate_experiment.py': HARNESS_SHA})
    files.update({'tests/dsd/' + name: value for name, value in PROVER.items()})
    for name, expected in sorted(files.items()):
        rel = Path(name)
        require(not rel.is_absolute() and '..' not in rel.parts, 'unsafe source dependency')
        pinned(root / rel, expected)
    return {'source': source, 'design': DESIGN_SHA}, files


def reconstruct_plan(root):
    """Independent finite worklist construction from pinned normative inputs."""
    profiles = load(root / 'tests/dsd/reference/p06_coefficients.json')['profiles']
    profiles.update(load(root / 'tests/dsd/reference/p15_r3_coefficients.json')['profiles'])
    require(set(profiles) == set(NORMATIVE_BANDS), 'native profile population')
    jobs, active = [], []
    for v2, path, count in (
        (False, 'P15_v1_matrix_rebound_2026-10-15', 54),
        (True, 'P15_v2_matrix_2026-10-15', 27),
    ):
        cells = load(root / 'tests/dsd/results' / path / 'scalar/worklist.json')['scalar_cells']
        require(len(cells) == count, 'historical scalar matrix population')
        for cell in cells:
            native, output = cell['native_hz'], cell['pcm_hz']
            name = (f'decode.mastering.v2.dsd{native // 44100}' if v2 else
                    ('master' if cell['profile'] == 'mastering' else 'wide') + str(native // 44100))
            meta = profiles[name]
            intermediate = meta['intermediate_hz']
            require(meta['native_hz'] == native, 'matrix/native profile clock mismatch')
            P, S = NORMATIVE_BANDS[name]
            require((meta['pass_hz'], meta['stop_hz']) == (P, S), 'normative profile band mismatch')
            if intermediate == output:
                continue
            active.append(cell['id'])
            effective = min(Fraction(P), Fraction(475, 1000) * min(intermediate, output))
            for mode, end in (('pass', effective), ('stop', Fraction(output, 2))):
                lo = Fraction(0)
                while lo < end:
                    hi = min(lo + 1000, end)
                    jobs.append(dict(cell_id=cell['id'], profile=name,
                        intermediate_hz=intermediate, output_hz=output, mode=mode,
                        lo=str(lo), hi=str(hi), effective_p=str(effective), source_s=S))
                    lo = hi
    require(len(active) == len(set(active)) == 72 and len(jobs) == 11516,
            'complete canonical matrix population')
    require(digest(jobs) == PLAN_SHA, 'independently reconstructed canonical plan digest')
    selected = [(i, job) for i, job in enumerate(jobs) if job['cell_id'] == CELL]
    require(len(selected) == 232 and selected[0][0] == 5597 and selected[-1][0] == 5828,
            'target canonical index population')
    require(digest([job for _, job in selected]) == CELL_PLAN_SHA, 'target canonical plan digest')
    for mode, end, count in (('pass', 40000, 40), ('stop', 192000, 192)):
        intervals = [j for _, j in selected if j['mode'] == mode]
        require(len(intervals) == count, 'target mode population')
        current = Fraction(0)
        for job in intervals:
            require(Fraction(job['lo']) == current and Fraction(job['hi']) - current == 1000,
                    'gap, overlap, or altered canonical interval width')
            current = Fraction(job['hi'])
        require(current == end, 'incomplete normative endpoint coverage')
    return selected


def log_enclosure(x, terms):
    """Rational enclosure using log(x)=2*atanh((x-1)/(x+1))."""
    require(type(x) is Fraction and x > 0 and type(terms) is int and terms > 0,
            'invalid exact logarithm arguments')
    z = (x - 1) / (x + 1)
    z2, power, total = z*z, z, Fraction(0)
    for k in range(terms):
        total += 2*power / (2*k + 1)
        power *= z2
    # All omitted terms have the sign of z. Replace their denominators by
    # the smallest omitted denominator and sum the geometric series.
    tail = 2*abs(power) / ((2*terms + 1)*(1-z2))
    return (total, total + tail) if z >= 0 else (total - tail, total)


L2 = log_enclosure(Fraction(2), 40)
L125 = log_enclosure(Fraction(5, 4), 40)
LN10 = (3*L2[0] + L125[0], 3*L2[1] + L125[1])


def exact_display(value, name):
    require(type(value) in (int, float) and math.isfinite(value) and value >= 0,
            'invalid nonnegative finite certificate bound: ' + name)
    q = Fraction(value)
    return q, {'binary64_hex': float(value).hex(), 'exact_rational': str(q)}


def check_inequalities(cert, mode):
    checks = {}
    require(all(name in cert for name in ('max_coherent_alias_upper',
        'max_native_stop_source_transfer_upper', 'min_wanted_transfer_lower',
        'max_total_transfer_upper')), 'missing certificate bound field')
    alias_key = ('max_coherent_alias_upper' if mode == 'pass' else
                 'max_native_stop_source_transfer_upper')
    alias, checks[alias_key] = exact_display(cert.get(alias_key), alias_key)
    require(alias < Fraction(1, 100000000), 'display bound does not establish strict -160 dB')
    checks[alias_key]['strictly_below_1e_minus_8'] = True
    if mode == 'pass':
        lower, checks['min_wanted_transfer_lower'] = exact_display(
            cert.get('min_wanted_transfer_lower'), 'min_wanted_transfer_lower')
        upper, checks['max_total_transfer_upper'] = exact_display(
            cert.get('max_total_transfer_upper'), 'max_total_transfer_upper')
        require(Fraction(1, 2) < lower <= upper < 2, 'invalid passband gain range')
        require(log_enclosure(lower, 8)[0] > -LN10[0]/200000,
                'display lower bound does not establish -0.0001 dB')
        require(log_enclosure(upper, 8)[1] < LN10[0]/200000,
                'display upper bound does not establish +0.0001 dB')
        checks['min_wanted_transfer_lower']['strictly_above_10_power_minus_1_over_200000'] = True
        checks['max_total_transfer_upper']['strictly_below_10_power_1_over_200000'] = True
        require(cert.get('max_native_stop_source_transfer_upper') is None, 'pass/stop bound substitution')
    else:
        require(all(cert.get(name) is None for name in ('max_coherent_alias_upper',
            'min_wanted_transfer_lower', 'max_total_transfer_upper')), 'stop/pass bound substitution')
    return checks


def validate_receipt(doc, index, job, binding):
    require(type(doc) is dict and doc.get('schema') == SCHEMA, 'receipt schema')
    require(doc.get('job') == job and doc.get('canonical_work_index') == index and
            type(doc.get('canonical_work_index')) is int, 'canonical work identity')
    require(doc.get('binding') == binding and doc.get('qualified_release') is False,
            'source/design binding or release disposition')
    require(doc.get('prover_code_sha256') == PROVER and
            doc.get('stage_snapshot_sha256') == SNAPSHOT_SHA and
            doc.get('verified_operator_binding_sha256') == OPERATOR_SHA, 'outer proof/operator identity')
    require(doc.get('mathematical_scope') == 'local continuous ideal-coefficient interval', 'mathematical scope')
    identity = doc.get('experiment_identity')
    require(type(identity) is dict, 'missing experiment identity')
    for name, value in dict(job=job, binding=binding, prover_code_sha256=PROVER,
            stage_snapshot_sha256=SNAPSHOT_SHA,
            verified_operator_binding_sha256=OPERATOR_SHA, harness_sha256=HARNESS_SHA).items():
        require(identity.get(name) == value, 'experiment identity mismatch: ' + name)
    resources = identity.get('resources', {})
    require(type(resources.get('max_nodes')) is int and 1 <= resources['max_nodes'] <= 131072 and
            type(resources.get('max_paths')) is int and 9408 <= resources['max_paths'] <= 100000,
            'experiment node/path resource record')
    require(type(resources.get('seconds')) in (int, float) and
            math.isfinite(resources['seconds']) and 0 < resources['seconds'] <= 3600,
            'experiment wall resource record')
    cert = doc.get('certificate')
    require(type(cert) is dict, 'missing local certificate')
    expected_status = 'PASS-LOCAL-BAND' if job['mode'] == 'pass' else 'PASS-LOCAL-STOP-SOURCE'
    require(cert.get('status') == expected_status and cert.get('qualified_release') is False,
            'local receipt is not the required PASS: ' + str(cert.get('status')) + ':' + str(cert.get('reason')))
    expected = dict(profile=PROFILE, input_hz=176400, output_hz=384000,
        native_hz=11289600, band_kind=job['mode'], governing_passband_hz=40000,
        governing_stopband_hz=80000, certified_hz=[job['lo'], job['hi']],
        limits=dict(passband_db='0.0001', coherent_alias_db='-160'))
    for name, value in expected.items():
        require(cert.get(name) == value, 'certificate obligation mismatch: ' + name)
    for name in COUNTERS:
        require(type(cert.get(name)) is int and cert[name] >= 0, 'invalid certificate counter: ' + name)
    leaves, nodes = cert['fully_proven_subintervals'], cert['nodes_examined']
    require(leaves > 0 and nodes == 2*leaves-1 and nodes <= resources['max_nodes'], 'incomplete binary proof tree')
    require(cert['exact_branch_splits'] + cert['interval_subdivisions'] == leaves-1 and
            cert['exact_path_enumerations'] == 1+2*cert['exact_branch_splits'], 'proof-tree accounting')
    require(cert['max_alias_path_population'] == 9408 and
            cert['cheap_difference_majorants_used'] <= cert['fir_interval_evaluations'], 'alias/FIR accounting')
    population = cert.get('alias_population_operations')
    require(type(population) is dict and set(population) == set(POPULATION_COUNTERS) and
            all(type(x) is int and x >= 0 for x in population.values()), 'subtree operation accounting')
    measurement = doc.get('measurement', {})
    require(measurement.get('environment', {}).get('mpmath') == '1.3.0',
            'unreviewed endpoint float conversion library version')
    for name in ('elapsed_s', 'cpu_s', 'process_elapsed_s', 'peak_rss_kib'):
        value = measurement.get(name)
        require(type(value) in (int, float) and math.isfinite(value) and value >= 0,
                'invalid measurement: ' + name)
    require(type(identity.get('profiling_enabled')) is bool and
            identity['profiling_enabled'] == measurement.get('profiling_enabled'), 'profiling record mismatch')
    return check_inequalities(cert, job['mode'])


def verify_receipts(directory, selected, binding):
    expected = {digest(job): (index, job) for index, job in selected}
    rows, invalid, seen = [], [], set()
    for path in sorted(directory.glob('*.json')):
        try:
            raw = read_file(path)
            doc = strict_json(raw)
            is_target = type(doc) is dict and type(doc.get('job')) is dict and doc['job'].get('cell_id') == CELL
            if not is_target and path.stem not in expected:
                continue
            require(path.suffix == '.json' and path.stem in expected, 'unexpected target work filename')
            require(path.stem not in seen, 'duplicate target canonical work')
            seen.add(path.stem)
            index, job = expected[path.stem]
            checks = validate_receipt(doc, index, job, binding)
            rows.append(dict(canonical_work_index=index, work_sha256=path.stem,
                receipt_filename=path.name, receipt_sha256=sha256(raw).hexdigest(), job=job,
                status=doc['certificate']['status'], checked_inequalities=checks,
                proof_counters={name: doc['certificate'][name] for name in COUNTERS},
                alias_population_operations=doc['certificate']['alias_population_operations'],
                measurement={key: doc['measurement'][key] for key in
                    ('elapsed_s', 'cpu_s', 'process_elapsed_s', 'peak_rss_kib')}))
        except (Invalid, ValueError, TypeError, KeyError) as exc:
            invalid.append(dict(receipt_filename=path.name, reason=str(exc)))
    rows.sort(key=lambda row: row['canonical_work_index'])
    missing = [dict(canonical_work_index=i, work_sha256=key, job=job)
               for key, (i, job) in expected.items() if key not in seen]
    complete = len(rows) == 232 and not invalid and not missing
    return dict(status='COMPLETE_CANONICAL_RECEIPT_COVERAGE_VERIFIED' if complete else 'OPEN',
        expected_intervals=232, verified_intervals=len(rows),
        verified_by_mode={mode: sum(row['job']['mode'] == mode for row in rows) for mode in ('pass', 'stop')},
        missing_intervals=missing, invalid_receipts=invalid, receipts=rows)


def publish(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    require(not path.is_symlink(), 'symlink publication target')
    fd, temporary = tempfile.mkstemp(prefix='.cell-verifier-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            require(read_file(path) == data, 'immutable publication conflict: ' + str(path))
    finally:
        os.unlink(temporary)


def main(argv=None):
    require((sys.float_info.radix, sys.float_info.mant_dig, sys.float_info.max_exp,
             sys.float_info.min_exp) == (2, 53, 1024, -1021), 'binary64 Python float required')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--receipts', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    root, receipts = args.root.resolve(strict=True), args.receipts.resolve(strict=True)
    binding, files = dependencies(root)
    selected = reconstruct_plan(root)
    report = verify_receipts(receipts, selected, binding)
    report.update(schema='P15/independent-complete-cell-receipt-verification/1',
        cell_id=CELL, qualified_release=False, p15_release='BLOCKED',
        numerical_proof_replayed=False, internal_leaf_proof_transcripts_available=False,
        canonical_plan_sha256=PLAN_SHA, cell_plan_sha256=CELL_PLAN_SHA,
        verifier_sha256=sha256(read_file(Path(__file__))).hexdigest(),
        source_design_binding=binding, dependency_sha256=files,
        exact_threshold_construction=dict(ln10_enclosure=[str(q) for q in LN10],
            pass_gain_exponent='1/200000', alias_upper_strictly_below='1/100000000',
            method='exact rational atanh series with signed geometric remainder'),
        coverage_obligations=dict(pass_output_hz=['0', '40000'],
            native_stop_output_coordinate_hz=['0', '192000'], native_source_abs_hz_at_least='80000',
            canonical_interval_width_hz='1000', endpoints='all intervals closed; adjoining endpoints included'),
        verification_scope=(
            'Independent canonical aggregation, exact binary64 displayed-inequality checks, '
            'proof-tree count consistency and SHA-256 source/operator/prover/harness verification. '
            'Per-leaf arithmetic and exact alias-transition endpoint proofs are inherited from '
            'the pinned prover, not recomputed here. The finite FIR continuity argument covers '
            'one-sided alias relabeling; native-stop membership conservatively includes touching '
            'source harmonics for the whole subinterval.'),
        numerical_assumptions=(
            'Pinned prover uses directed interval arithmetic and mpmath 1.3.0. Its normal positive '
            'endpoint conversion truncates to binary64 and applies nextafter outward before JSON '
            'serialization. Python JSON round trips binary64; this verifier converts those values '
            'to exact rationals. Receipt-recorded numerical-library versions are checked; package '
            'binary identities and arbitrary-input FFT4G runtime rounding are not proved.'),
        independent_remaining_obligations=[
            'FFT4G arbitrary-input production execution-roundoff proof',
            'Remaining P15 cells and all independent release obligations',
            'Physical comparator adjudication and incomplete metrology replay payloads'])
    for name, expected in files.items():
        pinned(root / name, expected)
    if args.output:
        output = args.output.absolute()
        require(not output.is_symlink(), 'symlink evidence directory')
        for name, expected in sorted(files.items()):
            publish(output / 'source_snapshot' / name, pinned(root / name, expected))
        publish(output / 'verifier_snapshot.py', read_file(Path(__file__)))
        publish(output / 'canonical_jobs.json', encoded([dict(index=i, job=j, work_sha256=digest(j)) for i, j in selected]))
        publish(output / 'receipt_sha256.txt', ''.join(
            row['receipt_sha256'] + '  ' + row['receipt_filename'] + '\n' for row in report['receipts']).encode())
        publish(output / 'verification.json', encoded(report))
        manifest = ''.join(sha256(read_file(path)).hexdigest() + '  ' + str(path.relative_to(output)) + '\n'
                           for path in sorted(output.rglob('*')) if path.is_file() and path.name != 'SHA256SUMS')
        publish(output / 'SHA256SUMS', manifest.encode())
    print(json.dumps({key: report[key] for key in ('status', 'cell_id', 'expected_intervals',
          'verified_intervals', 'verified_by_mode', 'numerical_proof_replayed', 'p15_release')}, sort_keys=True))
    if report['invalid_receipts']:
        print(json.dumps({'invalid_receipts': report['invalid_receipts']}, sort_keys=True), file=sys.stderr)
    return 0 if report['status'] == 'COMPLETE_CANONICAL_RECEIPT_COVERAGE_VERIFIED' else 2


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (Invalid, ValueError, TypeError, KeyError, OSError) as exc:
        print(json.dumps(dict(status='OPEN', qualified_release=False, error=str(exc)), sort_keys=True))
        raise SystemExit(2)
