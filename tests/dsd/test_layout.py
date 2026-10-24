#!/usr/bin/env python3
"""P04 independent known-answer channel/metadata oracle matrix.

Builds DFF CHNL/LSCO fixtures without using SoX.  Parses the serialized
output format, inspects the actual channel samples, and checks both API
ownership and loss-policy behavior.  Stores every command/exit and verdict.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import pathlib
import struct
import subprocess
import tempfile
import time
from reference import fixtures, verify

ROOT = pathlib.Path(__file__).resolve().parents[2]


def dff(ids: list[bytes], bits: tuple[bytes, ...], lsco: int | None = None,
        lsco_first: bool = False) -> bytes:
    assert len(ids) == len(bits) and all(len(x) == 4 for x in ids)
    assert len({x for x in ids}) == len(ids)
    assert len(set(map(len, bits))) == 1 and len(bits[0]) % 8 == 0
    frames = len(bits[0]); nch = len(ids)
    prop = fixtures.chunk(b'FS  ', struct.pack('>I', fixtures.DSD64))
    chnl = fixtures.chunk(b'CHNL', struct.pack('>H', nch) + b''.join(ids))
    opt = fixtures.chunk(b'LSCO', struct.pack('>H', lsco)) if lsco is not None else b''
    prop += (opt + chnl) if lsco_first else (chnl + opt)
    prop += fixtures.chunk(b'CMPR', b'DSD ' + bytes([14]) + b'not compressed')
    payload = bytes(fixtures.pack_byte(channel,i,True) for i in range(0,frames,8)
                    for channel in bits)
    return fixtures.chunk(b'FRM8', b'DSD ' +
        fixtures.chunk(b'FVER',bytes.fromhex('01050000')) +
        fixtures.chunk(b'PROP',b'SND ' + prop) +
        fixtures.chunk(b'DSD ',payload))


def dff_fields(blob: bytes):
    r = verify.decode_dff(blob)
    prop = next(c for c in r['top'] if c['tag'] == 'PROP')
    subs = verify.chunks(blob, prop['payload_start']+4, prop['payload_end'])
    fields = {c['tag']: blob[c['payload_start']:c['payload_end']] for c in subs}
    ids = [fields['CHNL'][2+i*4:6+i*4] for i in range(r['channels'])]
    lsco = struct.unpack('>H',fields['LSCO'])[0] if 'LSCO' in fields else None
    return r, ids, lsco


def wav_fields(blob: bytes):
    assert blob[:4] in (b'RIFF',b'RIFX') and blob[8:12]==b'WAVE'
    assert blob[:4] == b'RIFF'  # test contract is little-endian
    off=12; fmt=None; data=None
    while off+8<=len(blob):
        name=blob[off:off+4]
        n=struct.unpack_from('<I',blob,off+4)[0]
        assert off+8+n<=len(blob), 'WAV chunk extent'
        part=blob[off+8:off+8+n]
        if name==b'fmt ':fmt=part
        if name==b'data':data=part
        off += 8+n+(n&1)
    assert fmt is not None and data is not None
    tag,nch,rate,_,_,bps = struct.unpack_from('<HHIIHH',fmt)
    mask=None; native_tag=tag
    if tag==0xfffe:
        cb,valid,mask,low=struct.unpack_from('<HHIH',fmt,16)
        assert cb==22 and valid<=bps
        native_tag=low
    return dict(tag=tag,native_tag=native_tag,channels=nch,rate=rate,
                bits=bps,mask=mask,data=data)


def wave_signs(wav: dict, limit: int) -> list[bytes]:
    fmt = ('f' if wav['native_tag']==3 and wav['bits']==32 else
           'h' if wav['native_tag']==1 and wav['bits']==16 else None)
    assert fmt is not None, f'unsupported test output encoding {wav}'
    size = 4 if fmt=='f' else 2
    count = min(len(wav['data'])//(size*wav['channels']),limit)
    out=[bytearray() for _ in range(wav['channels'])]
    for row in range(count):
        for ch in range(wav['channels']):
            pos=(row*wav['channels']+ch)*size
            val=struct.unpack_from('<'+fmt,wav['data'],pos)[0]
            out[ch].append(int(val>0))
    return [bytes(x) for x in out]


def pcm_wav(channels: int, mask: int | None = None, frames: int = 96) -> bytes:
    """Independently constructed 44.1 kHz PCM16, tag 1 or extensible.

    None means no channel-mask field, unlike an extensible header with a zero
    mask.  Each channel has a distinct sample sequence.
    """
    assert channels in (1, 2, 4)
    samples = b''.join(struct.pack('<h', ((i * (ch + 2) * 17) % 2401) - 1200)
                       for i in range(frames) for ch in range(channels))
    fmt = struct.pack('<HHIIHH', 1 if mask is None else 0xfffe,
                      channels, 44100, 44100 * channels * 2, channels * 2, 16)
    if mask is not None:
        subtype_pcm = struct.pack('<IHH8s', 1, 0, 0x10,
                                  bytes.fromhex('800000aa00389b71'))
        fmt += struct.pack('<HHI', 22, 16, mask) + subtype_pcm
    body = (b'WAVE' + b'fmt ' + struct.pack('<I', len(fmt)) + fmt +
            b'data' + struct.pack('<I', len(samples)) + samples)
    return b'RIFF' + struct.pack('<I', len(body)) + body


class Runner:
    def __init__(self,args):
        self.args=args
        self.observations=[]
        self.cases=[]

    def call(self,*argv):
        start=time.monotonic()
        p=subprocess.run([str(x) for x in argv],stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                         timeout=60,cwd=ROOT)
        obs=dict(command=[str(x) for x in argv],exit=p.returncode,
                 stdout=p.stdout.decode(errors='replace'),
                 stderr=p.stderr.decode(errors='replace'),
                 duration_s=time.monotonic()-start)
        self.observations.append(obs)
        return obs

    def check(self,name,fn):
        try:
            details=fn()
            self.cases.append(dict(name=name,status='pass',details=details))
            print('PASS',name)
        except Exception as exc:
            self.cases.append(dict(name=name,status='fail',error=repr(exc)))
            print('FAIL',name,repr(exc))

    def must(self,argv):
        result=self.call(*argv)
        assert result['exit']==0, result
        return result

    def suite(self):
        td=self.args.results
        td.mkdir(parents=True,exist_ok=True)
        # Independently generated P04 fixtures are test outputs, not source.
        # Keep them in the caller-supplied writable results tree so VPATH
        # and immutable/Nix-style source directories are supported.
        fixture_dir=td/'fixtures/p04'
        fixture_dir.mkdir(parents=True,exist_ok=True)
        v=fixtures.bits(128,4)
        v5=fixtures.bits(128,5)
        v6=fixtures.bits(128,6)
        # Assign each channel a distinct chronology.  The original DFF order
        # is deliberately not FL, FR mask order.
        cases = {
            'swap_lsco': dff([b'MRGT',b'MLFT',b'C   ',b'LFE '],v,lsco=4,lsco_first=True),
            'context': dff([b'A-00',b'B-01',b'C-02',b'D-03'],v,lsco=65535),
            'ambiguous': dff([b'MLFT',b'MRGT',b'LS  ',b'RS  '],v),
            'type5_standard': dff([b'MLFT',b'MRGT',b'C   ',b'LFE '],v),
            'stereo_lsco0': dff([b'SLFT',b'SRGT'],fixtures.bits(128,2),lsco=0),
            'five_lsco3': dff([b'MLFT',b'MRGT',b'C   ',b'LS  ',b'RS  '],v5,lsco=3),
            'six_lsco4': dff([b'MLFT',b'MRGT',b'C   ',b'LFE ',b'LS  ',b'RS  '],v6,lsco=4),
        }
        self.inputs={}
        for name,payload in cases.items():
            f=fixture_dir/('p04_'+name+'.dff')
            f.write_bytes(payload)
            self.inputs[name]=f
        manifest={k:dict(path=str(self.inputs[k].relative_to(td)),
                         sha256=hashlib.sha256(data).hexdigest(),
                         truth='hand-constructed bytes with distinct channel sequences')
                  for k,data in cases.items()}
        pcm_inputs={}
        for name,channels,mask in (
            ('mono_unmasked',1,None), ('stereo_unmasked',2,None),
            ('quad_unmasked',4,None), ('stereo_masked',2,0x3),
            ('stereo_side_masked',2,0x600),
            ('stereo_unsupported_mask',2,0x800)):
            payload=pcm_wav(channels,mask)
            path=fixture_dir/('p04_'+name+'.wav')
            path.write_bytes(payload)
            pcm_inputs[name]=path
            manifest[name]=dict(path=str(path.relative_to(td)),
                sha256=hashlib.sha256(payload).hexdigest(),
                truth='independent RIFF/PCM16 fixture, explicit mask only when named')

        self.check('public_layout_ownership_type4_type5_and_mappings',lambda:
            self.must([self.args.unit,'unit']))

        def clone(name):
            with tempfile.TemporaryDirectory() as tmp:
                output=pathlib.Path(tmp)/'copy.dff'
                self.must([self.args.unit,'clone',self.inputs[name],output])
                original, a, lsco=dff_fields(self.inputs[name].read_bytes())
                actual, b, got=dff_fields(output.read_bytes())
                assert b==a and got==lsco, (a,b,lsco,got)
                assert actual['timeline']==original['timeline']
                return dict(ids=[x.hex() for x in a],lsco=lsco,
                            chronological_bits_sha256=actual['chronological_bits_sha256'])
        for name in ('swap_lsco','context','ambiguous','type5_standard',
                     'stereo_lsco0','five_lsco3','six_lsco4'):
            self.check('copy_owned_original_CHNL_LSCO_'+name,lambda name=name:clone(name))

        def clone_dsf(input_name,expected_type):
            with tempfile.TemporaryDirectory() as tmp:
                source=ROOT/'tests/dsd/fixtures'/input_name
                dest=pathlib.Path(tmp)/'copy.dsf'
                self.must([self.args.unit,'clone',source,dest])
                a=verify.decode_dsf(source.read_bytes()); b=verify.decode_dsf(dest.read_bytes())
                assert b['channel_type']==expected_type and a['timeline']==b['timeline']
                return dict(type=b['channel_type'],bits_hash=b['chronological_bits_sha256'])
        self.check('library_clone_dsf_type4',lambda:clone_dsf('type4_quad_96.dsf',4))
        self.check('library_clone_dsf_type5',lambda:clone_dsf('type5_quad_96.dsf',5))
        self.check('library_clone_dsf_msb_bps8',lambda:clone_dsf('msb_stereo_96.dsf',2))

        def inspect(path):
            result=self.must([self.args.unit,'inspect',path])
            return json.loads(result['stdout'])

        def inspect_dsf():
            a=inspect(ROOT/'tests/dsd/fixtures/type4_quad_96.dsf')
            b=inspect(ROOT/'tests/dsd/fixtures/type5_quad_96.dsf')
            c=inspect(ROOT/'tests/dsd/fixtures/msb_stereo_96.dsf')
            assert a['dsf_type']==4 and b['dsf_type']==5
            assert [x['role'] for x in a['channels']]==[2,3,6,7],a
            assert [x['role'] for x in b['channels']]==[2,3,4,5],b
            assert c['bit_order']==8 and c['dsf_type']==2,c
            return dict(type4=a,type5=b,msb=c)
        self.check('stream_info_original_dsf_type_bit_order_and_roles',inspect_dsf)

        def inspect_wsd():
            original=bytearray(fixtures.make_wsd(fixtures.bits(32,2)))
            struct.pack_into('>I',original,48,0x11223344)
            path=fixture_dir/'p04_opaque_assignment.wsd'
            path.write_bytes(original)
            manifest['opaque_assignment'] = dict(path=str(path.relative_to(td)),
                sha256=hashlib.sha256(original).hexdigest(),truth='hand-constructed WSD ch_asn')
            a=inspect(path)
            assert a['container']==3 and a['wsd_present']==1 and a['wsd_assignment']==0x11223344,a
            assert [x['role'] for x in a['channels']]==[0,0],a
            return a
        self.check('wsd_ch_asn_opaque_provenance_no_speaker_guess',inspect_wsd)

        def inspect_lsco():
            six=inspect(self.inputs['six_lsco4']); five=inspect(self.inputs['five_lsco3'])
            two=inspect(self.inputs['stereo_lsco0'])
            for obj,value,num in ((six,4,6),(five,3,5),(two,0,2)):
                assert obj['lsco_present']==1 and obj['lsco']==value,len(obj['channels'])
                assert len(obj['channels'])==num
            swap=inspect(self.inputs['swap_lsco'])
            assert swap['lsco']==4 and [x['id'] for x in swap['channels']]==[
                b'MRGT'.hex(),b'MLFT'.hex(),b'C   '.hex(),b'LFE '.hex()]
            return dict(stereo=two,five=five,six=six,inconsistent=swap)
        self.check('LSCO_known_consistent_and_inconsistent_keeps_explicit_CHNL',inspect_lsco)


        def into_dsf(name,explicit=False,expected=5):
            with tempfile.TemporaryDirectory() as tmp:
                dest=pathlib.Path(tmp)/'out.dsf'
                args=[self.args.sox,'-D',self.inputs[name]]
                if explicit:args+=['--dsd-layout','FL,FR,FC,LFE']
                args += [dest]
                r=self.call(*args)
                if not explicit and name=='context':
                    assert r['exit']!=0 and not dest.exists(),r
                    assert 'DSF cannot encode' in r['stderr'],r
                    return {'reject':True}
                assert r['exit']==0,r
                actual=verify.decode_dsf(dest.read_bytes())
                original=dff_fields(self.inputs[name].read_bytes())[0]
                assert actual['channel_type']==expected and actual['timeline']==original['timeline']
                return dict(dsf_type=actual['channel_type'],bits=actual['chronological_bits_sha256'])
        self.check('dff_standard_to_native_dsf5',lambda:into_dsf('type5_standard'))
        self.check('dff_context_to_dsf_unrepresentable_rejected',lambda:into_dsf('context'))
        self.check('dff_context_explicit_assignment_native_dsf5',lambda:into_dsf('context',True))

        def dsf_to_dff():
            with tempfile.TemporaryDirectory() as tmp:
                source=ROOT/'tests/dsd/fixtures/type5_quad_96.dsf'
                dest=pathlib.Path(tmp)/'out.dff'
                self.must([self.args.sox,'-D',source,dest])
                a=verify.decode_dsf(source.read_bytes())
                b,ids,lsco=dff_fields(dest.read_bytes())
                assert ids==[b'MLFT',b'MRGT',b'C   ',b'LFE '] and lsco is None
                assert b['frames']%8==0 and b['timeline']==a['timeline']
                return dict(ids=[x.decode() for x in ids],bits_hash=b['chronological_bits_sha256'])
        self.check('dsf_to_dff_standard_IDs_and_bit_sequences',dsf_to_dff)

        def wav(name,warn=False,explicit=False,reverse=False,float_output=True):
            with tempfile.TemporaryDirectory() as tmp:
                source=self.inputs[name]
                dest=pathlib.Path(tmp)/'out.wav'
                args=[self.args.sox,'-D',source]
                if warn:args+=['--dsd-layout-loss','warn']
                if explicit:args+=['--dsd-layout','FL,FR,SL,SR']
                args+=['-e','floating-point' if float_output else 'signed-integer',
                       '-b','32' if float_output else '16',dest]
                if reverse:args+=['remix','2','1','3','4']
                result=self.call(*args)
                if name=='ambiguous' and not (warn or explicit):
                    assert result['exit']!=0 and not dest.exists(),result
                    return {'reject':True}
                assert result['exit']==0,result
                w=wav_fields(dest.read_bytes())
                expected_mask = 0 if warn and name=='ambiguous' and not explicit else (
                    0x603 if explicit else 0xf)
                assert (w['channels'],w['tag'],w['mask'])==(4,0xfffe,expected_mask),w
                original=dff_fields(source.read_bytes())[0]['timeline']
                indices=(1,0,2,3) if name=='swap_lsco' or reverse else (0,1,2,3)
                # For explicit order, original channels are already FL FR SL SR.
                if explicit:indices=(0,1,2,3)
                if warn and name=='ambiguous':indices=(0,1,2,3)
                if reverse: indices=(0,1,2,3) if name=='type5_standard' else (1,0,2,3)
                actual=wave_signs(w,128)
                assert actual == [original[i] for i in indices],dict(actual=actual,expected=indices)
                assert (w['native_tag'],w['bits'])==(3,32) if float_output else (w['native_tag'],w['bits'])==(1,16)
                return dict(mask=w['mask'],order=indices,bit_sequences_match=True,
                            bytes=hashlib.sha256(w['data']).hexdigest())
        self.check('wav_float_mask_order_with_explicit_input_swap',lambda:wav('swap_lsco'))
        self.check('wav_pcm16_mask_order_with_explicit_input_swap',lambda:wav('swap_lsco',float_output=False))
        self.check('wav_ambiguous_side_vs_back_reject',lambda:wav('ambiguous'))
        self.check('wav_ambiguous_side_vs_back_unspecified_mask_override',lambda:wav('ambiguous',warn=True))
        self.check('wav_ambiguous_explicit_side_assignment',lambda:wav('ambiguous',explicit=True))
        self.check('wav_remix_and_mask_order_compose_to_canonical_samples',lambda:wav('type5_standard',reverse=True))

        def wav_input_roles():
            with tempfile.TemporaryDirectory() as tmp:
                wavpath=pathlib.Path(tmp)/'source.wav'
                dsfpath=pathlib.Path(tmp)/'out.dsf'
                self.must([self.args.sox,'-D',self.inputs['type5_standard'],
                           '-e','floating-point','-b','32',wavpath])
                meta=inspect(wavpath)
                assert [c['role'] for c in meta['channels']]==[2,3,4,5],meta
                self.must([self.args.sox,'-D',wavpath,dsfpath])
                dsf=verify.decode_dsf(dsfpath.read_bytes())
                assert dsf['channel_type']==5,dsf
                return dict(wav_roles=[2,3,4,5],native_dsf_type=5)
        self.check('WAV_extensible_FC_maps_to_FC_and_DSF_Type5',wav_input_roles)

        def identity_channels_native(name,channels,expected_type):
            source=ROOT/'tests/dsd/fixtures'/name
            with tempfile.TemporaryDirectory() as tmp:
                a=pathlib.Path(tmp)/'baseline.dsf'
                b=pathlib.Path(tmp)/'channels.dsf'
                self.must([self.args.sox,'-D',source,a])
                self.must([self.args.sox,'-D',source,b,'channels',str(channels)])
                original=verify.decode_dsf(source.read_bytes())
                baseline=verify.decode_dsf(a.read_bytes())
                actual=verify.decode_dsf(b.read_bytes())
                assert original['channel_type']==baseline['channel_type']==actual['channel_type']==expected_type
                assert original['timeline']==baseline['timeline']==actual['timeline']
                return dict(dsf_type=expected_type,channels=channels,
                            bits_hash=actual['chronological_bits_sha256'])
        for source,nch,ctype in (('mono_96.dsf',1,1),('stereo_96.dsf',2,2),
                                 ('type4_quad_96.dsf',4,4),('type5_quad_96.dsf',4,5)):
            self.check('channels_noop_native_'+source,lambda s=source,n=nch,t=ctype:
                identity_channels_native(s,n,t))

        def identity_channels_dff(name,nch):
            with tempfile.TemporaryDirectory() as tmp:
                dest=pathlib.Path(tmp)/'out.dff'
                self.must([self.args.sox,'-D',self.inputs[name],dest,'channels',str(nch)])
                before,ids,lsco=dff_fields(self.inputs[name].read_bytes())
                after,output_ids,output_lsco=dff_fields(dest.read_bytes())
                assert (output_ids,output_lsco)==(ids,lsco)
                assert after['timeline']==before['timeline']
                return dict(ids=[x.decode() for x in output_ids],lsco=lsco,
                            bits_hash=after['chronological_bits_sha256'])
        self.check('channels_noop_DFF_stereo_CHNL_LSCO',lambda:
            identity_channels_dff('stereo_lsco0',2))
        self.check('channels_noop_DFF_quad_CHNL_LSCO',lambda:
            identity_channels_dff('swap_lsco',4))

        def actual_channels_change_invalidates(source_name,output_channels):
            with tempfile.TemporaryDirectory() as tmp:
                source=self.inputs[source_name]
                dff_dest=pathlib.Path(tmp)/'changed.dff'
                dsf_dest=pathlib.Path(tmp)/'changed.dsf'
                self.must([self.args.sox,'-D',source,dff_dest,
                           'channels',str(output_channels)])
                result,ids,_=dff_fields(dff_dest.read_bytes())
                assert result['channels']==output_channels
                assert ids==[f'C{i:03d}'.encode() for i in range(output_channels)],ids
                rejected=self.call(self.args.sox,'-D',source,dsf_dest,
                                   'channels',str(output_channels))
                assert rejected['exit']!=0 and not dsf_dest.exists(),rejected
                return dict(channels=output_channels,unnamed_ids=[x.decode() for x in ids],
                            cannot_invent_DSF_type=True)
        self.check('channels_reduction_clears_DFF_roles',lambda:
            actual_channels_change_invalidates('type5_standard',2))
        self.check('channels_expansion_clears_DFF_roles',lambda:
            actual_channels_change_invalidates('stereo_lsco0',4))

        def identity_channels_wav():
            with tempfile.TemporaryDirectory() as tmp:
                source=ROOT/'tests/dsd/fixtures/stereo_96.dsf'
                baseline=pathlib.Path(tmp)/'baseline.wav'
                noop=pathlib.Path(tmp)/'noop.wav'
                for out,fx in ((baseline,[]),(noop,['channels','2'])):
                    self.must([self.args.sox,'-D',source,'-e','signed-integer',
                               '-b','16',out,*fx])
                a=wav_fields(baseline.read_bytes());b=wav_fields(noop.read_bytes())
                assert a['tag']==b['tag']==0xfffe
                assert a['mask']==b['mask']==3
                assert a['data']==b['data']
                return dict(mask=3,samples_identical=True,
                            data_hash=hashlib.sha256(a['data']).hexdigest())
        self.check('channels_noop_stereo_WAV_mask_and_samples',identity_channels_wav)

        def pcm_into_dsd(name,nch,expected_type,expected_ids):
            source=pcm_inputs[name]
            with tempfile.TemporaryDirectory() as tmp:
                output={}
                for extension in ('dsf','dff'):
                    dst=pathlib.Path(tmp)/('auto.'+extension)
                    explicit=pathlib.Path(tmp)/('explicit.'+extension)
                    roles='MONO' if nch==1 else 'FL,FR'
                    self.must([self.args.sox,'-D',source,'-r',str(fixtures.DSD64),dst])
                    self.must([self.args.sox,'-D',source,'--dsd-layout',roles,
                               '-r',str(fixtures.DSD64),explicit])
                    if extension=='dsf':
                        auto=verify.decode_dsf(dst.read_bytes())
                        named=verify.decode_dsf(explicit.read_bytes())
                        assert auto['channel_type']==named['channel_type']==expected_type
                    else:
                        auto,ids,_=dff_fields(dst.read_bytes())
                        named,explicit_ids,_=dff_fields(explicit.read_bytes())
                        assert ids==explicit_ids==expected_ids,ids
                    assert auto['frames']==named['frames']==96*64
                    assert auto['timeline']==named['timeline']
                    output[extension]=dict(frames=auto['frames'],
                        bits_hash=auto['chronological_bits_sha256'])
                return output
        self.check('conventional_PCM_mono_WAV_to_DSF_and_DFF',lambda:
            pcm_into_dsd('mono_unmasked',1,1,[b'C   ']))
        self.check('conventional_PCM_stereo_WAV_to_DSF_and_DFF',lambda:
            pcm_into_dsd('stereo_unmasked',2,2,[b'SLFT',b'SRGT']))

        def explicit_wav_assignment():
            with tempfile.TemporaryDirectory() as tmp:
                src=pcm_inputs['stereo_unmasked']
                dest=pathlib.Path(tmp)/'explicit.dff'
                self.must([self.args.sox,'-D',src,'--dsd-layout','FR,FL',
                           '-r',str(fixtures.DSD64),dest])
                _,ids,_=dff_fields(dest.read_bytes())
                assert ids==[b'SRGT',b'SLFT'],ids
                return dict(IDs=[x.decode() for x in ids])
        self.check('PCM_explicit_assignment_overrides_conventional_stereo',explicit_wav_assignment)

        def nonconventional_wav_mask():
            with tempfile.TemporaryDirectory() as tmp:
                side=pcm_inputs['stereo_side_masked']
                dff_out=pathlib.Path(tmp)/'side.dff'
                dsf_out=pathlib.Path(tmp)/'side.dsf'
                self.must([self.args.sox,'-D',side,'-r',str(fixtures.DSD64),dff_out])
                _,ids,_=dff_fields(dff_out.read_bytes())
                assert ids==[b'LS  ',b'RS  '],ids
                rejected=self.call(self.args.sox,'-D',side,'-r',str(fixtures.DSD64),dsf_out)
                assert rejected['exit']!=0 and not dsf_out.exists(),rejected
                return dict(IDs=[x.decode() for x in ids],DSF_rejected=True)
        self.check('WAV_extensible_side_roles_not_replaced_with_stereo',nonconventional_wav_mask)

        def unknown_wav_mask_rejected():
            with tempfile.TemporaryDirectory() as tmp:
                source=pcm_inputs['stereo_unsupported_mask']
                dest=pathlib.Path(tmp)/'out.dsf'
                r=self.call(self.args.sox,'-D',source,'-r',str(fixtures.DSD64),dest)
                assert r['exit']!=0 and not dest.exists(),r
                return dict(explicit_unrepresentable_mask_not_guessed=True)
        self.check('WAV_explicit_unsupported_mask_not_guessed',unknown_wav_mask_rejected)

        def ambiguous_multichannel_pcm():
            with tempfile.TemporaryDirectory() as tmp:
                source=pcm_inputs['quad_unmasked']
                dest=pathlib.Path(tmp)/'out.dsf'
                r=self.call(self.args.sox,'-D',source,'-r',str(fixtures.DSD64),dest)
                assert r['exit']!=0 and not dest.exists(),r
                return dict(unknown_quad_not_guessed=True)
        self.check('unknown_four_channel_PCM_requires_assignment_for_DSF',ambiguous_multichannel_pcm)

        def plain_pcm_unchanged():
            with tempfile.TemporaryDirectory() as tmp:
                src=pcm_inputs['stereo_unmasked']
                dst=pathlib.Path(tmp)/'out.wav'
                self.must([self.args.sox,'-D',src,'-e','signed-integer','-b','16',dst])
                a=wav_fields(src.read_bytes());b=wav_fields(dst.read_bytes())
                assert a['data']==b['data']
                assert a['mask'] is None and b['mask'] is None
                return dict(plain_PCM_sample_data_unchanged=True,no_mask_added=True)
        self.check('ordinary_PCM_to_PCM_no_mask_or_sample_change',plain_pcm_unchanged)

        def pcm_compat():
            with tempfile.TemporaryDirectory() as tmp:
                wavpath=pathlib.Path(tmp)/'source.wav'
                rawpath=pathlib.Path(tmp)/'ordinary.raw'
                self.must([self.args.sox,'-D',self.inputs['type5_standard'],
                           '-e','signed-integer','-b','16',wavpath])
                self.must([self.args.sox,'-D',wavpath,'-e','signed-integer','-b','16',rawpath])
                assert rawpath.stat().st_size>0
                return dict(PCM_to_raw_still_allowed=True,bytes=rawpath.stat().st_size)
        self.check('PCM_WAV_channel_mask_does_not_change_ordinary_PCM_policy',pcm_compat)

        def dff_remix(mix=False):
            with tempfile.TemporaryDirectory() as tmp:
                source=self.inputs['type5_standard']
                dest=pathlib.Path(tmp)/'out.dff'
                eff=['remix','1,2'] if mix else ['remix','2','1','3','4']
                r=self.must([self.args.sox,'-D',source,dest,*eff])
                original=dff_fields(source.read_bytes())[0]['timeline']
                output,ids,lsco=dff_fields(dest.read_bytes())
                if mix:
                    assert ids==[b'C000'] and output['channels']==1,ids
                    return dict(ids=[x.decode() for x in ids],invalidated=True)
                assert ids==[b'MRGT',b'MLFT',b'C   ',b'LFE '],ids
                assert output['timeline']==[original[i] for i in (1,0,2,3)]
                return dict(ids=[x.decode() for x in ids],bits_match=True)
        self.check('remix_pure_permutation_retains_DFF_channel_IDs',lambda:dff_remix(False))
        self.check('remix_mixing_invalidates_original_channel_IDs',lambda:dff_remix(True))

        def loss_policy():
            with tempfile.TemporaryDirectory() as tmp:
                source=self.inputs['type5_standard']
                dest=pathlib.Path(tmp)/'out.raw'
                r=self.call(self.args.sox,'-D',source,'-e','signed-integer','-b','16',dest)
                assert r['exit']!=0 and not dest.exists(),r
                r=self.must([self.args.sox,'-D',source,'--dsd-layout-loss','warn',
                              '-e','signed-integer','-b','16',dest])
                assert dest.exists() and 'discarding DSD channel layout' in r['stderr'],r
                return dict(reject_before_create=True,warn_visible=True)
        self.check('metadata_loss_default_reject_explicit_warn',loss_policy)

        def no_false_angle():
            with tempfile.TemporaryDirectory() as tmp:
                source=self.inputs['ambiguous']
                dest=pathlib.Path(tmp)/'out.dsf'
                r=self.call(self.args.sox,'-D',source,dest)
                assert r['exit']!=0 and not dest.exists(),r
                return dict(ambiguous_surround_not_mislabeled_as_dsf_back=True)
        self.check('DSDIFF_surround_ambiguous_DSF_rejected',no_false_angle)

        (fixture_dir/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
        count_pass=sum(c['status']=='pass' for c in self.cases)
        result=dict(phase='P04',counts=dict(pass_=count_pass,fail=len(self.cases)-count_pass),
                    cases=self.cases,commands=self.observations,fixtures=manifest)
        (td/'layout.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
        print(json.dumps(result['counts'],sort_keys=True))
        return 0 if count_pass==len(self.cases) else 1


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--sox',type=pathlib.Path,default=ROOT/'src/sox')
    ap.add_argument('--unit',type=pathlib.Path,default=ROOT/'test/dsd_test_layout')
    ap.add_argument('--results',type=pathlib.Path,default=ROOT/'tests/dsd/results/P04/layout')
    args=ap.parse_args()
    return Runner(args).suite()


if __name__=='__main__':
    raise SystemExit(main())
