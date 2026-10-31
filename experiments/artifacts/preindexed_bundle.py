"""Producer-portable byte index and equivalent two-artifact local admission."""
import hashlib
import json
import mmap
import os
from pathlib import Path
import time

import compact_python as compact
import generic_lock as generic
import cache_store as cache
import pipeline_transport as transport
import transfer as t

MAGIC=b'GAPORT01'


def portable_index(local_index,destination):
    original=Path(local_index).read_bytes();fields=list(compact.HEADER.unpack_from(original));old_meta=fields[2]
    meta=json.loads(original[compact.HEADER.size:compact.HEADER.size+old_meta])
    meta['containers']=[dict(algorithm='sha256',digest=r['sha256'],size=r['size']) for r in meta['containers']]
    encoded=t.encode(meta);fields[0]=MAGIC;fields[2]=len(encoded)
    result=compact.HEADER.pack(*fields)+encoded+original[compact.HEADER.size+old_meta:]
    t.atomic_write(destination,result);return dict(algorithm='sha256',digest=t.digest(result),size=len(result))


def identity(stat):return [stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns]


def acquire(url,body,pin,root):
    begin=time.perf_counter();view=generic.BinaryView(body,pin);objects=list(view.contents);parsed=time.perf_counter()
    if sum(obj['size'] for obj in objects)>t.MAX_PACK:raise t.TransferError('artifact admission quota')
    root=Path(root);store=cache.Files(root);client=None;hits=set();hashed=len(body)
    try:
        for key,data in store.iter_available(objects):
            hashed+=len(data)
            if t.digest(data)==key:hits.add(key)
        missing=[obj for obj in objects if obj['sha256'] not in hits];checked=time.perf_counter()
        if missing:
            client=transport.Client(url)
            for obj,payload in client.stream_batch(missing):
                hashed+=len(payload)
                if len(payload)!=obj['size'] or t.digest(payload)!=obj['sha256']:raise t.TransferError('preindexed artifact integrity')
                store.put_verified(obj,payload)
        t.atomic_write(root/'ready.json',t.encode(dict(version=1,lock=pin,objects=sorted(obj['sha256'] for obj in objects))))
        return view,dict(seconds=time.perf_counter()-begin,parse_seconds=parsed-begin,cache_seconds=checked-parsed,requests=client.requests if client else 0,transfer_bytes=sum(o['size'] for o in missing),hash_bytes=hashed,cache_hits=len(hits),objects=len(objects),store=dict(store.stats))
    except BaseException:(root/'ready.json').unlink(missing_ok=True);raise
    finally:
        if client:client.close()
        store.close()


def admit(root,index_desc,payload_desc,binding_path):
    """No derived table construction: verify portable tables, publish tiny local binding."""
    begin=time.perf_counter();root=Path(root);objects=root/'objects/sha256';index_path=objects/index_desc['digest'];payload_path=objects/payload_desc['digest']
    body=cache.read_bounded(index_path,compact.MAX_INDEX)
    if len(body)!=index_desc['size'] or t.digest(body)!=index_desc['digest']:raise t.TransferError('portable index admission integrity')
    meta=metadata(body)
    if meta['containers']!=[payload_desc]:raise t.TransferError('portable payload cross-binding')
    desc=dict(path=os.path.relpath(payload_path,root),digest=payload_desc['digest'],size=payload_desc['size'],identity=identity(payload_path.stat()))
    binding=t.encode(dict(version=1,index=index_desc,logical_pin=meta['lock_sha256'],containers=[desc]))
    # The body is private until complete receiver validation succeeds.
    reader=Reader(root,index_path,index_desc['digest'],binding,t.digest(binding),validate_all=True);reader.close()
    t.atomic_write(binding_path,binding)
    return dict(binding_pin=t.digest(binding),logical_pin=meta['lock_sha256'],seconds=time.perf_counter()-begin,index_bytes=len(body),binding_bytes=len(binding))


