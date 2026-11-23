#!/usr/bin/env python3
"""Fail closed on unapproved edits to accepted Phase 08 references (D13).

The R3 predecessor is pinned by Git tree objects, independent of commit IDs.
Signed AM1, AM2, AM5 and AM6 name the full approved scope, including
1.1.2 decoder/encoder source and the sealed reference-folder membership.
Byte identities here attest approved implementations; they are not owner
approvals and cannot authorize any new content or new source deltas.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
PREDECESSOR = '595d401 (delivery history)'
PRED_TREES = {
    'tests/pcm64/qualification/reference/': '0c6e4628a1545c75f07bdecf1bb979732096875e',
    'src/': '5acbc0d8dc554ce234e3b4fe5f2b62a890f94c6c',
}
TARGET = 'tests/pcm64/qualification/reference/'
SOURCE_PINS = ('src/dsd_coeffs.h', 'src/pcmdsd.h', 'src/pcmdsd_coeffs.h')
# Current AM1 implementation identities, reviewed in Return 1. Their full
# bytes are held stable by AM6; a later change needs a further owner record.
AM1_SOURCE_BLOBS = {
    'src/dsd_decode.c': '057f70876f66b70b54441b6d7259151ccd2a0463',
    'src/dsd_stats.c': '5f287f5a1da21b2349d3b5dfc26f0b1f10556016',
}

# New AM1 coefficient identities are the unchanged Git blob objects shipped
# by main 3bba2f9a5, not identities freshly calculated from the candidate.
AM1_HEADERS = {
    'src/dsd_coeffs_112.h': 'ce7a16ded4c63383a7f45ee5fbd40e2544c1f42f',
    'src/pcmdsd_coeffs_112.h': 'efffdc263b6f917f76a70e1fb356ef518bc7b6be',
}
# Blob of the decoder table immediately before AM1. Content identities
# survive re-authoring, unlike delivery-history commit IDs.
PRE_AM1_DECODER_BLOB = '510f689377fb2a393ff8928fcac56d7f8050219e'
AMENDMENT = ROOT / 'docs/dsd/amendments/PHASE08_OWNER_AMENDMENT_1_2026-11-22.md'
AMENDMENT2 = ROOT / 'docs/dsd/amendments/PHASE08_OWNER_AMENDMENT_2_2026-11-22.md'
RECORD = ROOT / 'docs/dsd/amendments/PHASE08_OWNER_DECISIONS_2026-11-20.md'
AMENDMENT_SHA256 = '54a8a9644f2e0bf8404072c80dcbad38dc4d579b74d1ea3e921ba743d28cd38f'
AMENDMENT2_SHA256 = '65768ffd131fd3bdaf610c12f51f40408d2dfacc5c249d67b4ab8b72ab1c3a2a'
RECORD_SHA256 = '78d7338b82ead1b160b47b40a7cd614c201067b64b81fbf9a5a85850c016e158'



def git(*args: str) -> bytes:
    return subprocess.check_output(['git', '-C', str(ROOT), *args], stderr=subprocess.PIPE)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def baseline_spec(path: str) -> str:
    for prefix, tree in PRED_TREES.items():
        if path.startswith(prefix):
            return f'{tree}:{path[len(prefix):]}'
    raise AssertionError(f'no pinned predecessor tree covers {path}')


def baseline_bytes(path: str) -> bytes:
    return git('show', baseline_spec(path))


def validate_pair(path: str, raw: bytes) -> dict:
    expected = baseline_bytes(path)
    if raw != expected:
        raise AssertionError(f'UNAUTHORIZED REFERENCE CHANGE: {path}; predecessor preserved at {PREDECESSOR}')
    return {'path': path, 'sha256': digest(expected), 'size': len(expected)}


# The *separately signed* owner record controls whether each delta is allowed.
# The comparison below enforces the recorded scope byte-for-byte; it cannot
# grant new approvals, change pinned words or silently accept another edit.
def owner_approvals() -> dict:
    if (digest(AMENDMENT.read_bytes()) != AMENDMENT_SHA256 or
        digest(AMENDMENT2.read_bytes()) != AMENDMENT2_SHA256 or
        digest(RECORD.read_bytes()) != RECORD_SHA256):
        raise AssertionError('D13 owner approval record changed or missing')
    content = AMENDMENT.read_text()
    am1 = re.search(r'^## AM1\..*?(?=^## AM2\.)', content, re.M | re.S)
    am2 = re.search(r'^## AM2\..*?(?=^## AM3\.)', content, re.M | re.S)
    if not am1 or not am2:
        raise AssertionError('AM1 or AM2 owner approval absent')
    am5 = re.search(r'^## AM5\..*?(?=^## AM6\.)', AMENDMENT2.read_text(), re.M | re.S)
    am6 = re.search(r'^## AM6\..*', AMENDMENT2.read_text(), re.M | re.S)
    if not am5 or not am6:
        raise AssertionError('AM5 or AM6 owner approval absent')
    a, b, c, d = am1.group(), am2.group(), am5.group(), am6.group()
    if not all(token in a for token in (
        '3bba2f9a5', 'src/pcmdsd.c',
        '681739ced15d65b7df0dd3ee9bc5d24f7ffd1133',
        'encode.mastering.v1.dsd256', 'encode.mastering.v2.dsd512',
        'encode.mastering.v2.dsd1024', 'decoder (DSD to PCM)')):
        raise AssertionError('AM1 does not approve these decoder and encoder front-end changes')
    if not all(token in b for token in (
        'src/pcmdsd.c', 'ab3beae36d5a94efc80f8f718ebb885ea52f06c4',
        'dsd_coremath_gain.h', 'headroom expression')):
        raise AssertionError('AM2 does not authorize the D6 fixed-headroom correction')
    if not all(token in c for token in (
        '681739ced15d65b7df0dd3ee9bc5d24f7ffd1133',
        'comment-only changes in `src/pcmdsd.c`', 'not yet retested',
        'encode.mastering.v1.dsd256', 'encode.mastering.v2.dsd512',
        'encode.mastering.v2.dsd1024')):
        raise AssertionError('AM5 does not approve comment-only high-rate evidence corrections')
    if not all(token in d for token in (
        PRED_TREES[TARGET], PRED_TREES['src/'],
        *AM1_HEADERS.values(), 'src/dsd_decode.c', 'src/dsd_stats.c',
        'src/pcmdsd.c', 'src/dsd.c', 'missing fails the guard')):
        raise AssertionError('AM6 does not define the required sealed source/reference scope')
    return {'AM1': '1.1.2 high-rate decoder and three encoder front ends',
            'AM2': 'CORE-MATH D6 include and fixed-headroom expression',
            'AM5': 'high-rate evidence comments only in pcmdsd.c',
            'AM6': 'sealed reference folder, source identities and approved scope'}


def substitute(raw: bytes, before: bytes, after: bytes, label: str) -> bytes:
    if raw.count(before) != 1:
        raise AssertionError(f'{label}: approved predecessor text missing or repeated')
    return raw.replace(before, after, 1)


def authorized_pcmdsd() -> bytes:
    # Start with the R3 source at the immutable predecessor tree.
    old = baseline_bytes('src/pcmdsd.c')
    after_d6 = substitute(old,
        b'#include "dsd_resonator.h"\n',
        b'#include "dsd_resonator.h"\n#include "dsd_coremath_gain.h"\n', 'AM2 include')
    after_d6 = substitute(after_d6,
        b'pow(10.,-p->options.headroom_db/20.)',
        b'dsd_coremath_gain_from_db(-p->options.headroom_db)', 'AM2 fixed headroom')
    # The documented after-AM2 predecessor must match before AM1 is applied.
    if digest(after_d6) != digest(git('cat-file', 'blob',
                                           '681739ced15d65b7df0dd3ee9bc5d24f7ffd1133')):
        raise AssertionError('AM2 predecessor mismatch')
    edits = (
        (b'#include "pcmdsd_coeffs.h"\n',
         b'#include "pcmdsd_coeffs.h"\n#include "pcmdsd_coeffs_112.h"\n'),
        (b'  {"encode.mastering.v1.dsd256",11289600,176400,40000,80000,\n'
         b'    lsx_pcmdsd_coeff_master64_256,61,lsx_pcmdsd_guards[2],1,LSX_PCMDSD_CERTIFICATE_SHA256,0},',
         b'  /* AM1: at DSD256+ only the FIR/front-end rate and pass/stop edges\n'
         b'   * change to 1.1.2. The v1/v2 SDM modulators and guards do not change.\n'
         b'   * P10 front-end certificate authenticates only unchanged DSD64/128. */\n'
         b'  {"encode.mastering.v1.dsd256",11289600,352800,60000,100000,\n'
         b'    lsx_dsd112_encoder_master256_1024,117,lsx_pcmdsd_guards[2],1,NULL,0},'),
        (b'   * both v2 profiles use the already-certified 61-tap master64_256 bank. */',
         b'   * the changed 1.1.2 high-rate FIRs carry no historical P10 certificate. */'),
        (b'  {"encode.mastering.v2.dsd512",22579200,176400,40000,80000,\n'
         b'    lsx_pcmdsd_coeff_master64_256,61,lsx_pcmdsd_p20_guards,1,LSX_PCMDSD_CERTIFICATE_SHA256,0},',
         b'  {"encode.mastering.v2.dsd512",22579200,352800,88200,148200,\n'
         b'    lsx_dsd112_encoder_master512,81,lsx_pcmdsd_p20_guards,1,NULL,0},'),
        (b'  {"encode.mastering.v2.dsd1024",45158400,176400,40000,80000,\n'
         b'    lsx_pcmdsd_coeff_master64_256,61,lsx_pcmdsd_v2_guards,1,LSX_PCMDSD_CERTIFICATE_SHA256,0},',
         b'  {"encode.mastering.v2.dsd1024",45158400,705600,120000,200000,\n'
         b'    lsx_dsd112_encoder_master256_1024,117,lsx_pcmdsd_v2_guards,1,NULL,0},'),
    )
    for oldtext, newtext in edits:
        after_d6 = substitute(after_d6, oldtext, newtext, 'AM1 front end')
    # AM5 explicitly permits comment-only updates in this pinned file.
    # These two changes do not affect the available encoder rows/ABI.
    after_d6 = substitute(after_d6,
        b'/* qualified=1 as of 2026-10-20: the design authority recorded its P15\n'
        b' * engineering acceptance on 2026-10-19 and withdrew the outstanding\n'
        b' * formal-proof obligation as a release blocker. Coefficients, guards and\n'
        b' * certificate digests are unchanged. */',
        b'/* P15 engineering acceptance (2026-10-19) applies to the former front end.\n'
        b' * DSD64/128 retain those certified coefficients and their qualification.\n'
        b' * DSD256 now uses the 1.1.2 FIR; its old-front-end stability evidence\n'
        b' * does not qualify that combination, which has not yet been retested. */',
        'AM5 P15 evidence comment')
    after_d6 = substitute(after_d6,
        b'   * CLANS-7 recurrence, which passed training 17/17, verify 17, holdout\n'
        b'   * 36/36, cross-ISA and an uninterrupted 3,600-second nominal soak.\n',
        b'   * CLANS-7 recurrence, which passed training 17/17, verify 17, holdout\n'
        b'   * 36/36, cross-ISA and an uninterrupted 3,600-second nominal soak\n'
        b'   * with the OLD front end. Stability with the 1.1.2 FIR front end is\n'
        b'   * NOT YET RETESTED; the qualified flag stays for encoder availability.\n',
        'AM5 P21 evidence comment')
    return after_d6


def validate_owner_pcmdsd(raw: bytes) -> dict:
    expected = authorized_pcmdsd()
    if raw != expected:
        raise AssertionError('UNAUTHORIZED SOURCE CHANGE: src/pcmdsd.c; only AM1/AM2/AM5 scoped changes approved')
    return {'path': 'src/pcmdsd.c', 'sha256': digest(expected),
            'authorized_owner_amendments': ['AM1', 'AM2', 'AM5']}


def authorized_decoder_table() -> bytes:
    old = git('cat-file', 'blob', PRE_AM1_DECODER_BLOB)
    edits = (
        (b'  {11289600, 176400, LSX_DSD_PROFILE_MASTERING,  40000,  80000, 6, LSX_DSD_BANK_MASTER64_256, 2724, "decode.mastering.dsd256"},',
         b'  {11289600, 352800, LSX_DSD_PROFILE_MASTERING,  60000, 100000, 5, LSX_DSD_BANK_MASTER112_256_1024, 2244, "decode.mastering.dsd256"},'),
        (b'  /* The v1 high-rate frontends reuse the P06 banks. Mastering retains its\n'
         b'   * 176400-Hz clock; wideband scales its intermediate clock with the native\n'
         b'   * rate. P21 authorizes the associated file and transport read operations. */\n'
         b'  {22579200, 176400, LSX_DSD_PROFILE_MASTERING,  40000,  80000, 7, LSX_DSD_BANK_MASTER64_256,  5476, "decode.mastering.dsd512"},\n'
         b'  {45158400, 176400, LSX_DSD_PROFILE_MASTERING,  40000,  80000, 8, LSX_DSD_BANK_MASTER64_256, 10980, "decode.mastering.dsd1024"},',
         b'  /* AM1: 1.1.2 replacement mastering banks and clocks at DSD256+.\n'
         b'   * DSD64/128 and all wideband profiles retain their earlier coefficients. */\n'
         b'  {22579200, 352800, LSX_DSD_PROFILE_MASTERING,  88200, 148200, 6, LSX_DSD_BANK_MASTER112_512, 3300, "decode.mastering.dsd512"},\n'
         b'  {45158400, 705600, LSX_DSD_PROFILE_MASTERING, 120000, 200000, 6, LSX_DSD_BANK_MASTER112_256_1024, 4516, "decode.mastering.dsd1024"},'),
    )
    for before, after in edits:
        old = substitute(old, before, after, 'AM1 decoder table')
    return old


def validate_decoder_table(raw: bytes) -> dict:
    expected = authorized_decoder_table()
    if raw != expected:
        raise AssertionError('UNAUTHORIZED SOURCE CHANGE: src/dsd.c; AM1 decoder rows only')
    return {'path': 'src/dsd.c', 'sha256': digest(expected),
            'authorized_owner_amendments': ['AM1']}


def validate_am1_header(path: str, raw: bytes) -> dict:
    # Content-only Git blob identity; no lookup by a delivery commit ID.
    val = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
    if val != AM1_HEADERS[path]:
        raise AssertionError(f'UNAUTHORIZED SOURCE CHANGE: {path}; not main 1.1.2 filter words')
    return {'path': path, 'git_blob': val, 'sha256': digest(raw),
            'authorized_owner_amendments': ['AM1']}


def validate_am1_source(path: str, raw: bytes) -> dict:
    wanted = AM1_SOURCE_BLOBS[path]
    got = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
    if got != wanted:
        raise AssertionError(f'UNAUTHORIZED SOURCE CHANGE: {path}; differs from AM1-approved Return 1 content')
    return {'path': path, 'git_blob': got, 'sha256': digest(raw),
            'authorized_owner_amendments': ['AM1', 'AM6']}


def sealed_reference_members(names: list[str]) -> None:
    # Include untracked additions, symlinks and nested paths; a Git index-only
    # check would miss precisely the added-file case covered by AM6.
    folder = ROOT / TARGET
    if not folder.is_dir() or folder.is_symlink():
        raise AssertionError('D13 sealed reference folder is absent or replaced')
    present = {TARGET + p.relative_to(folder).as_posix()
               for p in folder.rglob('*') if not p.is_dir() or p.is_symlink()}
    if present != set(names):
        added, removed = sorted(present - set(names)), sorted(set(names) - present)
        raise AssertionError(f'UNAUTHORIZED REFERENCE MEMBERSHIP CHANGE: added={added}, missing={removed}')
    for name in names:
        file = ROOT / name
        if file.is_symlink() or not file.is_file():
            raise AssertionError(f'pinned reference file missing or symlink: {name}')


def run():
    approvals = owner_approvals()
    for tree in PRED_TREES.values():
        if git('cat-file', '-t', tree).decode().strip() != 'tree':
            raise AssertionError(f'pinned predecessor tree missing: {tree}')
    names = [TARGET + x for x in
             git('ls-tree', '-r', '--name-only', PRED_TREES[TARGET]).decode().splitlines()]
    assert names and any(x.endswith('accepted-reconstruction-sse2.zlib') for x in names)
    sealed_reference_members(names)
    checked = []
    for name in names:
        checked.append(validate_pair(name, (ROOT / name).read_bytes()))
    # Certified encoder front end, unchanged by owner decision D3. Historical
    # profile identities and the coefficient arrays must never auto-update.
    for name in SOURCE_PINS:
        if not (ROOT / name).is_file() or (ROOT / name).is_symlink():
            raise AssertionError(f'D13 pinned source missing or symlink: {name}')
        checked.append(validate_pair(name, (ROOT / name).read_bytes()))
    checked.append(validate_owner_pcmdsd((ROOT / 'src/pcmdsd.c').read_bytes()))
    checked.append(validate_decoder_table((ROOT / 'src/dsd.c').read_bytes()))
    for name in AM1_SOURCE_BLOBS:
        checked.append(validate_am1_source(name, (ROOT / name).read_bytes()))
    for path in AM1_HEADERS:
        checked.append(validate_am1_header(path, (ROOT / path).read_bytes()))
    sys.path.insert(0, str(ROOT / 'tests/pcm64/qualification'))
    from reconstruction_reference import accepted_words
    items = accepted_words()
    if len(items) != 19:
        raise AssertionError('historical predecessor has wrong accepted sample count')
    # Mutation control: flipping one byte, in memory, must cause rejection.
    victim = next(name for name in names if name.endswith('accepted-reconstruction-sse2.zlib'))
    altered = bytearray((ROOT / victim).read_bytes())
    altered[len(altered) // 2] ^= 1
    rejected = False
    try:
        validate_pair(victim, altered)
    except AssertionError:
        rejected = True
    if not rejected:
        raise AssertionError('D13 mutation check failed: guard did not reject edit')
    # Mutate outside AM1/AM2 in an otherwise approved source.
    pcmdsd = bytearray((ROOT / 'src/pcmdsd.c').read_bytes())
    pos = pcmdsd.index(b'#include <math.h>')
    pcmdsd[pos] ^= 1
    try:
        validate_owner_pcmdsd(bytes(pcmdsd))
    except AssertionError:
        pass
    else:
        raise AssertionError('D13 pcmdsd mutation check failed')
    decoder = bytearray((ROOT / 'src/dsd.c').read_bytes())
    decoder[decoder.index(b'decode.mastering.dsd256')] ^= 1
    try:
        validate_decoder_table(bytes(decoder))
    except AssertionError:
        pass
    else:
        raise AssertionError('D13 decoder table mutation check failed')
    hdr = bytearray((ROOT / 'src/dsd_coeffs_112.h').read_bytes())
    hdr[len(hdr) // 2] ^= 1
    try:
        validate_am1_header('src/dsd_coeffs_112.h', bytes(hdr))
    except AssertionError:
        pass
    else:
        raise AssertionError('D13 filter header mutation check failed')
    return {'schema':'phase08-reference-immutability/1',
            'status':'PASS_LOCKED_PREDECESSOR',
            'baseline':PREDECESSOR, 'baseline_trees':PRED_TREES,
            'owner_approvals': approvals,
            'predecessor_type':'historical v2 reconstruction; NOT unified decoder oracle',
            'accepted_v2_fixtures':len(items),
            'mutation_rejection':'PASS', 'pcmdsd_outside_D6_mutation_rejection':'PASS',
            'AM1_decoder_table_mutation_rejection':'PASS',
            'AM1_filter_header_mutation_rejection':'PASS',
            'AM6_sealed_reference_membership':'PASS',
            'AM6_decoder_and_identity_sources':'PASS',
            'unified_decoder_reference_approval':'OPEN',
            'files':checked}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--results',type=Path,required=True)
    args=ap.parse_args()
    try: result=run()
    except Exception as e: result={'status':'FAIL','error':str(e), 'unified_decoder_reference_approval':'OPEN'}
    args.results.mkdir(parents=True,exist_ok=True)
    (args.results/'immutable-reference.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(f"{result['status']}: D13 sealed predecessor; D16 unified approval OPEN")
    if result['status']=='FAIL':print(result['error'],file=sys.stderr)
    return int(result['status']=='FAIL')

if __name__=='__main__':raise SystemExit(main())
