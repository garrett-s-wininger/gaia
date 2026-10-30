"""Producer for experimental pointer-free LE/u64 mapped lookup layout v1."""
import hashlib
from pathlib import Path
import struct
import sys
import time

import binary_index
from native_loader import NativeBundleReader

MAGIC=b'GAIACAT\0'
HEADER=struct.Struct('<8sII32s9Q')
DIRECTORY=struct.Struct('<QQ')


def capacity(n):
    result=1
    while result<2*n:result*=2
    return result


def build_mapped_catalog(archive,index,pin,destination,library,*,budget=16*1048576):
    if sys.byteorder!='little' or struct.calcsize('P')!=8:raise ValueError('producer currently requires LE/64-bit')
    begin=time.perf_counter()
    reader=NativeBundleReader(archive,index,index_sha256=pin,library=library,verify='local',catalog_mode='native',catalog_budget=budget)
    try:
        encoded=Path(index).read_bytes()
        if hashlib.sha256(encoded).hexdigest()!=pin:raise ValueError('index changed during production')
        document=binary_index.decode(encoded);count,dirs,modules,used,_,_=reader.live_counts
        # Exhaustively check every name-to-ordinal/module binding against the
        # original admitted index before certifying the derived lookup artifact.
        for i,(name,*_) in enumerate(document['entries']):
            if reader.row_id(name)!=i:raise ValueError('producer file binding differs')
            if name.endswith(('.py','.pyc')):
                stem=name[:-4] if name.endswith('.pyc') else name[:-3]
                package=stem.endswith('/__init__')
                if package:stem=stem[:-len('/__init__')]
                if reader.precomputed_modules[stem.replace('/','.')]!= (name,package):raise ValueError('producer module binding differs')
        records=bytearray();cursor=128+28*count+4*dirs
        for i,name in enumerate(document['directories']):
            length=binary_index.LENGTH.unpack_from(encoded,128+28*count+4*i)[0]
            if reader.directories[name]!=i:raise ValueError('producer directory binding differs')
            records.extend(DIRECTORY.pack(cursor,length));cursor+=length
        body=reader._ffi.live_export(reader._handle)
        expected=24*count+32*dirs+16*capacity(count)+8*capacity(dirs)
        if len(body)!=expected or used!=len(body)+16*dirs:raise ValueError('producer table layout differs')
        total=256+len(records)+len(body)
        header=HEADER.pack(MAGIC,1,0,bytes.fromhex(pin),count,dirs,modules,capacity(count),capacity(dirs),
                           total,256,256+len(records),len(body))
        output=header+b'\0'*(256-len(header))+records+body
        path=Path(destination);path.write_bytes(output)
        return dict(path=str(path.resolve()),sha256=hashlib.sha256(output).hexdigest(),bytes=len(output),
                    entries=count,modules=modules,producer_seconds=time.perf_counter()-begin,
                    format='gaia-mapped-catalog',version=1,index_sha256=pin)
    finally:reader.close()
