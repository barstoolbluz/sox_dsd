"""Strict DSF header reader, channel bit windows and candidate DSF muxer.

DSF blocks are 4096 bytes per channel, interleaved by block, with least
significant bit first for the default SoX DSF output. No audio resampling.
"""
from __future__ import annotations
import os,struct
from pathlib import Path
import numpy as np
from .common import syncdir
BLOCK=4096
HEADER=92


def inspect(path):
    path=Path(path)
    with open(path,'rb') as f:h=f.read(HEADER)
    if len(h)!=HEADER or h[:4]!=b'DSD ' or h[28:32]!=b'fmt ' or h[80:84]!=b'data':raise ValueError('invalid DSF header')
    if struct.unpack_from('<Q',h,4)[0]!=28 or struct.unpack_from('<Q',h,32)[0]!=52:raise ValueError('unsupported chunk sizes')
    size=struct.unpack_from('<Q',h,12)[0];metadata=struct.unpack_from('<Q',h,20)[0]
    version,fmt,ch_type,channels,rate,bps=struct.unpack_from('<6I',h,40)
    frames=struct.unpack_from('<Q',h,64)[0];block=struct.unpack_from('<I',h,72)[0]
    reserved=struct.unpack_from('<I',h,76)[0];data_bytes=struct.unpack_from('<Q',h,84)[0]-12
    if version!=1 or fmt!=0 or channels not in range(1,7) or ch_type not in range(1,8) or bps!=1 or block!=BLOCK or reserved or rate not in (2822400,5644800):raise ValueError('unsupported DSF variant (requires default little-bit-order 4096-byte blocks)')
    expected=((frames+8*BLOCK-1)//(8*BLOCK))*BLOCK*channels
    actual=path.stat().st_size
    if frames<=0 or data_bytes!=expected or size<HEADER+expected or actual<size or metadata not in (0,) and not (HEADER+expected<=metadata<size):raise ValueError('invalid DSF frame/data extent')
    return {'rate':rate,'frames':frames,'channels':channels,'channel_type':ch_type,'payload_bytes':expected,'header':h}


def read_channel_window(path,info,channel,start,frames):
    if not (0<=channel<info['channels'] and start>=0 and frames>=0 and start+frames<=info['frames']):raise ValueError('out-of-range DSF window')
    initial=start//8; end=(start+frames+7)//8;data=bytearray()
    with open(path,'rb') as f:
        i=initial
        while i<end:
            page=i//BLOCK;offset=i%BLOCK; count=min(end-i,BLOCK-offset)
            f.seek(HEADER+page*BLOCK*info['channels']+channel*BLOCK+offset)
            value=f.read(count)
            if len(value)!=count:raise ValueError('truncated DSF channel payload')
            data.extend(value);i+=count
    unpacked=np.unpackbits(np.frombuffer(data,dtype=np.uint8),bitorder='little')
    return (unpacked[start%8:start%8+frames].astype(np.int8)*2-1)


def read_packed_window(path,start,frames):
    if start<0 or frames<0:raise ValueError('invalid bit window')
    with open(path,'rb') as f:
        f.seek(start//8)
        raw=f.read((start%8+frames+7)//8)
    if len(raw)!=(start%8+frames+7)//8:raise ValueError('truncated candidate bit file')
    u=np.unpackbits(np.frombuffer(raw,dtype=np.uint8),bitorder='little')
    return (u[start%8:start%8+frames].astype(np.int8)*2-1)


def mux_candidate(reference,bit_files,destination):
    info=inspect(reference);destination=Path(destination)
    if len(bit_files)!=info['channels']:raise ValueError('candidate channel count differs')
    expected=(info['frames']+7)//8
    for name in bit_files:
        if Path(name).stat().st_size!=expected:raise ValueError('incorrect candidate packed sample count')
    h=bytearray(info['header']);payload=info['payload_bytes']
    struct.pack_into('<Q',h,12,HEADER+payload);struct.pack_into('<Q',h,20,0);struct.pack_into('<Q',h,84,payload+12)
    with open(destination,'xb') as f:
        f.write(h)
        from contextlib import ExitStack
        with ExitStack() as stack:
            readers=[stack.enter_context(open(p,'rb')) for p in bit_files]
            for _ in range(payload//(BLOCK*len(readers))):
                for ch in readers:
                    data=ch.read(BLOCK)
                    f.write(data)
                    if len(data)<BLOCK:f.write(b'\x00'*(BLOCK-len(data)))
            for ch in readers:
                if ch.read(1):raise ValueError('extra candidate data')
        f.flush();os.fsync(f.fileno())
    if inspect(destination)['frames']!=info['frames']:raise RuntimeError('candidate DSF verification failed')
    syncdir(destination.parent)
