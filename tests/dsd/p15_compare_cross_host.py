#!/usr/bin/env python3
"""Compare two host runs by SOURCE WAV and decoded DSF chronology, not file hashes alone.

Difference is a diagnostic, not failure: DSD_DESIGN 8.6 does not promise
cross-host scalar SDM byte identity. Run frozen analysis-v1 separately for
quality/stability on real recordings if bit chronologies differ.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import json

from p15_matrix_contract import write_json_atomic
from reference.verify import decode_dsf


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as src:
        for chunk in iter(lambda: src.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def compare(first_wav: Path, second_wav: Path, first_dsf: Path, second_dsf: Path) -> dict:
    wav_hashes = [sha_file(p) for p in (first_wav, second_wav)]
    result = dict(schema='P15/cross-host-scalar-diagnostic/1',
                  authority='DSD_DESIGN 8.6, 10.2, 10.6',
                  cross_host_scalar_bit_equality_required=False,
                  source_wav_sha256=wav_hashes,
                  source_bytes_identical=wav_hashes[0] == wav_hashes[1],
                  dsf_file_sha256=[sha_file(p) for p in (first_dsf, second_dsf)],
                  status='SOURCE_MISMATCH',
                  release_quality_claim='NONE: independent analysis-v1 spectral and state receipts still required')
    if not result['source_bytes_identical']:
        return result
    native = [decode_dsf(p.read_bytes()) for p in (first_dsf, second_dsf)]
    identities = [dict(channels=n['channels'], native_frames=n['frames'],
                       native_rate_hz=n['rate'],
                       chronology_sha256=n['chronological_bits_sha256']) for n in native]
    result['native'] = identities
    result['native_counts_and_rate_match'] = all(
        identities[0][key] == identities[1][key] for key in
        ('channels', 'native_frames', 'native_rate_hz'))
    result['chronological_bits_identical'] = (
        identities[0]['chronology_sha256'] == identities[1]['chronology_sha256'])
    result['status'] = ('MATCHING_AUDIO' if result['native_counts_and_rate_match']
                        and result['chronological_bits_identical'] else 'AUDIO_DIFFERS_NEEDS_METROLOGY')
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    for arg in ('first-wav', 'second-wav', 'first-dsf', 'second-dsf', 'output'):
        ap.add_argument('--' + arg, type=Path, required=True)
    a = ap.parse_args()
    report = compare(a.first_wav, a.second_wav, a.first_dsf, a.second_dsf)
    write_json_atomic(a.output, report)
    print(json.dumps(dict(status=report['status'], native=report.get('native'))))
    return 2 if report['status'] == 'SOURCE_MISMATCH' else 0


if __name__ == '__main__':
    raise SystemExit(main())