def metadata(body):
    if len(body)<compact.HEADER.size:raise t.TransferError('portable index header')
    magic,version,ms,n,m,d,c,s=compact.HEADER.unpack_from(body)
    if magic!=MAGIC or version!=1 or ms>t.MAX_MANIFEST or max(n,m,d,c)>t.MAX_OBJECTS*2 or compact.HEADER.size+ms>len(body):raise t.TransferError('portable index version/bounds')
    value=json.loads(body[compact.HEADER.size:compact.HEADER.size+ms],object_pairs_hook=t._pairs)
    if not isinstance(value,dict) or set(value)!={'version','lock_sha256','kind','containers'} or value['version']!=1 or value['kind'] not in ('pack','zip') or not isinstance(value['lock_sha256'],str) or not t.HEX.fullmatch(value['lock_sha256']) or not isinstance(value['containers'],list) or len(value['containers'])!=1 or not cache.valid_descriptor(value['containers'][0],t.MAX_PACK+8):raise t.TransferError('portable index metadata')
    return value


class Reader(compact.Reader):
    def __init__(self,root,index_path,index_pin,binding_body,binding_pin,validate_all=False):
        begin=time.perf_counter();self.stream=None;self.mapping=None;self.data=[];self.closed=False;self.filename=str(root)
        try:
            body=cache.read_bounded(Path(index_path),compact.MAX_INDEX)
            if t.digest(body)!=index_pin:raise t.TransferError('portable index pin')
            self.meta=metadata(body);magic,version,ms,n,m,d,c,s=compact.HEADER.unpack_from(body)
            self.stream=open(index_path,'rb');self.mapping=mmap.mmap(self.stream.fileno(),0,access=mmap.ACCESS_READ)
            if self.mapping[:]!=body:raise t.TransferError('portable index changed')
            self.counts=(n,m,d);self.offsets=(compact.HEADER.size+ms,compact.HEADER.size+ms+n*compact.FILE.size,compact.HEADER.size+ms+n*compact.FILE.size+m*compact.MODULE.size)
            self.children_start=self.offsets[2]+d*compact.DIRECTORY.size;self.string_start=self.children_start+c*4;self.string_size=s;self.child_count=c
            if self.string_start+s!=len(body):raise t.TransferError('portable index table geometry')
            if len(binding_body)>8192 or t.digest(binding_body)!=binding_pin:raise t.TransferError('local binding pin/bound')
            binding=json.loads(binding_body,object_pairs_hook=t._pairs)
            if set(binding)!={'version','index','logical_pin','containers'} or binding['version']!=1 or binding['index']!=dict(algorithm='sha256',digest=index_pin,size=len(body)) or binding['logical_pin']!=self.meta['lock_sha256'] or len(binding['containers'])!=1:raise t.TransferError('local binding schema')
            for local,desc in zip(binding['containers'],self.meta['containers']):
                if set(local)!={'path','digest','size','identity'} or local['digest']!=desc['digest'] or local['size']!=desc['size'] or not isinstance(local['path'],str) or Path(local['path']).is_absolute() or '..' in Path(local['path']).parts:raise t.TransferError('local payload binding')
                stream=open(Path(root)/local['path'],'rb');stat=os.fstat(stream.fileno())
                if identity(stat)!=local['identity'] or stat.st_size!=desc['size']:stream.close();raise t.TransferError('portable payload identity')
                self.data.append((stream,mmap.mmap(stream.fileno(),0,access=mmap.ACCESS_READ)))
            self.tables=[compact.Table(self,i) for i in range(3)];self.entries=self.tables[0];self.precomputed_modules=self.tables[1];self.directories=compact.Directories(self);self.precomputed_packages=compact.Packages(self);self.precomputed_children=compact.Children(self)
            if validate_all:
                for kind in range(3):
                    previous=None
                    for i in range(self.counts[kind]):
                        name=self.name(kind,i);name.decode()
                        if previous is not None and previous>=name:raise t.TransferError('portable index sorted names')
                        previous=name;row=self.row(kind,i)
                        if kind==0:
                            if row[2]>=len(self.data) or row[3] or row[4]+row[5]>len(self.data[row[2]][1]):raise t.TransferError('portable file span')
                        elif kind==1:
                            if row[2]>=n or row[3] not in (0,1):raise t.TransferError('portable module row')
                        elif row[2] not in (0,1) or row[3]+row[4]>c:raise t.TransferError('portable child span')
                for j in range(c):
                    if compact.CHILD.unpack_from(self.mapping,self.children_start+j*4)[0]>=m:raise t.TransferError('portable child ID')
            self.native_timings=dict(setup_seconds=time.perf_counter()-begin,read_seconds=0,hash_seconds=0,reads=0,read_bytes=0,index_bytes=len(body),integrity_policy='sha256+crc32-every-read')
        except BaseException:self.close();raise
