#!/usr/bin/env python3
"""Fail closed on unapproved edits to accepted Phase 08 references (D13).

The predecessor is the content of the R3 corrective (595d401 in the delivery
history), pinned by Git tree object IDs, never the candidate source, a freshly
generated receipt, or an automatically rewritten manifest. Tree IDs depend only
on content, so they are the same in every history that carries it. Commit IDs
are not: integration re-authors commits, which changes their IDs.
Owner approval requires a separately reviewed successor reference and an
explicit predecessor/reason record; this guard intentionally cannot grant it.
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
SOURCE_PINS = ('src/dsd_coeffs.h', 'src/pcmdsd.c', 'src/pcmdsd.h',
               'src/pcmdsd_coeffs.h')
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
RECORD = ROOT / 'docs/dsd/amendments/PHASE08_OWNER_DECISIONS_2026-11-20.md'
AMENDMENT_SHA256 = '54a8a9644f2e0bf8404072c80dcbad38dc4d579b74d1ea3e921ba743d28cd38f'
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
    if digest(AMENDMENT.read_bytes()) != AMENDMENT_SHA256 or digest(RECORD.read_bytes()) != RECORD_SHA256:
        raise AssertionError('D13 owner approval record changed or missing')
    content = AMENDMENT.read_text()
    am1 = re.search(r'^## AM1\..*?(?=^## AM2\.)', content, re.M | re.S)
    am2 = re.search(r'^## AM2\..*?(?=^## AM3\.)', content, re.M | re.S)
    if not am1 or not am2:
        raise AssertionError('AM1 or AM2 owner approval absent')
    a, b = am1.group(), am2.group()
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
    return {'AM1': '1.1.2 DSD256+ decoder and three encoder front ends',
            'AM2': 'CORE-MATH D6 include and fixed-headroom expression'}


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
    return after_d6


def validate_owner_pcmdsd(raw: bytes) -> dict:
    expected = authorized_pcmdsd()
    if raw != expected:
        raise AssertionError('UNAUTHORIZED SOURCE CHANGE: src/pcmdsd.c; only AM1 and AM2 scoped changes approved')
    return {'path': 'src/pcmdsd.c', 'sha256': digest(expected),
            'authorized_owner_amendments': ['AM1', 'AM2']}


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


def run():
    approvals = owner_approvals()
    for tree in PRED_TREES.values():
        if git('cat-file', '-t', tree).decode().strip() != 'tree':
            raise AssertionError(f'pinned predecessor tree missing: {tree}')
    names = [TARGET + x for x in
             git('ls-tree', '-r', '--name-only', PRED_TREES[TARGET]).decode().splitlines()]
    assert names and any(x.endswith('accepted-reconstruction-sse2.zlib') for x in names)
    checked = []
    for name in names:
        checked.append(validate_pair(name, (ROOT / name).read_bytes()))
    # Certified encoder front end, unchanged by owner decision D3. Historical
    # profile identities and the coefficient arrays must never auto-update.
    for name in SOURCE_PINS:
        if (ROOT / name).exists() and git('cat-file', '-e', baseline_spec(name)) is not None:
            checked.append(validate_owner_pcmdsd((ROOT / name).read_bytes()) if name == 'src/pcmdsd.c'
                           else validate_pair(name, (ROOT / name).read_bytes()))
    checked.append(validate_decoder_table((ROOT / 'src/dsd.c').read_bytes()))
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
