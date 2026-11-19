"""Phase 08: retained SSE2 reconstruction words and bounded cross-ISA comparison.

The compressed words were taken from the accepted R3 physical receipts (18
short cases), plus the independently pinned gain-effect CLI case. Their exact
SHA-256 values are in accepted-physical-behavior.json, which predated this
fixture. Never regenerate this fixture from the candidate under test.

The CLI and public API still have to match exactly *within one selected kernel*;
that route/partition check is distinct from this accepted numeric reference.
"""
from __future__ import annotations

from functools import lru_cache
import hashlib
import math
from pathlib import Path
import struct
import zlib

from attestation import approved_behavior

REFERENCE_BACKEND = 'sse2'
# Maximum observed accepted R3 scalar/SIMD deviation is O(1e-16).
# 2^-48 (~3.55e-15) PCM units permits alternate binary64 summation order
# but not a meaningful gain/filter change (roughly 7e-15 of DSD +/-0.5 FS).
CROSS_BACKEND_MAX_ABS = 2.0**-48
_FRAMES, _CHANNELS, _WORD_SIZE = 1537, 2, 8
_CASE_BYTES = _FRAMES*_CHANNELS*_WORD_SIZE
_COMPRESSED_SHA256 = 'dde0a8fb4cf13bd595ba068ad0bc7ca1bab13a8010943ecdd64ef02a50175e21'
_FIXTURE = Path(__file__).with_name('reference')/'accepted-reconstruction-sse2.zlib'


def insist(ok, reason):
    if not ok:
        raise AssertionError(reason)


@lru_cache(maxsize=1)
def accepted_words():
    """Load immutable, individually hash-checked words, not a running decoder."""
    accepted = approved_behavior()
    digests = {case: entry['reconstructed_float64_words_sha256']
               for case, entry in accepted['short_cases'].items()}
    digests['gain_effect'] = accepted['target_cases']['gain_effect'][
        'reconstructed_float64_words_sha256']
    names = sorted(digests)
    compressed = _FIXTURE.read_bytes()
    insist(hashlib.sha256(compressed).hexdigest()==_COMPRESSED_SHA256,
           'accepted SSE2 reconstruction fixture itself changed')
    words = zlib.decompress(compressed)
    insist(len(names)==19 and len(words)==len(names)*_CASE_BYTES,
           'accepted SSE2 reconstruction fixture has wrong shape')
    result = {}
    for index, name in enumerate(names):
        raw = words[index*_CASE_BYTES:(index+1)*_CASE_BYTES]
        insist(hashlib.sha256(raw).hexdigest()==digests[name],
               f'{name}: accepted reconstruction words disagree with prior frozen digest')
        result[name] = raw
    return result


def check_reconstruction(raw, name, actual_backend):
    """Verify independently retained values; never trust the receipt as oracle.

    Exact file/receipt and same-backend CLI/API comparisons belong to callers.
    Only the numerical comparison between different selected kernels uses a
    tolerance. Nonfinite values fail unconditionally.
    """
    reference = accepted_words()[name]
    insist(actual_backend in ('scalar', 'sse2', 'avx1', 'avx2', 'avx512'),
           f'{name}: unknown reconstruction kernel {actual_backend!r}')
    insist(len(raw)==len(reference),f'{name}: wrong reconstructed binary64 payload length')
    if actual_backend==REFERENCE_BACKEND:
        insist(raw==reference,
               f'{name}: selected SSE2 backend differs from exact accepted words')
        return {'reference_backend': REFERENCE_BACKEND, 'comparison': 'exact',
                'max_absolute_error': 0.0}
    max_error=0.0
    for (actual,), (expected,) in zip(struct.iter_unpack('<d',raw),
                                     struct.iter_unpack('<d',reference)):
        insist(math.isfinite(actual) and math.isfinite(expected),
               f'{name}: nonfinite reconstructed PCM sample')
        error=abs(actual-expected)
        insist(error<=CROSS_BACKEND_MAX_ABS,
               f'{name}: {actual_backend} reconstruction exceeds independently '
               f'accepted cross-ISA error: {error:.17g} > {CROSS_BACKEND_MAX_ABS:.17g}')
        max_error=max(max_error,error)
    return {'reference_backend':REFERENCE_BACKEND, 'comparison':'absolute_binary64_bound',
            'max_allowed_absolute_error':CROSS_BACKEND_MAX_ABS,
            'max_absolute_error':max_error}
