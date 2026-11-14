#!/usr/bin/env python3
"""Source-bound round03 high-rate mastering coefficient selection.

Pin exact binary64 coefficient spellings and selected table hashes against
observed/round03/tables/ROUND03_TABLES.json from the 2026-11-13 handoff.
No historical P17 generator or certificate is edited by this check.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

EXPECTED = {
    22579200: ('sdm-8-dsd512', '07f187c77d15c886d08071c8e5c4838f0bce63e8b6ef32434ef745638d62393e'),
    45158400: ('sdm-8-dsd1024', '777f361c07376cff4d869688a965e03490ba1d6cdfe473376fe75f61ef59a086'),
}

def selected(header: Path):
    text=header.read_text()
    match=re.search(r'lsx_sdm_mastering_highrate\[2\]\s*=\s*\{(.*)\};',text,re.S)
    if not match:
        raise AssertionError('missing exactly two selected high-rate tables')
    entries=re.findall(r'\{\s*\{([^{}]+)\},\s*\{([^{}]+)\},\s*8,\s*(\d+)u,\s*"([^"]+)"\s*,\s*0,\s*0,\s*0\s*\}',match.group(1))
    if len(entries)!=2:
        raise AssertionError('expected precisely two eighth-order tables')
    rows=[]
    for a,g,rate,name in entries:
        rate=int(rate)
        assert rate in EXPECTED, f'unsupported mastering rate: {rate}'
        words={'a':[x.strip() for x in a.split(',')],
               'g':[x.strip() for x in g.split(',')], 'order':8}
        assert len(words['a'])==len(words['g'])==8
        for key in ('a','g'):
            # Reject imprecise decimal rewrites and nonliteral expressions.
            for number in words[key]:
                value=float.fromhex(number)
                assert value==value and number.lower().startswith('0x')
        digest=hashlib.sha256(json.dumps(words,sort_keys=True).encode()).hexdigest()
        expected_name,expected_digest=EXPECTED[rate]
        assert (name,digest)==(expected_name,expected_digest), (
            f'DSD{rate//44100} coefficients changed: {digest}, expected {expected_digest}')
        rows.append({'native_hz':rate,'table':name,'coefficient_sha256':digest})
    assert {r['native_hz'] for r in rows}==set(EXPECTED)
    return rows


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--header',type=Path,default=Path(__file__).resolve().parents[3]/
        'src/sdm_mastering_highrate.h')
    ap.add_argument('--results',type=Path)
    args=ap.parse_args()
    rows=selected(args.header)
    if args.results:
        args.results.parent.mkdir(parents=True,exist_ok=True)
        args.results.write_text(json.dumps({'status':'PASS','source':str(args.header),
            'entries':rows},indent=2)+'\n')
    print(json.dumps({'status':'PASS','entries':rows},sort_keys=True))


if __name__=='__main__':
    main()
