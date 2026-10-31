"""Identical compact tables/per-read hashes over explicit ranges or sealed memory."""
import json
import fcntl
import mmap
import os
from pathlib import Path
import sys
import time

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'artifacts'))
import compact_python as compact
import preindexed_bundle as portable
import transfer as t
from service import ModelIO,Profile,Sealed,SEALS,checked_digest


class RangeData:
    def __init__(self,model,stream,path,size):self.model,self.stream,self.path,self.size=model,stream,path,size
    def __len__(self):return self.size
    def __getitem__(self,slice):
        if not isinstance(slice,slice_type) or slice.step is not None:raise ValueError('only contiguous byte ranges')
        start,stop=slice.start,slice.stop
        if not 0<=start<=stop<=self.size:raise ValueError('payload range')
        return self.model.pread(self.stream,self.path,start,stop-start)
    def close(self):pass


slice_type=slice


class Reader(compact.Reader):
    def __init__(self,job,model):
        begin=time.perf_counter();self.closed=False;self.stream=None;self.mapping=None;self.data=[];self.index_owner=None;self.filename=job['root']
        try:
            if job['mode']=='range':
                body=model.read(job['index_path'],job['index']['size']);checked_digest(body,job['index']);self.index_owner=Sealed(body);index_fd=self.index_owner.fd
            else:
                index_fd=job['index_fd']
                for fd in (index_fd,job['payload_fd']):
                    if fcntl.fcntl(fd,fcntl.F_GET_SEALS)&SEALS!=SEALS:raise ValueError('only fully sealed memory inputs are accepted')
                if os.fstat(index_fd).st_size!=job['index']['size']:raise ValueError('sealed index size')
                body=os.pread(index_fd,job['index']['size'],0);checked_digest(body,job['index'])
            meta=portable.metadata(body)
            if meta['containers']!=[job['payload']]:raise ValueError('index/payload binding')
            self.mapping=mmap.mmap(index_fd,0,access=mmap.ACCESS_READ)
            magic,version,ms,n,m,d,c,s=compact.HEADER.unpack_from(body);self.counts=(n,m,d);self.offsets=(compact.HEADER.size+ms,compact.HEADER.size+ms+n*compact.FILE.size,compact.HEADER.size+ms+n*compact.FILE.size+m*compact.MODULE.size)
            self.children_start=self.offsets[2]+d*compact.DIRECTORY.size;self.string_start=self.children_start+c*4;self.string_size=s;self.child_count=c
            if self.string_start+s!=len(body):raise ValueError('index regions')
            if job['mode']=='range':
                path=model.checked(job['payload_path']);stream=path.open('rb')
                if os.fstat(stream.fileno()).st_size!=job['payload']['size']:stream.close();raise ValueError('payload size')
                self.data=[(stream,RangeData(model,stream,path,job['payload']['size']))]
            elif job['mode']=='memory':
                fd=job['payload_fd'];stream=os.fdopen(os.dup(fd),'rb')
                if os.fstat(fd).st_size!=job['payload']['size']:stream.close();raise ValueError('memory payload size')
                self.data=[(stream,mmap.mmap(fd,0,access=mmap.ACCESS_READ))]
            else:raise ValueError('reader mode')
            self.tables=[compact.Table(self,i) for i in range(3)];self.entries=self.tables[0];self.precomputed_modules=self.tables[1];self.directories=compact.Directories(self);self.precomputed_packages=compact.Packages(self);self.precomputed_children=compact.Children(self)
            self.native_timings=dict(setup_seconds=time.perf_counter()-begin,read_seconds=0,hash_seconds=0,reads=0,read_bytes=0,index_bytes=len(body),integrity_policy='sha256+crc32-every-read')
        except BaseException:self.close();raise
    def close(self):
        super().close()
        if self.index_owner:self.index_owner.close();self.index_owner=None


def validate_index(body,payload):
    meta=portable.metadata(body)
    if meta['containers']!=[payload]:raise ValueError('portable payload cross-binding')
    magic,version,ms,n,m,d,c,s=compact.HEADER.unpack_from(body)
    starts=(compact.HEADER.size+ms,compact.HEADER.size+ms+n*compact.FILE.size,compact.HEADER.size+ms+n*compact.FILE.size+m*compact.MODULE.size)
    children=starts[2]+d*compact.DIRECTORY.size;pool=children+c*4
    if pool+s!=len(body):raise ValueError('index table geometry')
    for kind,count in enumerate((n,m,d)):
        previous=None;schema=(compact.FILE,compact.MODULE,compact.DIRECTORY)[kind]
        for i in range(count):
            row=schema.unpack_from(body,starts[kind]+i*schema.size);offset,size=row[:2]
            if offset+size>s:raise ValueError('index text bounds')
            name=body[pool+offset:pool+offset+size];name.decode()
            if previous is not None and previous>=name:raise ValueError('index ordering')
            previous=name
            if kind==0:
                if row[2]!=0 or row[3] or row[4]+row[5]>payload['size']:raise ValueError('file span')
            elif kind==1:
                if row[2]>=n or row[3] not in (0,1):raise ValueError('module row')
            elif row[2] not in (0,1) or row[3]+row[4]>c:raise ValueError('children span')
    for i in range(c):
        if compact.CHILD.unpack_from(body,children+i*4)[0]>=m:raise ValueError('child row')
    return meta
