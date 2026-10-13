#!/usr/bin/env python3
"""Review provenance/completeness of an older-AVX physical receipt.

This is not a numerical/metrology certificate. It blocks inconsistent host
identity or absent raw measurements before a reviewer considers the timing.
Cross-host SDM byte equality is deliberately NOT an acceptance condition.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

from p15_matrix_contract import write_json_atomic

ROOT = Path(__file__).resolve().parents[2]
REQUIRED_MODES = ('fir-single', 'fir-block', 'sdm')
REQUIRED_TIERS = ('scalar', 'sse2', 'avx1')
BENCH_SOURCES = (
    'src/dsd_dispatch.c', 'src/dsd_kernels_scalar.c',
    'src/dsd_kernels_sse2.c', 'src/dsd_kernels_avx1.c',
    'src/dsd_kernels_avx2.c', 'src/dsd_kernels_avx512.c',
    'src/dsd_coeffs.h', 'src/sdm.c', 'src/sdm_normal_commit_i.h',
    'tests/dsd/test_p11.c', 'tests/dsd/bench_p11.py',
)
REQUIRED_FILES = (
    'host.txt', 'gate-eligibility.txt', 'clock.txt', 'kernel.log',
    'kernel-output-sha256.txt', 'kernel/kernel-timing.json',
)


def inspect_receipt(directory: Path, source_root: Path = ROOT) -> dict:
    problems: list[str] = []
    present = {}
    for name in REQUIRED_FILES:
        location = directory / name
        present[name] = location.is_file() and location.stat().st_size > 0
        if not present[name]:
            problems.append('missing or empty raw receipt: ' + name)

    host_path = directory / 'host.txt'
    metadata = {}
    if host_path.is_file():
        content = host_path.read_text(encoding='utf-8', errors='replace')
        patterns = {
            'model': r'^model name\s*:\s*(.+)$',
            'microcode': r'^microcode\s+(\S+)$',
            'avx': r'^avx / avx2\s+(yes|no)\s*/\s*(yes|no)\s*$',
            'virt': r'^virt\s+(.+)$',
        }
        for key, pattern in patterns.items():
            match = re.search(pattern, content, flags=re.MULTILINE)
            if match:
                metadata[key] = match.groups() if key == 'avx' else match.group(1).strip()
            else:
                problems.append('host.txt lacks independently checkable ' + key)
        if metadata.get('avx') != ('yes', 'no'):
            problems.append('not proven AVX1 without AVX2; host flags: ' + str(metadata.get('avx')))
        if metadata.get('virt') != 'none (hypervisor flag absent)':
            problems.append('not proven nonvirtualized physical host: ' + str(metadata.get('virt')))

    eligible_path = directory / 'gate-eligibility.txt'
    if eligible_path.is_file() and not re.search(
            r'^gate_relevant=yes\s*$', eligible_path.read_text(errors='replace'), re.MULTILINE):
        problems.append('runner did not assert gate_relevant=yes on this host')

    clock_path = directory / 'clock.txt'
    clocks = {}
    if clock_path.is_file():
        for line in clock_path.read_text(errors='replace').splitlines():
            match = re.search(r'^\s*(scalar|sse2|avx1)\s+median\s+([\d.]+)\s+MHz.*?busy samples\s+(\d+)\s+of\s+(\d+)', line)
            if match:
                tier, value, busy, total = match.groups()
                clocks[tier] = dict(mhz=float(value), busy=int(busy), total=int(total))
        if set(clocks) != set(REQUIRED_TIERS):
            problems.append('no full scalar/SSE2/AVX1 measured-clock set')
        elif any(row['busy'] < 10 or row['busy'] > row['total'] or row['mhz'] <= 0 for row in clocks.values()):
            problems.append('invalid or insufficient measured-clock samples')
        else:
            mhz = [row['mhz'] for row in clocks.values()]
            if (max(mhz) - min(mhz)) / min(mhz) > .02:
                problems.append('clock medians across tiers differ by more than 2%')

    bench_path = directory / 'kernel/kernel-timing.json'
    timing = {}
    if bench_path.is_file():
        try:
            timing = json.loads(bench_path.read_text())
            if not isinstance(timing, dict):
                raise ValueError('expected benchmark JSON object')
            config = timing.get('config', {})
            if not isinstance(config, dict):
                raise ValueError('expected benchmark config object')
            reps = config.get('repetitions', 0)
            if timing.get('status') != 'PASS' or not isinstance(reps, int) or reps < 15:
                problems.append('kernel benchmark not PASS with >=15 repetitions')
            if timing.get('errors') or timing.get('unrun'):
                problems.append('kernel benchmark contains errors or unrun arms')
            if not set(REQUIRED_MODES).issubset(config.get('modes', [])):
                problems.append('missing required kernel benchmark modes')
            if not set(REQUIRED_TIERS).issubset(config.get('tiers', [])):
                problems.append('missing required kernel benchmark tiers')
            grouped = {}
            rows = timing.get('raw', [])
            if not isinstance(rows, list):
                raise ValueError('expected benchmark raw array')
            for row in rows:
                if not isinstance(row, dict):
                    raise ValueError('non-object raw benchmark row')
                if row.get('exit') == 0:
                    key = (row.get('mode'), row.get('tier'))
                    grouped.setdefault(key, set()).add(row.get('round'))
            if not isinstance(reps, int) or reps < 15:
                reps = 15
            for mode in REQUIRED_MODES:
                for tier in REQUIRED_TIERS:
                    if len(grouped.get((mode, tier), set())) != reps:
                        problems.append(f'raw benchmark repetitions incomplete: {mode}/{tier}')
            source_hashes = timing.get('source_sha256', {})
            if not isinstance(source_hashes, dict):
                raise ValueError('expected source hash object')
            if set(source_hashes) != set(BENCH_SOURCES):
                problems.append('benchmark source hash inventory incomplete or unexpected')
            for relative, expected_hash in source_hashes.items():
                # Only the script's own well-defined paths, no arbitrary path
                # resolution driven by untrusted receipts.
                if not re.fullmatch(r'(?:src|tests/dsd)/[a-zA-Z0-9_.-]+', relative):
                    problems.append('invalid source path inside benchmark source hashes')
                    continue
                local = source_root / relative
                if (not isinstance(expected_hash, str) or not local.is_file()
                        or hashlib.sha256(local.read_bytes()).hexdigest() != expected_hash):
                    problems.append('benchmark source hash differs from delivered source: ' + relative)
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            problems.append('unparseable kernel benchmark: ' + str(exc))

    return dict(
        schema='P15/physical-older-avx-receipt-review/1',
        status='ADMISSIBLE_FOR_INDEPENDENT_REVIEW' if not problems else 'BLOCKED',
        ready_for_release=False,
        meaning='input provenance and raw kernel timing completeness, NOT full P15 ISA/numerical release acceptance',
        cross_host_byte_hash_requirement=False,
        host=metadata, measured_clocks=clocks,
        required_files_present=present, problems=problems,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = inspect_receipt(args.results)
    write_json_atomic(args.output, result)
    print(json.dumps(dict(status=result['status'], problems=result['problems']), sort_keys=True))
    return 0 if not result['problems'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
