#!/usr/bin/env python3
"""Reproducible, non-qualifying census of the canonical P15 worklist.

The historical 60-second campaign is immutable and is never relabeled.  New
measurements are overlaid under explicit labels.  This program does no spectral
arithmetic and cannot issue a spectral PASS.  Its rate-only transition census
is independent of FIR magnitudes, so it remains useful when numerical work
times out before publishing its counters.

For a reverse-stage reachable residue group d*Z modulo Fout, the complete M
branches of an L/M stage generate gcd(d, Fin)*Z modulo Fin.  Branch-window
crossings are f = L*Fin/2 (mod d); input-fold crossings are f = Fin/2
(mod gcd(d, Fin)).  Their union partitions the complete alias schedule.  This
is a topology census, not a replacement for the prover's endpoint checks or a
license to merge coherent paths.  Multiplicity is retained separately from the
number of primitive families.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from fractions import Fraction
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import tempfile

from p15_full_band_campaign import (
    bindings, canonical_plan, check_one, digest, freqstr, receipt_path,
    source_operators,
)
from p15_src_bound_operator import sha_file
from p15_src_capture_matrix import DEFAULT as SNAPSHOTS
from p15_src_complete_aliases import all_active_cells
from p15_src_stagewise_alias_proof import make_native_stages, make_src_stages
from p15_src_stagewise_continuum import PROFILE_BANDS

ROOT = Path(__file__).resolve().parents[2]
HISTORY = ROOT / 'tests/dsd/results/P15_full_band_campaign_complete_2026-10-18'
THIRD_PASS = ROOT / 'tests/dsd/results/P15_prover_third_pass_2026-10-18'
SCHEMA = 'P15/high-rate-census/1'
COUNTERS = (
    'nodes_examined', 'exact_branch_splits', 'exact_path_enumerations',
    'fir_interval_evaluations', 'cheap_difference_majorants_used',
    'fully_proven_subintervals', 'proven_subintervals', 'pending_intervals',
)


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def relative(path):
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def publish(path, data):
    """Exclusive, idempotent publication; a changed census needs a new folder."""
    if path.is_symlink():
        raise ValueError('linked census output refused: ' + str(path))
    if path.exists():
        if not path.is_file() or path.read_bytes() != data:
            raise ValueError('immutable census conflict: ' + str(path))
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.census-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temp, path)
        except FileExistsError:
            if path.is_symlink() or path.read_bytes() != data:
                raise ValueError('concurrent census conflict: ' + str(path))
    finally:
        os.unlink(temp)


def lattice_points(residue, period, lo, hi, *, endpoints=False):
    """Exact rational lattice intersections, with explicit endpoint treatment."""
    residue, period, lo, hi = map(Fraction, (residue, period, lo, hi))
    if period <= 0 or lo > hi:
        raise ValueError('invalid lattice interval')
    first = math.ceil((lo - residue) / period)
    last = math.floor((hi - residue) / period)
    return tuple(q for k in range(first, last + 1)
                 if (lo <= (q := residue + k * period) <= hi if endpoints
                     else lo < (q := residue + k * period) < hi))


def rate_topology(cell, op):
    stages = make_native_stages(cell['profile']) + make_src_stages(op)
    spacing = op.output_hz
    path_count = 1
    transitions = []
    stage_rows = []
    for i, stage in enumerate(stages):
        taps = [(k, value.hex()) for k, value in stage.taps]
        stage_rows.append(dict(
            index=i, kind=stage.kind, input_hz=stage.input_hz,
            output_hz=freqstr(stage.output_hz), L=stage.L, M=stage.M,
            taps=len(stage.taps), exact_binary64_taps_sha256=digest(taps),
        ))
    for i in range(len(stages) - 1, -1, -1):
        stage = stages[i]
        if stage.output_hz.denominator != 1 or int(stage.output_hz) % spacing:
            raise ValueError('nonintegral/inconsistent reverse residue group')
        upstream = math.gcd(spacing, stage.input_hz)
        # Uniformity follows from the homomorphism of complete cyclic residue
        # groups; the quotient counts colliding paths, not discarded aliases.
        if (stage.L * upstream) % spacing:
            raise ValueError('nonuniform reverse alias group unsupported')
        transitions.append(dict(
            stage=i, kind='inverse_branch_window',
            residue_hz=freqstr(Fraction(stage.L * stage.input_hz, 2) % spacing),
            period_hz=str(spacing),
        ))
        transitions.append(dict(
            stage=i, kind='input_frequency_fold',
            residue_hz=freqstr(Fraction(stage.input_hz, 2) % upstream),
            period_hz=str(upstream),
        ))
        path_count *= stage.M
        spacing = upstream
    native = cell['native_hz']
    family_count = native // spacing
    if (native % spacing or Fraction(op.output_hz, op.U) != spacing or
            path_count % family_count):
        raise ValueError('rate-only native lattice differs from bound operator')
    # Deduplicate identical grids for a compact exact event union.  The
    # per-stage list above retains the origin of every grid.
    grids = sorted({(Fraction(t['residue_hz']), Fraction(t['period_hz']))
                    for t in transitions})
    points = sorted({point for residue, period in grids
                     for point in lattice_points(residue, period, 0,
                                                 Fraction(op.output_hz, 2))})
    pair = SNAPSHOTS / f"{cell['intermediate_hz']}-{cell['output_hz']}"
    return dict(
        native_hz=native, intermediate_hz=cell['intermediate_hz'],
        output_hz=cell['output_hz'], stage_count=len(stages),
        native_stage_count=sum(s.kind.startswith('native-') for s in stages),
        src_stage_count=sum(s.kind.startswith('src-') for s in stages),
        stages=stage_rows, complete_path_count=path_count,
        primitive_source_family_count=family_count,
        path_multiplicity_per_primitive_family=path_count // family_count,
        primitive_frequency_spacing_hz=str(spacing),
        exact_stage_transition_lattices=transitions,
        exact_routing_transition_points_hz=[freqstr(q) for q in points],
        stage_snapshot_sha256=sha_file(pair / 'stage-snapshot.json'),
        operator_binding_sha256=sha_file(pair / 'operator-binding.json'),
        scope='Exact rate-only schedule census; no spectral or phase-cancellation claim',
    )


def record(file, doc):
    cert = doc['certificate']
    result = dict(path=relative(file), sha256=sha_file(file),
                  status=cert['status'], reason=cert.get('reason'),
                  counters={k: cert[k] for k in COUNTERS if k in cert})
    for key in ('measurement', 'prover_code_sha256', 'proof_code_sha256',
                'stage_snapshot_sha256', 'verified_operator_binding_sha256'):
        if key in doc:
            result[key] = doc[key]
        elif key in cert:
            result[key] = cert[key]
    return result


def validate_overlay(doc, by_hash, binding):
    job = doc.get('job')
    if not isinstance(job, dict) or digest(job) not in by_hash or by_hash[digest(job)] != job:
        raise ValueError('measurement is not a canonical work item')
    if doc.get('binding') != binding or doc.get('qualified_release') is not False:
        raise ValueError('measurement source/design or release binding mismatch')
    cert = doc.get('certificate')
    expected = 'PASS-LOCAL-BAND' if job['mode'] == 'pass' else 'PASS-LOCAL-STOP-SOURCE'
    if not isinstance(cert, dict) or cert.get('status') not in ('OPEN', expected):
        raise ValueError('measurement has an incompatible spectral disposition')
    if cert.get('qualified_release', False) is not False:
        raise ValueError('unauthorized inner release claim')
    if cert['status'] != 'OPEN' and (
        cert.get('certified_hz') != [job['lo'], job['hi']] or
        cert.get('band_kind') != job['mode'] or
        cert.get('input_hz') != job['intermediate_hz'] or
        cert.get('output_hz') != job['output_hz'] or
        cert.get('profile') != job['profile'] or
        cert.get('governing_passband_hz') != PROFILE_BANDS[job['profile']][0]
    ):
        raise ValueError('measurement certificate does not cover its canonical job')

    # Historical campaign receipts have only the canonical source/design
    # binding. Preserve their original schema, but validate every additional
    # source/operator binding when supplied by a newer local experiment.
    containers = [('receipt', doc), ('certificate', cert)]
    if 'experiment_identity' in doc:
        identity = doc['experiment_identity']
        if not isinstance(identity, dict):
            raise ValueError('invalid experiment identity')
        mirrored = ('job', 'binding', 'prover_code_sha256',
                    'stage_snapshot_sha256', 'verified_operator_binding_sha256')
        if any(key not in doc or key not in identity or doc[key] != identity[key]
               for key in mirrored):
            raise ValueError('experiment identity does not mirror receipt bindings')
        # Also cover optional duplicated harness, label, resource, and future
        # identity fields without requiring historical receipts to invent them.
        if any(key in doc and doc[key] != value for key, value in identity.items()):
            raise ValueError('conflicting duplicated experiment identity field')
        code = doc['prover_code_sha256']
        if (not isinstance(code, dict) or not code or
                any(not isinstance(name, str) or not name or
                    not isinstance(value, str) or len(value) != 64 or
                    any(c not in '0123456789abcdef' for c in value)
                    for name, value in code.items())):
            raise ValueError('invalid experiment prover hash mapping')
        # Hash equality between baseline and candidate is deliberately NOT an
        # obligation. Each experiment binds its own implementation; independent
        # replay checks that mapping against its separately frozen source tree.
        if ('profiling_enabled' in identity and
                isinstance(doc.get('measurement'), dict) and
                'profiling_enabled' in doc['measurement'] and
                identity['profiling_enabled'] != doc['measurement']['profiling_enabled']):
            raise ValueError('conflicting experiment profiling identity')
        containers.append(('experiment_identity', identity))

    pair_fields = ('stage_snapshot_sha256', 'verified_operator_binding_sha256')
    if any(key in item for _, item in containers for key in pair_fields):
        pair = SNAPSHOTS / f"{job['intermediate_hz']}-{job['output_hz']}"
        expected = dict(
            stage_snapshot_sha256=sha_file(pair / 'stage-snapshot.json'),
            verified_operator_binding_sha256=sha_file(pair / 'operator-binding.json'),
        )
        for where, item in containers:
            if any(key in item and item[key] != value for key, value in expected.items()):
                raise ValueError(where + ' operator snapshot/binding SHA mismatch')
    source_fields = dict(source_sha256=binding['source'],
                         governing_dsd_design_sha256=binding['design'])
    for where, item in containers:
        if any(key in item and item[key] != value for key, value in source_fields.items()):
            raise ValueError(where + ' source/design SHA mismatch')
    return digest(job)


def read_overlays(sources, by_hash, binding):
    result = defaultdict(lambda: defaultdict(list))
    source_rows = []
    for label, directory in sources:
        if not label or not directory.is_dir() or directory.is_symlink():
            raise ValueError('invalid labeled measurement directory')
        recognized = 0
        for file in sorted(directory.rglob('*.json')):
            if file.is_symlink() or not file.is_file():
                raise ValueError('linked measurement refused')
            doc = json.loads(file.read_text())
            if not isinstance(doc, dict) or 'job' not in doc or 'certificate' not in doc:
                continue  # Metadata/benchmarks are not campaign receipts.
            work = validate_overlay(doc, by_hash, binding)
            result[work][label].append(record(file, doc))
            recognized += 1
        source_rows.append(dict(label=label, directory=relative(directory),
                                recognized_canonical_receipts=recognized))
    # The four final third-pass local receipts have explicit source/operator
    # bindings but predate the job wrapper. Match only exact canonical jobs.
    by_local = {(j['profile'], j['intermediate_hz'], j['output_hz'],
                 j['mode'], j['lo'], j['hi']): work
                for work, j in by_hash.items()}
    for file in sorted((THIRD_PASS / 'final_local_certificates').glob('*.json')):
        if file.is_symlink():
            raise ValueError('linked third-pass local receipt')
        cert = json.loads(file.read_text())
        key = (cert['profile'], cert['input_hz'], cert['output_hz'],
               cert['band_kind'], *cert['certified_hz'])
        work = by_local.get(key)
        if work is None:
            raise ValueError('third-pass local receipt is not canonical')
        pair = SNAPSHOTS / f"{cert['input_hz']}-{cert['output_hz']}"
        if (cert.get('source_sha256') != binding['source'] or
            cert.get('governing_dsd_design_sha256') != binding['design'] or
            cert.get('stage_snapshot_sha256') != sha_file(pair / 'stage-snapshot.json') or
            cert.get('verified_operator_binding_sha256') != sha_file(pair / 'operator-binding.json')):
            raise ValueError('third-pass local receipt binding mismatch')
        doc = dict(job=by_hash[work], binding=binding, certificate=cert,
                   qualified_release=False)
        validate_overlay(doc, by_hash, binding)
        result[work]['third_pass_final_local'].append(record(file, doc))
    return result, source_rows


def state_classification(original, measurements):
    """Report observed outcomes only; do not infer mathematical impossibility."""
    classes = []
    if original['status'].startswith('PASS'):
        classes.append('historical_certified_local_interval')
    else:
        reason = original.get('reason') or ''
        classes.append('historical_budget_exhaustion' if 'budget' in reason else
                       'historical_operator_precondition' if 'precondition' in reason else
                       'historical_other_open')
    current = {label: docs for label, docs in measurements.items()
               if not label.startswith('historical_') and label != 'third_pass_final_local'}
    if not current:
        classes.append('current_run_unmeasured')
    for label, docs in sorted(current.items()):
        passes = [d for d in docs if d['status'].startswith('PASS')]
        classes.append(label + (':observed_local_pass' if passes else ':observed_open'))
    return classes


def select_corpus(rows):
    groups = defaultdict(list)
    for row in rows:
        job = row['job']
        if job['output_hz'] == 384000 or (
                job['cell_id'].startswith('dsd256.') and job['output_hz'] in (192000, 44100)):
            groups[(job['cell_id'], job['mode'])].append(row)
    selected = {}
    for (cell, mode), entries in sorted(groups.items()):
        positions = [(0, 'dc_boundary'), (len(entries) // 2, 'band_interior'),
                     (len(entries) - 1, 'upper_guaranteed_passband_edge' if mode == 'pass'
                      else 'pcm_nyquist_boundary')]
        if mode == 'pass':
            positions.extend([(len(entries) // 4, 'lower_interior'),
                              (3 * len(entries) // 4, 'upper_interior')])
        else:
            positions.append((3 * len(entries) // 4, 'upper_stop_output_interior'))
            for i, row in enumerate(entries):
                if Fraction(row['job']['lo']) <= row['job']['source_s'] <= Fraction(row['job']['hi']):
                    positions.append((i, 'native_S_in_output_coordinates'))
            positions.append((max(range(len(entries)), key=lambda i: len(
                entries[i]['exact_routing_transition_points_hz'])), 'dense_routing_transitions'))
        for position, why in positions:
            row = entries[position]
            item = selected.setdefault(row['work_sha256'], dict(
                canonical_index=row['canonical_index'], work_sha256=row['work_sha256'],
                job=row['job'], original=row['original'],
                complete_path_count=row['complete_path_count'],
                primitive_source_family_count=row['primitive_source_family_count'],
                exact_routing_transition_points_hz=row['exact_routing_transition_points_hz'],
                exact_stop_membership_crossings_hz=row['exact_stop_membership_crossings_hz'],
                selection_reasons=[]))
            item['selection_reasons'].append(why)
    return sorted(selected.values(), key=lambda x: x['canonical_index'])


def create_census(output, measurements=()):
    jobs = canonical_plan()
    if len(jobs) != 11516:
        raise ValueError('canonical campaign population changed')
    by_hash = {digest(j): j for j in jobs}
    if len(by_hash) != len(jobs):
        raise ValueError('duplicate canonical work identity')
    binding = bindings()
    operators = source_operators(jobs)
    cells = {c['id']: c for c in all_active_cells()}
    topologies = {name: rate_topology(c, operators[(c['intermediate_hz'], c['output_hz'])])
                  for name, c in cells.items()}
    overlays, overlay_inputs = read_overlays(
        [('historical_600s', HISTORY / 'budget-sample'), *measurements], by_hash, binding)
    counts = Counter()
    reasons = Counter()
    by_cell = defaultdict(lambda: defaultdict(Counter))
    rows = []
    inventory = []
    for index, job in enumerate(jobs):
        work = digest(job)
        doc = check_one(HISTORY / 'receipts', job, binding)
        if doc is None:
            raise ValueError('missing canonical historical receipt')
        file = receipt_path(HISTORY / 'receipts', job)
        original = record(file, doc)
        inventory.append((file.name, original['sha256']))
        counts[original['status']] += 1
        if original['status'] == 'OPEN':
            reasons[original['reason'].split(':', 1)[0]] += 1
        topo = topologies[job['cell_id']]
        lo, hi = Fraction(job['lo']), Fraction(job['hi'])
        points = [q for q in topo['exact_routing_transition_points_hz'] if lo < Fraction(q) < hi]
        source_s = Fraction(job['source_s'])
        spacing = Fraction(topo['primitive_frequency_spacing_hz'])
        membership = sorted({q for sign in (-1, 1)
                             for q in lattice_points(sign * source_s, spacing, lo, hi)})
        stops = [lo, *(Fraction(q) for q in points), hi]
        flags = []
        if lo == 0:
            flags.append('dc')
        if job['mode'] == 'pass' and hi == Fraction(job['effective_p']):
            flags.append('guaranteed_passband_upper_edge')
        if hi == Fraction(job['output_hz'], 2):
            flags.append('pcm_nyquist')
        if lo <= source_s <= hi:
            flags.append('native_S_in_output_coordinates')
        if points:
            flags.append('interior_routing_transition')
        if membership:
            flags.append('native_stop_membership_transition')
        row = dict(
            canonical_index=index, work_sha256=work, job=job,
            source_native_hz=topo['native_hz'], dsd_rate=topo['native_hz'] // 44100,
            interval_width_hz=freqstr(hi - lo), frequency_features=flags,
            original=original, observations=dict(overlays.get(work, {})),
            classification=state_classification(original, overlays.get(work, {})),
            topology_cell=job['cell_id'], complete_path_count=topo['complete_path_count'],
            primitive_source_family_count=topo['primitive_source_family_count'],
            path_multiplicity_per_primitive_family=topo['path_multiplicity_per_primitive_family'],
            exact_routing_transition_points_hz=points,
            exact_stationary_piece_widths_hz=[freqstr(b - a) for a, b in zip(stops, stops[1:])],
            exact_stop_membership_crossings_hz=[freqstr(q) for q in membership],
            estimated_effort=dict(
                method='structural work proxy, not a wall-clock prediction',
                full_path_visits_for_one_cover=topo['complete_path_count'] * (len(points) + 1),
                stage_count=topo['stage_count'],
                unresolved_cause='requires numerical measurement' if original['status'] == 'OPEN' else None,
            ),
        )
        rows.append(row)
        by_cell[job['cell_id']]['original_' + job['mode']][original['status']] += 1
        for label, docs in row['observations'].items():
            status = 'PASS' if any(d['status'].startswith('PASS') for d in docs) else 'OPEN'
            by_cell[job['cell_id']][label + '_' + job['mode']][status] += 1
    if counts != Counter({'PASS-LOCAL-BAND': 1340, 'PASS-LOCAL-STOP-SOURCE': 5495, 'OPEN': 4681}):
        raise ValueError('historical receipt dispositions differ from pinned campaign')
    if reasons != Counter({'interval_wall_clock_budget_exhausted': 3907, 'operator_path_precondition': 774}):
        raise ValueError('historical OPEN reasons differ from pinned campaign')
    state = sha256()
    for name, sha in sorted(inventory):
        state.update(name.encode() + b'\0' + sha.encode() + b'\n')
    cell_rows = []
    for name, c in sorted(cells.items()):
        relevant = [row for row in rows if row['job']['cell_id'] == name]
        P, S = PROFILE_BANDS[c['profile']]
        cell_rows.append(dict(
            **c, declared_P_hz=P, declared_S_hz=S,
            effective_P_hz=relevant[0]['job']['effective_p'],
            canonical_pass_intervals=sum(r['job']['mode'] == 'pass' for r in relevant),
            canonical_stop_intervals=sum(r['job']['mode'] == 'stop' for r in relevant),
            counts={k: dict(v) for k, v in sorted(by_cell[name].items())},
            topology=topologies[name],
        ))
    corpus = select_corpus(rows)
    summary = dict(
        schema=SCHEMA, release='BLOCKED', qualified_release=False,
        purpose='Evidence census only; observed receipts retain original scope and disposition',
        canonical_intervals=len(rows), cells=len(cells), original_dispositions=dict(counts),
        original_open_reasons=dict(reasons),
        original_receipt_inventory_sha256=state.hexdigest(),
        original_summary_sha256=sha_file(HISTORY / 'SUMMARY.json'),
        census_code_sha256=sha_file(Path(__file__)),
        design_sha256=binding['design'], source_identity=binding['source'],
        measurement_inputs=overlay_inputs, selected_corpus_intervals=len(corpus),
        mathematical_limits=dict(passband_db='0.0001', coherent_alias_db='-160'),
        transition_census_method=(
            'Exact reverse cyclic residue groups: d <- gcd(d, Fin); branch window '
            'L*Fin/2 modulo old d; input fold Fin/2 modulo new d. All complete '
            'path multiplicities retained. Native stop membership +/-S modulo final d.'),
        limitations=[
            'An OPEN timeout does not establish spectral failure or insufficient mathematical bounds.',
            'Current observations are explicit overlays; the historical campaign is never relabeled.',
            'Rate topology does not prove a phase identity, permit cancellation, or provide a spectral certificate.',
            'Stop jobs concern native-source frequencies >= S folding into an output interval; their output coordinate is not a native-source band.',
            'An individual PASS does not establish complete cell coverage or FFT4G execution-roundoff bounds.',
        ],
    )
    output.mkdir(parents=True, exist_ok=True)
    if output.is_symlink():
        raise ValueError('linked census directory refused')
    files = {
        'intervals.jsonl': b''.join((json.dumps(r, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode() for r in rows),
        'cells.json': encoded(cell_rows), 'summary.json': encoded(summary),
        'corpus.json': encoded(corpus),
    }
    lines = [
        '# P15 high-rate canonical census', '',
        'Release remains **BLOCKED**. This census checks all 11,516 historical canonical receipts against the current pinned source/design identity. Historical counts remain 6,835 local passes and 4,681 OPEN.', '',
        'The matrix reports the original 60-second campaign. Explicit later observations remain separate in `intervals.jsonl` and `cells.json`. A timeout is not a spectral violation.', '',
        '| Cell | P / S (Hz) | Pass total / OPEN | Stop total / OPEN | Paths / families | SRC stages |',
        '|---|---:|---:|---:|---:|---:|',
    ]
    for c in cell_rows:
        if c['output_hz'] != 384000 and not (c['native_hz'] == 11289600 and c['output_hz'] == 192000):
            continue
        t = c['topology']
        lines.append(f"| {c['id']} | {c['effective_P_hz']} / {c['declared_S_hz']} | {c['canonical_pass_intervals']} / {c['counts']['original_pass'].get('OPEN', 0)} | {c['canonical_stop_intervals']} / {c['counts']['original_stop'].get('OPEN', 0)} | {t['complete_path_count']} / {t['primitive_source_family_count']} | {t['src_stage_count']} |")
    lines += [
        '', '## What the census establishes', '',
        '- All 2,151 historical OPEN intervals at 384 kHz were time-budget exhaustions. The old 774 operator-precondition outcomes occur in other cells; they are not evidence that 384 kHz is structurally unsupported.',
        '- DSD256 mastering to 384 kHz is the smallest preferred complete difficult target: 40 passband intervals plus 192 native-source-stop intervals. Its 9,408 paths have no native-family collisions.',
        '- DSD256 wideband to 192 kHz has 9,408 paths for 4,704 primitive families. Its 188 original OPEN outcomes came from the old single-path/count precondition; later code admits complete multiplicities. It is a useful structural-regression target.',
        '- The rate-only transition census gives exact rational event locations for every canonical interval. These are distinct from native-stop-membership crossings at +S and -S modulo the primitive source spacing. Membership crossings can make whole-interval inclusion conservative; a numerical experiment is required before attributing an OPEN to that conservatism.',
        '', '## Reproduce', '', 'From the repository root:', '', '```sh',
        'PYTHONPATH=tests/dsd OPENBLAS_NUM_THREADS=1 python tests/dsd/p15_high_rate_census.py --output NEW_DIRECTORY',
        '```', '',
        'Add `--measurement baseline=BASELINE_DIRECTORY --measurement candidate=CANDIDATE_DIRECTORY` to overlay new campaign-shaped receipts. Publication is exclusive and idempotent. Use a fresh output directory whenever inputs change.', '',
        '`corpus.json` selects DC, interior, upper passband, output Nyquist, dense-routing and native-S-coordinate intervals across all nine 384 kHz cells and DSD256 192/44.1 kHz cells. Selection is reproducible and does not change normative acceptance bands.', '',
        '## Exact topology argument and limits', '',
        'Start with the output residue group containing only zero, spacing Fout. If a reverse-stage input group has spacing d modulo its output clock, the full M branches of an L/M stage generate the subgroup with spacing gcd(d, Fin) modulo Fin. All branch multiplicities are retained. Branch-window changes occur at L*Fin/2 modulo d; input-frequency wrapping changes at Fin/2 modulo gcd(d, Fin). Their union identifies the open regions on which every inverse-path affine argument remains fixed. Endpoints remain subject to the prover’s independent one-sided checks.', '',
        'The final spacing is checked against the captured operator’s Fout/U. The complete path population is the product of stage denominators, and its ratio to native_hz/spacing records path multiplicity. The census does not combine transfer amplitudes, infer phase cancellation, or issue a spectral PASS.', '',
        'The structural work proxy multiplies complete paths by stationary pieces. It is not a runtime estimate: FIR lengths, upper-bound looseness, cache reuse and subdivision can dominate actual work. Current causes remain unclassified until numerical measurements demonstrate them.',
    ]
    files['README.md'] = ('\n'.join(lines) + '\n').encode()
    for name, data in files.items():
        publish(output / name, data)
    manifest = ''.join(f"{sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items()))
    publish(output / 'SHA256SUMS', manifest.encode())
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--measurement', action='append', default=[], metavar='LABEL=DIRECTORY')
    args = parser.parse_args()
    sources = []
    for value in args.measurement:
        if '=' not in value:
            parser.error('--measurement requires LABEL=DIRECTORY')
        label, directory = value.split('=', 1)
        if label.startswith('historical_') or label == 'third_pass_final_local':
            parser.error('reserved historical measurement label')
        if any(label == old for old, _ in sources):
            parser.error('duplicate measurement label')
        sources.append((label, Path(directory)))
    result = create_census(args.output, sources)
    print(json.dumps({key: result[key] for key in ('canonical_intervals', 'cells', 'original_dispositions', 'selected_corpus_intervals')}, sort_keys=True))


if __name__ == '__main__':
    main()
