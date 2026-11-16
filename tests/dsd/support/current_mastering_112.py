"""Read the 1.1.2 shipped mastering decoder banks for active regression oracles.

P06/P17 historical manifests remain frozen; never treat them as current
runtime truth when a profile's production FIR or decimation clock changes.
"""
from pathlib import Path
import hashlib
import json
import re

import numpy as np

ROOT = Path(__file__).resolve().parents[3]


def read_current_mastering():
    manifest = json.loads((ROOT/'tests/dsd/reference/mastering_passband_112.json').read_text())
    text = (ROOT/'src/dsd_coeffs_112.h').read_text()
    banks = {}
    for name, meta in manifest['banks']['decoder'].items():
        pattern = r'\blsx_dsd112_decoder_' + re.escape(name) + r'\[(\d+)\]\s*=\s*\{(.*?)\};'
        found = re.search(pattern, text, re.S)
        if found is None:
            raise AssertionError(f'production mastering 1.1.2 bank missing: {name}')
        values = np.array([float.fromhex(w.strip()) for w in found.group(2).split(',')
                           if w.strip()], dtype=np.float64)
        digest = hashlib.sha256(('\n'.join(v.hex() for v in values)+'\n').encode('ascii')).hexdigest()
        if len(values) != int(found.group(1)) or len(values) != meta['taps'] or digest != meta['sha256_float_hex']:
            raise AssertionError(f'production mastering bank changed without manifest: {name}')
        if not np.array_equal(values, values[::-1]):
            raise AssertionError(f'asymmetric mastering bank: {name}')
        banks['master112_'+name] = values
    return manifest['profiles'], banks


def active_p06_master256(manifest, banks):
    """Update a *copy* of the P06 runtime oracle, preserving historical files."""
    profiles, new_banks = read_current_mastering()
    banks.update(new_banks)
    runtime = profiles['dsd256']
    manifest['profiles']['master256'] = {
        'native_hz':runtime['native_hz'],
        'intermediate_hz':runtime['intermediate_hz'],
        'factor':runtime['factor'],
        'delay_native_frames':runtime['delay_native_frames'],
        'stage_banks':['halfband']*(runtime['stages']-1)+['master112_'+runtime['bank']],
    }
    return manifest, banks
