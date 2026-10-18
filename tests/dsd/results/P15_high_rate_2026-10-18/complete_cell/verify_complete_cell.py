#!/usr/bin/env python3
"""Independent receipt aggregation for selected complete DSD256 cells.

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
PROVER_V2 = dict(PROVER, **{
    'p15_src_branch_bound.py': '7a298cf8356b732de8a16f10dd824677694478f20c436438c971ae8e477dd583',
    'p15_src_halfband_majorant.py': 'e3fda2f3e7a53bc1cd574949909ec574d37ebd4bd1dbb5f969251b2a91b1d580',
    'p15_src_stagewise_continuum.py': 'def3efee896a27008f5dbef2e8bfb8a6fab98d8a167d6ad9cd9e9a78ee6ce83d',
})
PROVER_FINAL = dict(PROVER_V2, **{
    'p15_src_continuum_bounds.py': '2656e0fafac58a6d4cffd19002f6ff22d5a851f4e730afd9ab6e70c684f7f1b5',
})
PROVERS = {'high_rate_v1': PROVER, 'high_rate_v2': PROVER_V2, 'high_rate_final': PROVER_FINAL}
EVIDENCE = 'tests/dsd/results/P15_high_rate_2026-10-18'
TARGETS = {
    CELL: (PROFILE, 176400, 384000, 40, 192),
    'dsd256.wideband.pcm384000': ('wide256', 352800, 384000, 142, 192),
    'dsd256.mastering_v2.pcm384000': ('decode.mastering.v2.dsd256', 176400, 384000, 66, 192),
    'dsd256.wideband.pcm192000': ('wide256', 352800, 192000, 92, 96),
}
PAIRS = {
    (176400, 384000): dict(snapshot=SNAPSHOT_SHA, binding=OPERATOR_SHA, U=320, V=147,
                          stage_ratios=[(2, 1), (160, 147)]),
    (352800, 384000): dict(
        snapshot='6bf69a5195b7ab12f49b4925864a8e47cd69849649d837614ecf170ebc4342b2',
        binding='b648668bd4f6a2774e9a605c5f0df227795c58074cb0b5750ede66c5bf954333',
        U=160, V=147, stage_ratios=[(2, 1), (80, 147)]),
    (352800, 192000): dict(
        snapshot='f892d8329c13850626b56088dee42119a4df02ac662ea6e7db6ef1c1ec177a45',
        binding='abf5df004795456e5bfeaee8d4a86d90563a56c2997a79d17b44acdf48a9dd57',
        U=80, V=147, stage_ratios=[(160, 147), (1, 2)]),
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


def target_spec(cell):
    require(cell in TARGETS, 'unreviewed cell for aggregation')
    profile, intermediate, output, npass, nstop = TARGETS[cell]
    pair = PAIRS[intermediate, output]
    P, S = NORMATIVE_BANDS[profile]
    effective = min(Fraction(P), Fraction(475, 1000)*min(intermediate, output))
    native_factor = 11289600//intermediate
    paths = native_factor*math.prod(M for _, M in pair['stage_ratios'])
    families = Fraction(11289600)*pair['U']/output
    require(families.denominator == 1 and paths % int(families) == 0,
            'primitive native family and full-path populations')
    return dict(profile=profile, intermediate=intermediate, output=output, P=P, S=S,
        effective=effective, npass=npass, nstop=nstop, paths=paths, families=int(families),
        pair=pair, pair_path=f'tests/dsd/results/P15_SRC_STAGE_BOUND_OPT_2026-10-17/{intermediate}-{output}')


def proof_version(doc):
    code = doc.get('prover_code_sha256')
    matches = [name for name, expected in PROVERS.items() if code == expected]
    require(len(matches) == 1, 'unrecognized or incomplete prover identity')
    return matches[0]


def dependencies(root, cell=CELL):
    """Fixed operator binding pins all 35 source inputs; no imports needed."""
    spec = target_spec(cell)
    pair, path = spec['pair'], spec['pair_path']
    operator = strict_json(pinned(root / path / 'operator-binding.json', pair['binding']))
    snapshot = strict_json(pinned(root / path / 'stage-snapshot.json', pair['snapshot']))
    require(operator['schema'] == 'P15/stage-source-binding/1' and
            operator['status'] == 'SOURCE_BOUND_UNCERTIFIED' and
            operator['qualified'] is False, 'operator binding disposition')
    require((operator['input_hz'], operator['output_hz'], operator['U'], operator['V'],
             operator['reduced_U'], operator['reduced_V'], operator['period_multiple']) ==
            (spec['intermediate'], spec['output'], pair['U'], pair['V'], pair['U'], pair['V'], 1),
            'operator clock/phase identity')
    require(operator['snapshot_sha256'] == pair['snapshot'], 'operator snapshot identity')
    require(snapshot['input_hz'] == spec['intermediate'] and snapshot['output_hz'] == spec['output'] and
            snapshot['stage_count'] == len(pair['stage_ratios']), 'snapshot topology')
    ratios = [(stage['L'], (1 << -stage['M']) if stage['kind'] == 2 and stage['M'] < 0 else stage['M'])
              for stage in snapshot['stages']]
    require(ratios == pair['stage_ratios'], 'captured stage ratio topology')
    source = operator['source_sha256']
    require(type(source) is dict and len(source) == 35, 'source dependency population')
    files = dict(source)
    files.update({DESIGN: DESIGN_SHA,
                  path + '/operator-binding.json': pair['binding'],
                  path + '/stage-snapshot.json': pair['snapshot'],
                  'tests/dsd/p15_high_rate_experiment.py': HARNESS_SHA})
    # Receipt versions may differ from the currently installed proof modules.
    # Verify their immutable flat source snapshots, never silently import the
    # current implementation as a substitute for a receipt's implementation.
    for version, code in PROVERS.items():
        directory = EVIDENCE + '/reference_' + version + '_code'
        files.update({directory + '/' + name: value for name, value in code.items()})
        identity = read_file(root / directory / 'IDENTITY.json')
        require(strict_json(identity).get('prover_code_sha256') == code, 'flat prover snapshot inventory')
        files[directory + '/IDENTITY.json'] = sha256(identity).hexdigest()
    for name, expected in sorted(files.items()):
        rel = Path(name)
        require(not rel.is_absolute() and '..' not in rel.parts, 'unsafe source dependency')
        pinned(root / rel, expected)
    return {'source': source, 'design': DESIGN_SHA}, files


def reconstruct_plan(root, cell=CELL):
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
        for matrix_cell in cells:
            native, output = matrix_cell['native_hz'], matrix_cell['pcm_hz']
            name = (f'decode.mastering.v2.dsd{native // 44100}' if v2 else
                    ('master' if matrix_cell['profile'] == 'mastering' else 'wide') + str(native // 44100))
            meta = profiles[name]
            intermediate = meta['intermediate_hz']
            require(meta['native_hz'] == native, 'matrix/native profile clock mismatch')
            P, S = NORMATIVE_BANDS[name]
            require((meta['pass_hz'], meta['stop_hz']) == (P, S), 'normative profile band mismatch')
            if intermediate == output:
                continue
            active.append(matrix_cell['id'])
            effective = min(Fraction(P), Fraction(475, 1000) * min(intermediate, output))
            for mode, end in (('pass', effective), ('stop', Fraction(output, 2))):
                lo = Fraction(0)
                while lo < end:
                    hi = min(lo + 1000, end)
                    jobs.append(dict(cell_id=matrix_cell['id'], profile=name,
                        intermediate_hz=intermediate, output_hz=output, mode=mode,
                        lo=str(lo), hi=str(hi), effective_p=str(effective), source_s=S))
                    lo = hi
    require(len(active) == len(set(active)) == 72 and len(jobs) == 11516,
            'complete canonical matrix population')
    require(digest(jobs) == PLAN_SHA, 'independently reconstructed canonical plan digest')
    spec = target_spec(cell)
    selected = [(i, job) for i, job in enumerate(jobs) if job['cell_id'] == cell]
    require(len(selected) == spec['npass']+spec['nstop'], 'target canonical index population')
    if cell == CELL:
        require(selected[0][0] == 5597 and selected[-1][0] == 5828 and
                digest([job for _, job in selected]) == CELL_PLAN_SHA, 'original target canonical plan digest')
    for mode, end, count in (('pass', spec['effective'], spec['npass']),
                             ('stop', Fraction(spec['output'], 2), spec['nstop'])):
        intervals = [j for _, j in selected if j['mode'] == mode]
        require(len(intervals) == count, 'target mode population')
        current = Fraction(0)
        for job in intervals:
            require(Fraction(job['lo']) == current and Fraction(job['hi']) == min(current+1000, end),
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


def positive_exp_enclosure(x, terms=12):
    """Positive rational Taylor series with a geometric bound on its tail."""
    require(type(x) is Fraction and 0 <= x < 1 and type(terms) is int and terms > 0,
            'invalid exact exponential arguments')
    total = term = Fraction(1)
    for k in range(1, terms):
        term *= x/k
        total += term
    first_omitted = term*x/terms
    # Subsequent term ratios are at most x/(terms+1).
    return total, total + first_omitted/(1-x/(terms+1))


GAIN_PLUS = (positive_exp_enclosure(LN10[0]/200000)[0],
             positive_exp_enclosure(LN10[1]/200000)[1])
GAIN_MINUS = (1/GAIN_PLUS[1], 1/GAIN_PLUS[0])


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
        require(lower > GAIN_MINUS[1],
                'display lower bound does not establish -0.0001 dB')
        require(upper < GAIN_PLUS[0],
                'display upper bound does not establish +0.0001 dB')
        checks['min_wanted_transfer_lower']['strictly_above_10_power_minus_1_over_200000'] = True
        checks['max_total_transfer_upper']['strictly_below_10_power_1_over_200000'] = True
        require(cert.get('max_native_stop_source_transfer_upper') is None, 'pass/stop bound substitution')
    else:
        require(all(cert.get(name) is None for name in ('max_coherent_alias_upper',
            'min_wanted_transfer_lower', 'max_total_transfer_upper')), 'stop/pass bound substitution')
    return checks


def exact_margins(cert, mode):
    """Exact lower bounds on distance to each applicable amplitude limit."""
    alias_key = ('max_coherent_alias_upper' if mode == 'pass' else
                 'max_native_stop_source_transfer_upper')
    margins = {alias_key: Fraction(1, 100000000)-Fraction(cert[alias_key])}
    if mode == 'pass':
        margins['min_wanted_transfer_lower'] = Fraction(cert['min_wanted_transfer_lower'])-GAIN_MINUS[1]
        margins['max_total_transfer_upper'] = GAIN_PLUS[0]-Fraction(cert['max_total_transfer_upper'])
    return margins


def validate_receipt(doc, index, job, binding, cell=CELL, *, allow_open=False):
    spec = target_spec(cell)
    pair = spec['pair']
    require(type(doc) is dict and doc.get('schema') == SCHEMA, 'receipt schema')
    require(doc.get('job') == job and doc.get('canonical_work_index') == index and
            type(doc.get('canonical_work_index')) is int, 'canonical work identity')
    require(doc.get('binding') == binding and doc.get('qualified_release') is False,
            'source/design binding or release disposition')
    version = proof_version(doc)
    code = PROVERS[version]
    require(doc.get('stage_snapshot_sha256') == pair['snapshot'] and
            doc.get('verified_operator_binding_sha256') == pair['binding'], 'outer proof/operator identity')
    require(doc.get('mathematical_scope') == 'local continuous ideal-coefficient interval', 'mathematical scope')
    identity = doc.get('experiment_identity')
    require(type(identity) is dict, 'missing experiment identity')
    for name, value in dict(job=job, binding=binding, prover_code_sha256=code,
            stage_snapshot_sha256=pair['snapshot'],
            verified_operator_binding_sha256=pair['binding'], harness_sha256=HARNESS_SHA).items():
        require(identity.get(name) == value, 'experiment identity mismatch: ' + name)
    resources = identity.get('resources', {})
    require(type(resources.get('max_nodes')) is int and 1 <= resources['max_nodes'] <= 131072 and
            type(resources.get('max_paths')) is int and spec['paths'] <= resources['max_paths'] <= 100000,
            'experiment node/path resource record')
    require(type(resources.get('seconds')) in (int, float) and
            math.isfinite(resources['seconds']) and 0 < resources['seconds'] <= 3600,
            'experiment wall resource record')
    cert = doc.get('certificate')
    require(type(cert) is dict, 'missing local certificate')
    require(cert.get('qualified_release') is False, 'inner release disposition')
    measurement = doc.get('measurement', {})
    require(measurement.get('environment', {}).get('mpmath') == '1.3.0',
            'unreviewed endpoint float conversion library version')
    for name in ('elapsed_s', 'cpu_s', 'process_elapsed_s', 'peak_rss_kib'):
        value = measurement.get(name)
        require(type(value) in (int, float) and math.isfinite(value) and value >= 0,
                'invalid measurement: ' + name)
    require(type(identity.get('profiling_enabled')) is bool and
            identity['profiling_enabled'] == measurement.get('profiling_enabled'), 'profiling record mismatch')
    if allow_open and cert.get('status') == 'OPEN':
        require(type(cert.get('reason')) is str and bool(cert['reason']), 'missing OPEN reason')
        for name, expected in dict(certified_hz=[job['lo'], job['hi']], band_kind=job['mode'],
                input_hz=spec['intermediate'], output_hz=spec['output']).items():
            require(name not in cert or cert[name] == expected, 'incompatible OPEN interval metadata')
        return None
    expected_status = 'PASS-LOCAL-BAND' if job['mode'] == 'pass' else 'PASS-LOCAL-STOP-SOURCE'
    require(cert.get('status') == expected_status and cert.get('qualified_release') is False,
            'local receipt is not the required PASS: ' + str(cert.get('status')) + ':' + str(cert.get('reason')))
    expected = dict(profile=spec['profile'], input_hz=spec['intermediate'], output_hz=spec['output'],
        native_hz=11289600, band_kind=job['mode'], governing_passband_hz=spec['P'],
        governing_stopband_hz=spec['S'], certified_hz=[job['lo'], job['hi']],
        limits=dict(passband_db='0.0001', coherent_alias_db='-160'))
    for name, value in expected.items():
        require(cert.get(name) == value, 'certificate obligation mismatch: ' + name)
    for name in COUNTERS:
        require(type(cert.get(name)) is int and cert[name] >= 0, 'invalid certificate counter: ' + name)
    leaves, nodes = cert['fully_proven_subintervals'], cert['nodes_examined']
    require(leaves > 0 and nodes == 2*leaves-1 and nodes <= resources['max_nodes'], 'incomplete binary proof tree')
    require(cert['exact_branch_splits'] + cert['interval_subdivisions'] == leaves-1 and
            cert['exact_path_enumerations'] == 1+2*cert['exact_branch_splits'], 'proof-tree accounting')
    require(cert['max_alias_path_population'] == spec['paths'] and
            cert['cheap_difference_majorants_used'] <= cert['fir_interval_evaluations'], 'alias/FIR accounting')
    population = cert.get('alias_population_operations')
    population_keys = set(POPULATION_COUNTERS)
    if version != 'high_rate_v1':
        population_keys.add('terminal_saturation_returns')
    require(type(population) is dict and set(population) == population_keys and
            all(type(x) is int and x >= 0 for x in population.values()), 'subtree operation accounting')
    return check_inequalities(cert, job['mode'])


def verify_receipts(directories, selected, binding, cell=CELL):
    if isinstance(directories, Path):
        directories = [directories]
    expected = {digest(job): (index, job) for index, job in selected}
    chosen, attempts, invalid = {}, [], []
    for source_index, directory in enumerate(directories):
        for path in sorted(directory.glob('*.json')):
            try:
                raw = read_file(path)
                doc = strict_json(raw)
                is_target = type(doc) is dict and type(doc.get('job')) is dict and doc['job'].get('cell_id') == cell
                if not is_target and path.stem not in expected:
                    continue
                require(path.suffix == '.json' and path.stem in expected, 'unexpected target work filename')
                index, job = expected[path.stem]
                checks = validate_receipt(doc, index, job, binding, cell, allow_open=True)
                row = dict(canonical_work_index=index, work_sha256=path.stem,
                    receipt_source_index=source_index, receipt_filename=path.name,
                    receipt_sha256=sha256(raw).hexdigest(), job=job, prover_version=proof_version(doc),
                    status=doc['certificate']['status'], checked_inequalities=checks,
                    measurement={key: doc['measurement'][key] for key in
                        ('elapsed_s', 'cpu_s', 'process_elapsed_s', 'peak_rss_kib')})
                if checks is None:
                    row['reason'] = doc['certificate']['reason']
                else:
                    row['proof_counters'] = {name: doc['certificate'][name] for name in COUNTERS}
                    row['alias_population_operations'] = doc['certificate']['alias_population_operations']
                    # Input directory order is an explicit deterministic preference.
                    # A later PASS may fill an earlier OPEN, but all attempts remain.
                    chosen.setdefault(path.stem, row)
                attempts.append(row)
            except (Invalid, ValueError, TypeError, KeyError) as exc:
                invalid.append(dict(receipt_source_index=source_index, receipt_filename=path.name, reason=str(exc)))
    rows = list(chosen.values())
    rows.sort(key=lambda row: row['canonical_work_index'])
    missing = [dict(canonical_work_index=i, work_sha256=key, job=job)
               for key, (i, job) in expected.items() if key not in chosen]
    complete = len(rows) == len(selected) and not invalid and not missing
    return dict(status='COMPLETE_CANONICAL_RECEIPT_COVERAGE_VERIFIED' if complete else 'OPEN',
        expected_intervals=len(selected), verified_intervals=len(rows),
        verified_by_mode={mode: sum(row['job']['mode'] == mode for row in rows) for mode in ('pass', 'stop')},
        verified_by_prover={version: sum(row['prover_version'] == version for row in rows) for version in PROVERS},
        selection='First independently validated PASS in supplied directory order; all attempts retained',
        open_attempts=sum(row['status'] == 'OPEN' for row in attempts),
        missing_intervals=missing, invalid_receipts=invalid, receipts=rows, all_attempts=attempts)


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
    parser.add_argument('--cell', choices=sorted(TARGETS), default=CELL)
    parser.add_argument('--receipts', type=Path, action='append', required=True,
                        help='Repeat to form an ordered union; prior receipts are never overwritten')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    root = args.root.resolve(strict=True)
    receipts = [path.resolve(strict=True) for path in args.receipts]
    require(len(receipts) == len(set(receipts)) and all(path.is_dir() and path.is_relative_to(root) for path in receipts),
            'distinct receipt directories within the source bundle required')
    binding, files = dependencies(root, args.cell)
    selected = reconstruct_plan(root, args.cell)
    spec = target_spec(args.cell)
    report = verify_receipts(receipts, selected, binding, args.cell)
    for row in report['all_attempts']:
        row['receipt_repository_path'] = str((receipts[row['receipt_source_index']] / row['receipt_filename']).relative_to(root))
    report.update(schema='P15/independent-complete-cell-receipt-verification/1',
        cell_id=args.cell, qualified_release=False, p15_release='BLOCKED',
        numerical_proof_replayed=False, internal_leaf_proof_transcripts_available=False,
        canonical_plan_sha256=PLAN_SHA, cell_plan_sha256=digest([job for _, job in selected]),
        receipt_directories=[str(path.relative_to(root)) for path in receipts],
        verifier_sha256=sha256(read_file(Path(__file__))).hexdigest(),
        source_design_binding=binding, dependency_sha256=files,
        recognized_prover_code_sha256=PROVERS, harness_sha256=HARNESS_SHA,
        selected_proof_counters={name: sum(row['proof_counters'][name] for row in report['receipts'])
                                 for name in COUNTERS if name != 'max_alias_path_population'},
        selected_alias_population_operations={name: sum(row['alias_population_operations'].get(name, 0)
            for row in report['receipts']) for name in (*POPULATION_COUNTERS, 'terminal_saturation_returns')},
        source_population=dict(full_inverse_paths=spec['paths'], primitive_native_families=spec['families'],
            path_to_family_population_ratio=str(Fraction(spec['paths'], spec['families'])),
            native_nyquist_hz=5644800),
        exact_threshold_construction=dict(ln10_enclosure=[str(q) for q in LN10],
            gain_plus_enclosure=[str(q) for q in GAIN_PLUS], gain_minus_enclosure=[str(q) for q in GAIN_MINUS],
            pass_gain_exponent='1/200000', alias_upper_strictly_below='1/100000000',
            method='exact rational atanh and exponential series with bounded geometric remainders'),
        normative_readjudication=(
            'All recorded outward certificate summaries are independently rechecked against exact '
            'normative scalar limits. This does not rely on the inherited db_band decision thresholds, '
            'whose binary64 conversion widened the acceptance envelope slightly.'),
        coverage_obligations=dict(pass_output_hz=['0', str(spec['effective'])],
            native_stop_output_coordinate_hz=['0', str(Fraction(spec['output'], 2))],
            native_source_abs_hz_at_least=str(spec['S']), declared_profile_passband_hz=str(spec['P']),
            canonical_interval_maximum_width_hz='1000', endpoints='all intervals closed; adjoining endpoints included'),
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
            row['receipt_sha256'] + '  ' + row['receipt_repository_path'] + '\n' for row in report['receipts']).encode())
        publish(output / 'all_attempt_sha256.txt', ''.join(
            row['receipt_sha256'] + '  ' + row['receipt_repository_path'] + '\n' for row in report['all_attempts']).encode())
        publish(output / 'verification.json', encoded(report))
        manifest = ''.join(sha256(read_file(path)).hexdigest() + '  ' + str(path.relative_to(output)) + '\n'
                           for path in sorted(output.rglob('*')) if path.is_file() and path.name != 'SHA256SUMS')
        publish(output / 'SHA256SUMS', manifest.encode())
    print(json.dumps({key: report[key] for key in ('status', 'cell_id', 'expected_intervals',
          'verified_intervals', 'verified_by_mode', 'verified_by_prover', 'open_attempts',
          'numerical_proof_replayed', 'p15_release')}, sort_keys=True))
    if report['invalid_receipts']:
        print(json.dumps({'invalid_receipts': report['invalid_receipts']}, sort_keys=True), file=sys.stderr)
    return 0 if report['status'] == 'COMPLETE_CANONICAL_RECEIPT_COVERAGE_VERIFIED' else 2


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (Invalid, ValueError, TypeError, KeyError, OSError) as exc:
        print(json.dumps(dict(status='OPEN', qualified_release=False, error=str(exc)), sort_keys=True))
        raise SystemExit(2)
