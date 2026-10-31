"""Linux immutable compiler input segments and explicit edit overlays.

The caller supplies already admitted bytes. Base creation and each changed-body
segment are charged by publish; consumers independently verify new sealed data.
No mutable physical source check is removed by this experiment.
"""
from dataclasses import dataclass
import fcntl
import hashlib
import os
from pathlib import Path
import struct
import time
from types import MappingProxyType

import inline_snapshot
from project_benchmark import encode_inputs

MAX_BYTES=64*1024*1024
MAX_SEGMENTS=8
SEALS=fcntl.F_SEAL_SEAL|fcntl.F_SEAL_SHRINK|fcntl.F_SEAL_GROW|fcntl.F_SEAL_WRITE

class Segment:
    def __init__(self,body,digest,names):
        fd=os.memfd_create('gaia-inputs',os.MFD_CLOEXEC|os.MFD_ALLOW_SEALING)
        try:
            at=0;view=memoryview(body)
            while at<len(body):
                n=os.write(fd,view[at:])
                if n<=0:raise OSError('short immutable input write')
                at+=n
            fcntl.fcntl(fd,fcntl.F_ADD_SEALS,SEALS)
            if fcntl.fcntl(fd,fcntl.F_GET_SEALS)&SEALS!=SEALS:raise OSError('input sealing failed')
            self.owner=os.fdopen(fd,'rb');fd=-1
        finally:
            if fd>=0:os.close(fd)
        self.size=len(body);self.digest=digest;self.names=tuple(names)
    def __del__(self):
        owner=getattr(self,'owner',None)
        if owner is not None:owner.close()
    @property
    def path(self):return f'/proc/{os.getpid()}/fd/{self.owner.fileno()}'

@dataclass(frozen=True)
class State:
    segments:tuple
    files:dict
    deleted:frozenset


def manifest(state):
    out=bytearray(b'GAIACIN4'+struct.pack('<QQ',len(state.files),len(state.segments)))
    for segment in state.segments:
        name=segment.path.encode();out+=struct.pack('<I',len(name))+name+struct.pack('<Q',segment.size)+segment.digest
    out+=struct.pack('<Q',len(state.deleted))
    for name in sorted(state.deleted):
        raw=name.encode();out+=struct.pack('<I',len(raw))+raw
    if len(out)>4*1024*1024:raise ValueError('shared input manifest bound')
    return bytes(out)

class Session:
    def __init__(self,blake3):self.state=None;self.blake3=blake3
    def snapshot(self):return self.state
    def restore(self,state):self.state=state
    def keep_pins(self):return '\n'.join(s.digest.hex() for s in self.state.segments) if self.state else ''
    def publish(self,files,masks,jobs,output,views):
        begin=time.perf_counter_ns()
        if not 1<=jobs<=64 or not 0<len(files)<=100000 or files.keys()!=masks.keys():raise ValueError('shared input membership/jobs')
        bits=(1<<jobs)-1;current={}
        for name,body in files.items():
            if (not name.startswith('/') or name.endswith(('/','/.','/..')) or any(v in name for v in ('//','/./','/../','\\','\0')) or len(name.encode())>4096 or not 0<=masks[name]<=bits or len(body)>MAX_BYTES):raise ValueError('shared input path/mask/content')
            current[name]=body if type(body) is bytes else bytes(body)
        old=self.state
        changed={name:body for name,body in current.items() if old is None or (old.files.get(name) is not body and old.files.get(name)!=body)}
        deleted=((set(old.deleted)|set(old.files).difference(current)).difference(current) if old else set())
        # A compacted base prevents a long edit trace retaining an unbounded chain.
        compact=old is None or (bool(changed) and len(old.segments)>=MAX_SEGMENTS)
        serialized=0;hashed=0
        def segment(items):
            nonlocal serialized,hashed
            body=encode_inputs(items,magic=b'GAIACIN3')
            if len(body)>MAX_BYTES:raise ValueError('shared input segment byte bound')
            hashed+=len(body);pin=self.blake3(body)
            for known in old.segments if old else ():
                if known.digest==pin and known.size==len(body):return known
            serialized+=len(body)
            return Segment(body,pin,sorted(items))
        if not compact and changed:
            estimate=16+sum(14+len(n.encode())+len(b) for n,b in changed.items())
            compact=sum(s.size for s in old.segments)+estimate>MAX_BYTES
        if compact:
            segments=(segment(current),);deleted=set()
        elif changed:
            added=segment(changed)
            segments=tuple(s for s in old.segments if s.digest!=added.digest)+(added,)
        else:segments=old.segments
        state=State(segments,MappingProxyType(current),frozenset(deleted));wire=manifest(state)
        view=('GAIACV1\n'+''.join(f'{masks[name]}\n' for name in sorted(current))).encode()
        pin='blake3:'+self.blake3(wire).hex();view_pin=hashlib.sha256(view).hexdigest();hashed+=len(wire)
        inline_snapshot.atomic_write(output,wire);inline_snapshot.atomic_write(views,view)
        self.state=state
        return dict(correct=True,pin=pin,view_pin=view_pin,files=len(current),bytes=len(wire),loose_reads=0,loose_bytes=0,native_ns=0,
                    caller_ns=time.perf_counter_ns()-begin,created_segment_bytes=serialized,sender_hash_bytes=hashed,changed_files=len(changed),
                    deleted_files=len(deleted),segments=len(segments),retained_segment_bytes=sum(s.size for s in segments),compacted=compact)
