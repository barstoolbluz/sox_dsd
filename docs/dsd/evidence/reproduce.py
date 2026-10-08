#!/usr/bin/env python3
"""Reproduce only the observations used by the design, against an existing build."""
import argparse,json,os,pathlib,struct,subprocess,tempfile
p=argparse.ArgumentParser();p.add_argument('--sox',required=True);p.add_argument('--probe',required=True);p.add_argument('--out',required=True);a=p.parse_args()
out=pathlib.Path(a.out);out.mkdir(parents=True,exist_ok=True)
def dsf(path,frames=96,c=2,msb=False,ctype=None):
    bits=[[(i*3+j*5+(i//7))%11<5 for i in range(frames)]for j in range(c)]
    block=bytearray(4096*c)
    for j,ch in enumerate(bits):
        for i,b in enumerate(ch):block[j*4096+i//8]|=int(b)<<(7-i%8 if msb else i%8)
    typ=ctype if ctype is not None else c+(c>4)
    h=b'DSD '+struct.pack('<QQQ',28,92+len(block),0)+b'fmt '+struct.pack('<QIIIIIIQII',52,1,0,typ,c,2822400,8 if msb else 1,frames,4096,0)+b'data'+struct.pack('<Q',12+len(block))
    path.write_bytes(h+block);return bits
def ck(tag,data):return tag+struct.pack('>Q',len(data))+data+b'\0'*(len(data)&1)
def dff(path,frames=16,c=1,trailing=False):
    data=bytes([0x69,0x96]*((frames*c//8+1)//2))[:frames*c//8]
    prop=b'SND '+ck(b'FS  ',struct.pack('>I',2822400))+ck(b'CHNL',struct.pack('>H',c)+b''.join(f'C{i:03d}'.encode()for i in range(c)))+ck(b'CMPR',b'DSD '+bytes([14])+b'not compressed')
    children=ck(b'FVER',bytes.fromhex('01050000'))+ck(b'PROP',prop)+ck(b'DSD ',data)
    if trailing:children+=ck(b'MANF',b'TEST'+b'\xAA'*20)
    path.write_bytes(ck(b'FRM8',b'DSD '+children))
def run(cmd,env=None):
    r=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,text=True)
    return {'exit':r.returncode,'stdout':r.stdout.strip(),'stderr':r.stderr.strip()}
def probe(path,initial=0,offset=0,cap=4096,seek=0,fix=0):
    r=run([a.probe,'read',str(path),str(initial),str(offset),str(cap),str(seek),str(fix)])
    try:r['data']=json.loads(r.pop('stdout'))
    except ValueError:pass
    return r
res={}
with tempfile.TemporaryDirectory() as td:
    d=pathlib.Path(td); mono=d/'mono.dsf'; stereo=d/'stereo.dsf';dsf(mono,96,1);dsf(stereo,96,2)
    res['dsf_small_read_1']=probe(mono,cap=1)
    res['dsf_rewind']=probe(mono,8,0,4096,1)
    res['dsf_rewind_core_position_corrected']=probe(mono,8,0,4096,1,1)
    res['dsf_stereo_seek_8_frames_public_offset16']=probe(stereo,0,16,4096,1,1)
    msb=d/'msb.dsf';dsf(msb,96,2,True);res['dsf_msb']=probe(msb)
    tiny=d/'tiny.dff';dff(tiny,8);res['dff_one_cluster_read']=probe(tiny)
    trail=d/'trail.dff';dff(trail,128,1,True)
    res['dff_trailing_chunk_seek']=probe(trail,0,8,128,1)
    res['dff_trailing_chunk_seek_core_corrected']=probe(trail,0,8,128,1,1)
    for c in (1,4,100):
        for frames in (8,9,16):
            f=d/f'w{c}_{frames}.dff';env=os.environ.copy();env['MALLOC_PERTURB_']='85'
            rr=run([a.probe,'write',str(f),str(c),str(frames)],env)
            data=f.read_bytes();loc=data.rfind(b'DSD ')
            declared=struct.unpack_from('>Q',data,loc+4)[0]
            res[f'dff_writer_{c}ch_{frames}bits']={'run':rr,'physical_length':len(data),'frm8_size':struct.unpack_from('>Q',data,4)[0],'dsd_declared':declared,'dsd_physical_tail':len(data)-loc-12,'payload_first_32_hex':data[loc+12:loc+44].hex()}
    typ5=d/'type5.dsf';dsf(typ5,96,4,ctype=5); typout=d/'typeout.dsf'
    rr=run([a.sox,'-D',str(typ5),str(typout)])
    res['dsf_type5_roundtrip']={'run':rr,'output_type':struct.unpack_from('<I',typout.read_bytes(),48)[0]}
    wav=d/'r.wav';rr=run([a.sox,'-n','-r','44100','-b','32',str(wav),'synth','0.01','sine','1000'])
    res['wav_rewind']=probe(wav,8,0,4096,1)
    res['wav_rewind_core_position_corrected']=probe(wav,8,0,4096,1,1)
    for rate in (352800,705600):
        f=d/f'pcm{rate}.wav';res[f'pcm_output_{rate}']=run([a.sox,'-D',str(mono),'-r',str(rate),'-e','floating-point','-b','64',str(f),'rate','-v'])
(out/'reproductions.json').write_text(json.dumps(res,indent=2)+'\n')
print(json.dumps(res,indent=2))
