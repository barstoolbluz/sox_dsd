"""Accepted-production attestation and independent, fixed coefficient fixtures.

The expected SHA-256 and coefficient words are checked into the Phase 08
qualification reference *outside* the program under test. They are not
recreated from the current source/header, a running probe, or a receipt.
A changed production source requires explicit re-qualification, not an
automatic refresh of this reference manifest.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

REFERENCE=Path(__file__).with_name('reference')
# The predecessor manifest is immutable. Phase 08 deliberately changed these
# files under D7/D6/AM1/AM2; they are checked by their separate owner-scoped
# and executable Phase 08 gates, not certified as old production bytes.
# Every other legacy source remains tied to its immutable SHA-256 here.
PHASE08_CHANGED_SOURCES = frozenset({
    'src/dsd.c', 'src/dsd.h', 'src/dsd_decode.c', 'src/dsd_plan.c',
    'src/dsd_public.c', 'src/dsd_stats.c', 'src/gain.c',
    'src/pcmdsd.c', 'src/sox_dsd.h', 'src/sox_ng.c',
})

def digest(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda:f.read(1<<20),b''):h.update(block)
    return h.hexdigest()

def expected():
    return json.loads((REFERENCE/'accepted-8005f35.json').read_text())


def physical_contract():
    """Frozen accepted WAV-word and window identities, never a producer recipe.

    The fixture was transcribed once from the independently reviewed physical
    source WAVs at 1ca8702. Generating fresh audio or updating a receipt must
    not update it. Any change to this fixture requires separate human review.
    """
    contract=json.loads((REFERENCE/'physical-source-contract.json').read_text())
    if (contract.get('schema')!='phase08-independent-physical-input-contract/1' or
            contract.get('source_rate_hz')!=44100 or
            contract.get('channels')!=2 or
            len(contract.get('short',{}).get('cases',{}))!=18 or
            len(contract.get('long',{}).get('cases',{}))!=20):
        raise AssertionError('missing/changed accepted physical input contract')
    return contract

def approved_behavior():
    """Checked-in physical words from the accepted build, not a live probe.

    Source-pin changes never revise these independently reviewed outcomes.
    The short physical streams were checked with the frozen SDM recurrence
    and direct CLI admission; the long streams with the audited q-x analyzer.
    """
    data=json.loads((REFERENCE/'accepted-physical-behavior.json').read_text())
    if (data.get('schema')!='phase08-approved-physical-behavior/1' or
            len(data.get('short_cases',{}))!=18 or
            len(data.get('long_cases',{}))!=20 or
            set(data.get('target_cases',{}))!=
            {'overrange','gain_effect','dff_nonbyte'}):
        raise AssertionError('missing/incomplete approved independent behavioral words')
    return data


def verify(source):
    source=Path(source).resolve()
    p=expected()
    if p.get('schema')!='p08-accepted-source-independent-reference/1':
        raise AssertionError('unrecognized independent qualification baseline')
    for relative,want in p['source_file_sha256'].items():
        path=source/relative
        if not path.is_file() or not path.resolve().is_relative_to(source):
            raise AssertionError('missing accepted production source: '+relative)
        if digest(path) != want and relative not in PHASE08_CHANGED_SOURCES:
            raise AssertionError('unapproved production source changed: '+relative)
    # The changed encoder/decoder tables and headers have separate byte-exact
    # owner-scope verification; do not silently extend the old accepted
    # source identity to them.
    from immutable_reference_guard import (owner_approvals,
        validate_owner_pcmdsd, validate_decoder_table, validate_am1_header)
    owner_approvals()
    validate_owner_pcmdsd((source/'src/pcmdsd.c').read_bytes())
    validate_decoder_table((source/'src/dsd.c').read_bytes())
    for name in ('src/dsd_coeffs_112.h','src/pcmdsd_coeffs_112.h'):
        validate_am1_header(name, (source/name).read_bytes())
    for relative,want in p['src_stage_files'].items():
        path=REFERENCE/relative
        if not path.is_file() or digest(path)!=want:
            raise AssertionError('independent reference stage snapshot changed: '+relative)
    return p
