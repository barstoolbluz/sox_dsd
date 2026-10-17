#!/usr/bin/env python3
"""Read-only, source-bound adjudication of the 2026-10-16 Intel run.

This is not a new release manifest or an Intel dispatch policy.  Check raw
samples and source pins rather than transcribing the operator's summary.
Historical 2026-10-14 UNRUN is immutable; current observation is MEASURED.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import statistics

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'tests/dsd/results/P15_intel_physical_avx512_2026-10-16'
FAMILIES = ('fir-block', 'fir-single', 'sdm')
TIERS = ('avx2', 'avx512')


class InvalidIntelReceipt(ValueError):
    pass


def require(ok: bool, message: str) -> None:
    if not ok:
        raise InvalidIntelReceipt(message)


def finite(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def close(actual: float, expected: float) -> bool:
    return math.isclose(actual, expected, abs_tol=1e-8, rel_tol=2e-8)


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def source_binding(pins: dict, root: Path) -> None:
    require(bool(pins), 'empty source identity')
    for name, digest in pins.items():
        relative = Path(name)
        require(not relative.is_absolute() and '..' not in relative.parts and
                re.fullmatch('[0-9a-f]{64}', digest) is not None,
                'invalid source pin: ' + name)
        source = root / relative
        require(source.is_file() and
                hashlib.sha256(source.read_bytes()).hexdigest() == digest,
                'measured Intel source differs: ' + name)


def check_series(raw: list[dict], summary: dict, measure: str,
                 *, family: str, tier: str) -> float:
    rows = [x for x in raw if x.get('tier') == tier and
            (x.get('mode') == family or x.get('family') == family)]
    require(len(rows) == 15 and len({x.get('round', x.get('repeat')) for x in rows}) == 15,
            'missing/duplicate Intel observations: ' + family + '/' + tier)
    require(all(x.get('exit') == 0 and finite(x.get(measure)) and
                x[measure] > 0 for x in rows),
            'nonfinite/failed Intel observation: ' + family + '/' + tier)
    values = [x[measure] for x in rows]
    median = statistics.median(values)
    mad = statistics.median(abs(x-median) for x in values)
    require(summary.get('samples') == 15 and
            close(summary['median_' + measure], median) and
            close(summary['mad_' + measure], mad),
            'Intel raw/summary mismatch: ' + family + '/' + tier)
    if measure == 'wall_seconds':
        require(len({x['sha256'] for x in rows}) == 1,
                'Intel repeated output digests differ: ' + family + '/' + tier)
        require(rows[0]['sha256'] == summary['output_sha256'],
                'Intel output summary digest mismatch: ' + family + '/' + tier)
    return median


def review(root: Path = ROOT, base: Path | None = None) -> dict:
    base = root / 'tests/dsd/results/P15_intel_physical_avx512_2026-10-16' if base is None else base
    matrix = read(base / 'benchmark-matrix.json')
    kernel = read(base / 'kernel/kernel-timing.json')
    require(matrix['schema'] == 'P13/benchmark-matrix/1' and
            kernel['schema'] == 'P13/kernel-timing/1' and
            matrix['status'] == kernel['status'] == 'PASS' and
            not matrix['errors'] and not kernel['errors'],
            'Intel receipt invalid status/schema/errors')
    require(matrix['config']['repetitions'] == kernel['config']['repetitions'] == 15 and
            matrix['config']['tiers'] == kernel['config']['tiers'] == list(TIERS),
            'Intel receipt coverage/config differs')
    require(matrix['host']['cpu_vendor'] == 'GenuineIntel' and
            'i9-11900H' in matrix['host']['cpu_model'] and
            matrix['host']['hypervisor_flag_observed'] is False and
            (base / 'gate-eligibility.txt').read_text().startswith('gate_relevant=yes\n'),
            'Intel receipt identity/eligibility differs')
    source_binding(matrix['source_sha256'], root)
    source_binding(kernel['source_sha256'], root)
    require({x['family'] for x in matrix['comparisons'] if x['suite'] == 'kernel'} ==
            set(FAMILIES), 'Intel kernel comparisons incomplete')
    comparisons = {}
    for family in FAMILIES:
        metrics = {tier: check_series(kernel['raw'], kernel['summary'][family][tier],
                         'cpu_ns_per_frame', family=family, tier=tier)
                   for tier in TIERS}
        reported = [x for x in matrix['comparisons']
                    if x['suite'] == 'kernel' and x['family'] == family]
        require(len(reported) == 1 and
                close(reported[0]['speedup_avx512_over_avx2'],
                      metrics['avx2'] / metrics['avx512']),
                'Intel kernel comparison cannot be reproduced: ' + family)
        comparisons[family] = round(metrics['avx2'] / metrics['avx512'], 6)
    files = sorted(base.glob('*/forced-cli-timing.json'))
    require(len(files) == 6, 'Intel full conversion configurations incomplete')
    e2e = {}
    for file in files:
        item = read(file)
        require(item['schema'] == 'P13/end-to-end-timing/1' and
                item['status'] == 'PASS' and not item['errors'] and
                item['config']['repetitions'] == 15 and
                set(item['summary']) == {'decode', 'encode'},
                'Intel conversion receipt invalid: ' + file.parent.name)
        for family in ('decode', 'encode'):
            metrics = {tier: check_series(item['measurements'],
                            item['summary'][family][tier], 'wall_seconds',
                            family=family, tier=tier)
                       for tier in TIERS}
            require(item['summary'][family]['avx2']['output_sha256'] ==
                    item['summary'][family]['avx512']['output_sha256'],
                    'Intel cross-tier output digest differs: ' + file.parent.name)
            row = [x for x in matrix['comparisons'] if
                   x['suite'] == file.parent.name and x['family'] == family]
            ratio = metrics['avx2'] / metrics['avx512']
            require(len(row) == 1 and close(row[0]['speedup_avx512_over_avx2'], ratio),
                    'Intel conversion comparison cannot be reproduced: ' + file.parent.name)
            e2e[file.parent.name + '/' + family] = round(ratio, 6)
    require(len(e2e) == 12 and len(matrix['comparisons']) == 15 and
            len(kernel['raw']) == 90,
            'Intel measurement population incomplete')
    clock = (base / 'clock.txt').read_text()
    for tier in ('scalar', 'sse2', *TIERS):
        match = re.search(r'^\s*' + tier +
                          r'\s+median (\d+) MHz\s+p10 (\d+)\s+p90 (\d+)',
                          clock, re.M)
        require(match is not None and len(set(match.groups())) == 1 and
                int(match.group(1)) == 2500,
                'Intel frequency observation missing/inconsistent: ' + tier)
    return dict(status='MEASURED-SCOPED', historical_policy_status='UNRUN-SCOPE-EXEMPT',
                representative_host_claim='operator-recorded physical; not independently attested',
                exact_host='i9-11900H', gate_relevant_receipt=True,
                source_pins_checked=len(set(matrix['source_sha256']) |
                                        set(kernel['source_sha256'])),
                kernel_speedups=comparisons, conversion_speedups=e2e,
                conversion_speedup_range=[min(e2e.values()), max(e2e.values())],
                four_tier_clocks_mhz=2500, clock_downshift_observed=False,
                intel_preference_authorized=False, release_authorized=False,
                limitations='One operator-recorded host; no cross-silicon qualification. '
                            'No claim of a broad Intel performance policy or automatic ISA preference.')
