"""Scoped synchronous application-storage model; never claims block-device I/O."""
from dataclasses import dataclass
import fcntl
import hashlib
import os
from pathlib import Path
import tempfile
import time

MAX_BYTES=64*1024*1024
SEALS=fcntl.F_SEAL_SEAL|fcntl.F_SEAL_SHRINK|fcntl.F_SEAL_GROW|fcntl.F_SEAL_WRITE


@dataclass(frozen=True)
class Profile:
    name:str
    read_latency_ms:float=0
    write_latency_ms:float=0
    read_mib_s:float=0
    write_mib_s:float=0
    def __post_init__(self):
        if any(not 0<=value<=10000 for value in (self.read_latency_ms,self.write_latency_ms,self.read_mib_s,self.write_mib_s)):raise ValueError('profile bounds')


PROFILES=(Profile('nominal'),Profile('request-latency',read_latency_ms=1,write_latency_ms=1),Profile('bandwidth',read_mib_s=16,write_mib_s=16))


class ModelIO:
    def __init__(self,root,profile):
        self.root=Path(root).resolve();self.profile=profile;self._scoped={};self.read_calls=0;self.read_bytes=0;self.write_calls=0;self.write_bytes=0;self.requested_seconds=0;self.slept_seconds=0
    def checked(self,path):
        key=str(path)
        if key in self._scoped:return self._scoped[key]
        path=Path(path).resolve()
        if not path.is_relative_to(self.root):raise ValueError('outside private storage scope')
        if len(self._scoped)<4096:self._scoped[key]=path
        return path
    def charge(self,kind,size):
        if not 0<=size<=MAX_BYTES:raise ValueError('storage request bound')
        latency=getattr(self.profile,kind+'_latency_ms')/1000;rate=getattr(self.profile,kind+'_mib_s')
        requested=latency+(size/(rate*1024*1024) if rate else 0)
        if kind=='read':self.read_calls+=1;self.read_bytes+=size
        else:self.write_calls+=1;self.write_bytes+=size
        self.requested_seconds+=requested
        if requested:
            begin=time.perf_counter();time.sleep(requested);self.slept_seconds+=time.perf_counter()-begin
    def read(self,path,expected_size):
        if not 0<=expected_size<=MAX_BYTES:raise ValueError('read bound')
        path=self.checked(path)
        with path.open('rb') as source:
            if os.fstat(source.fileno()).st_size!=expected_size:raise ValueError('storage size mismatch')
            body=source.read(expected_size+1)
        if len(body)!=expected_size:raise ValueError('storage truncation')
        self.charge('read',len(body));return body
    def pread(self,stream,path,offset,size):
        self.checked(path)
        if not 0<=size<=MAX_BYTES or offset<0:raise ValueError('range bound')
        body=os.pread(stream.fileno(),size,offset)
        if len(body)!=size:raise ValueError('storage range truncation')
        self.charge('read',len(body));return body
    def write(self,path,body):
        if len(body)>MAX_BYTES:raise ValueError('write bound')
        path=self.checked(path);path.parent.mkdir(parents=True,exist_ok=True)
        fd,temporary=tempfile.mkstemp(prefix='.stage-',dir=path.parent)
        try:
            with os.fdopen(fd,'wb') as stream:
                if stream.write(body)!=len(body):raise OSError('short storage write')
            os.replace(temporary,path)
        finally:Path(temporary).unlink(missing_ok=True)
        # Logical synchronous-service acknowledgement, independent of kernel writeback.
        self.charge('write',len(body))
    def stats(self):return dict(read_calls=self.read_calls,read_bytes=self.read_bytes,write_calls=self.write_calls,write_bytes=self.write_bytes,requested_seconds=self.requested_seconds,slept_seconds=self.slept_seconds)


class Sealed:
    def __init__(self,body):
        if not 0<len(body)<=MAX_BYTES:raise ValueError('sealed input bound')
        fd=os.memfd_create('gaia-storage-admitted',os.MFD_CLOEXEC|os.MFD_ALLOW_SEALING)
        try:
            view=memoryview(body);at=0
            while at<len(view):
                written=os.write(fd,view[at:])
                if written<=0:raise OSError('short admitted memory copy')
                at+=written
            fcntl.fcntl(fd,fcntl.F_ADD_SEALS,SEALS)
            if fcntl.fcntl(fd,fcntl.F_GET_SEALS)&SEALS!=SEALS:raise OSError('snapshot not sealed')
        except BaseException:os.close(fd);raise
        self.fd=fd;self.size=len(body)
    def close(self):
        if self.fd>=0:os.close(self.fd);self.fd=-1


def checked_digest(body,descriptor):
    if descriptor['algorithm']!='sha256' or len(body)!=descriptor['size'] or hashlib.sha256(body).hexdigest()!=descriptor['digest']:raise ValueError('artifact digest mismatch')
