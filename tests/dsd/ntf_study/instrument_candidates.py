#!/usr/bin/env python3
"""Instrument a disposable source checkout with trial SDM profiles.

DO NOT run on a production checkout. Requires --source to be a COPY.
Only src/sdm.c and src/ntf_experiment_candidates.h are altered.
The output remains an experimental private P10 profile, not a writer profile.
"""
import argparse,json,re
from pathlib import Path

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--designs',type=Path,required=True)
    p.add_argument('--registry',type=Path,required=True)
    args=p.parse_args()
    src=args.source.resolve(); path=src/'src/sdm.c'
    assert (src/'test/dsd_test_p10').is_file(), 'instrument only a built, disposable checkout'
    original=path.read_text()
    if 'ntf_experiment_candidates.h' in original:raise RuntimeError('source was already instrumented')
    entries=[]; header='/* FOR THROWAWAY STUDY BUILDS ONLY. NOT PRODUCT QUALIFICATION. */\n#ifndef LSX_NTF_EXP_CANDIDATES_H\n#define LSX_NTF_EXP_CANDIDATES_H\nstatic const sdm_filter_t ntf_experimental_candidates[] = {\n'
    designs=json.loads(args.designs.read_text())
    groups=[(key, rec) for key,rec in sorted(designs['designs'].items()) if not rec['screen_rejected']]
    groups +=[(f'legacy-sdm{r["order"]}',r) for n,r in designs['references'].items() if n.startswith('sdm-')]
    for i,(key,rec) in enumerate(groups):
        n=rec['order']; v1=rec['a'];v2=rec['g']; name=f'encode.experimental.ntf.{key}.dsd512'
        assert n in range(4,8) and len(v1)==n and len(v2)==n
        aa=', '.join(v1+['0x0p+0']*(8-n)); gg=', '.join(v2+['0x0p+0']*(8-n))
        header += f'  {{ {{ {aa} }}, {{ {gg} }}, {n}, 22579200u, "ntf-{key}", 0, 0, 0 }},\n'
        entries.append({'key':key,'profile':name,'order':n,'index':i})
    header+='};\n#endif\n'
    source=original.replace('#include "sdm_p20_candidates.h"', '#include "sdm_p20_candidates.h"\n#include "ntf_experiment_candidates.h"')
    anchor='static const sdm_profile_t sdm_profiles[] = {'
    assert source.count(anchor)==1
    front,tail=source.split(anchor,1)
    suffix=tail.index('\n};')
    new_entries=''.join(f'  {{"{e["profile"]}", &ntf_experimental_candidates[{e["index"]}], 176400}},\n' for e in entries)
    source=front+anchor+tail[:suffix].rstrip().rstrip(',')+',\n'+new_entries+tail[suffix:]
    path.write_text(source)
    (src/'src/ntf_experiment_candidates.h').write_text(header)
    args.registry.write_text(json.dumps({'source':str(src),'candidates':entries},sort_keys=True,indent=2)+'\n')
    print('instrumented',len(entries),'candidates in disposable',src)
if __name__=='__main__':main()
