#!/usr/bin/env python3
import argparse, hashlib, json
from fractions import Fraction as Q
from pathlib import Path
from check_certificate import check
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'proofs/certificate.json'; cert=json.loads(p.read_text()); result=check(p); digest=result['certificate_sha256']
rows=',\n'.join('  {'+', '.join(row)+'}' for row in cert['T_hex'])
text='/* Generated from the exactly checked certificate. Do not edit. */\n'
text+='#define IQ_IDENTITY "'+digest+'"\n'
text+='static const unsigned char identity_bytes[32] = {'+', '.join('0x'+digest[j:j+2] for j in range(0,64,2))+'};\n'
text+='static const double transform[8][8] = {\n'+rows+'\n};\n'
text+='static const double feedback[8] = {'+', '.join(cert['preferred_a_hex'])+'};\n'
text+='static const double resonator[8] = {'+', '.join(cert['g_hex'])+'};\n'
text+='static const double state_cap[8] = {'+', '.join(float(v).hex() for v in result['coordinate_caps'])+'};\n'
text+='#define IQ_ENERGY_LIMIT '+float(Q(cert['energy_limit'])).hex()+'\n'
rec=cert['recovery']
text+='#define IQ_RECOVERY_ALPHA '+rec['contraction_hex']+'\n'
text+='#define IQ_RECOVERY_ENTRY_ENERGY '+rec['entry_energy_hex']+'\n'
text+='#define IQ_RECOVERY_EXIT_ENERGY '+rec['exit_energy_hex']+'\n'
text+='static const double recovery_entry_cap[8] = {'+', '.join(rec['entry_caps_hex'])+'};\n'
text+='static const double recovery_exit_cap[8] = {'+', '.join(rec['exit_caps_hex'])+'};\n'
text+='#define IQ_CERTIFIED_RECOVERY_STEPS '+str(rec['certified_max_active_steps'])+'u\n'

q=ROOT/'src/constants.h'; ap=argparse.ArgumentParser(); ap.add_argument('--check',action='store_true'); args=ap.parse_args()
if args.check:
    if not q.exists() or q.read_text()!=text: raise SystemExit('Header does not match the checked certificate')
else: q.write_text(text)
print('Header identity:',digest)
