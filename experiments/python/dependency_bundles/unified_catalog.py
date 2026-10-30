"""Experimental unified catalog v1: embedded range index, 64-bit or compact tables."""
from array import array
import hashlib
from pathlib import Path
import struct
import sys
import time

import binary_index
from native_loader import NativeBundleReader

MAGIC=b'GAIAUNI\0'
HEADER=struct.Struct('<8sII32s12Q')


def dense_capacity(n):
    result=1
    while result*3<n*4:result*=2
    return result


def word_width(request_compact,n,d,index_bytes):
    return 4 if request_compact and max(n,d,index_bytes)<2**32 else 8


def fnv(name):
    value=14695981039346656037
    for b in name.encode('utf-8'):value=((value^b)*1099511628211)&0xffffffffffffffff
    return value


def hash_slots(names,capacity):
    slots=array('I',[0])*capacity
    for row,name in names:
        slot=fnv(name)&(capacity-1)
        while slots[slot]:slot=(slot+1)&(capacity-1)
        slots[slot]=row+1
    return slots


def build_unified_catalog(archive,index,index_pin,source_lookup,destination,library,*,compact=True,budget=16*1048576):
    if sys.byteorder!='little' or struct.calcsize('P')!=8:raise ValueError('producer requires LE/64-bit')
    start=time.perf_counter()
    reader=NativeBundleReader(archive,index,index_sha256=index_pin,library=library,verify='local',
                             catalog_mode='mapped',catalog_path=source_lookup['path'],catalog_sha256=source_lookup['sha256'],catalog_budget=budget)
    try:
        encoded=Path(index).read_bytes();lookup=Path(source_lookup['path']).read_bytes()
        if hashlib.sha256(encoded).hexdigest()!=index_pin or hashlib.sha256(lookup).hexdigest()!=source_lookup['sha256']:
            raise ValueError('producer inputs changed')
        n,d,m,fc,dc=struct.unpack_from('<5Q',lookup,48);payload=struct.unpack_from('<Q',lookup,104)[0]
        values=array('Q');values.frombytes(lookup[payload:]);cursor=0
        def take(count):
            nonlocal cursor
            result=values[cursor:cursor+count];cursor+=count;return result
        offsets=take(n);files=take(fc);modules=take(fc);dirs=take(dc)
        rest=[take(d),take(d),take(d),take(d),take(n),take(n)]
        if cursor!=len(values):raise ValueError('producer table sizes differ')
        width=word_width(compact,n,d,len(encoded));flags=1 if width==4 else 0;mc=fc
        if flags:
            document=binary_index.decode(encoded);rows=list(document['entries'])
            fc,mc,dc=dense_capacity(n),dense_capacity(m),dense_capacity(d)
            files=hash_slots(((i,name) for i,(name,*_) in enumerate(rows)),fc)
            module_names=[]
            for i,(name,*_) in enumerate(rows):
                if not name.endswith(('.py','.pyc')):continue
                stem=name[:-4] if name.endswith('.pyc') else name[:-3]
                if stem.endswith('/__init__'):stem=stem[:-len('/__init__')]
                module_names.append((i,stem.replace('.','/')))
            if len(module_names)!=m:raise ValueError('producer module count differs')
            modules=hash_slots(module_names,mc)
            dirs=hash_slots(enumerate(document['directories']),dc)
        kind='I' if width==4 else 'Q'
        body=b''.join(array(kind,part).tobytes() for part in [offsets,files,modules,dirs,*rest])
        directory_records=bytearray();source_dir_offset=256
        for i in range(d):
            off,length=struct.unpack_from('<QQ',lookup,source_dir_offset+16*i)
            directory_records.extend(struct.pack('<II' if width==4 else '<QQ',off,length))
        index_offset=256;dir_offset=(index_offset+len(encoded)+7)&~7
        table_offset=(dir_offset+len(directory_records)+7)&~7;total=table_offset+len(body)
        header=HEADER.pack(MAGIC,1,flags,bytes.fromhex(index_pin),total,index_offset,len(encoded),n,d,m,fc,mc,dc,dir_offset,table_offset,len(body))
        output=header+b'\0'*(256-len(header))+encoded
        output+=b'\0'*(dir_offset-len(output))+directory_records
        output+=b'\0'*(table_offset-len(output))+body
        if len(output)!=total:raise ValueError('unified layout size differs')
        path=Path(destination);path.write_bytes(output)
        return dict(path=str(path.resolve()),sha256=hashlib.sha256(output).hexdigest(),bytes=len(output),
                    word_bytes=width,file_slots=fc,module_slots=mc,directory_slots=dc,
                    index_sha256=index_pin,entries=n,modules=m,format='gaia-unified-catalog',version=1,
                    producer_seconds=time.perf_counter()-start,compact_requested=compact)
    finally:reader.close()
