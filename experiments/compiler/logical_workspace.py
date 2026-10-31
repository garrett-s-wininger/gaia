"""Authoritative immutable logical generations and selective completion proofs.

Only admitted API updates change this workspace. A loose directory is a separate
adapter; this provider never claims to discover unreported physical edits.
"""
from collections import OrderedDict
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import stat
import struct
import threading
import time
from types import MappingProxyType
import uuid

import condition_index as reference
from inline_snapshot import atomic_write
from result_history import receipt_proof,rebound_receipt

MAGIC=b'GAIALQ01';LIMIT=8*1048576
class GenerationChanged(RuntimeError):pass

@dataclass(frozen=True)
class Generation:
    number:int
    files:dict
    masks:dict
    digests:dict
    nodes:dict
    jobs:int

class Workspace:
    def __init__(self,files,masks,jobs):
        if not 1<=jobs<=64:raise ValueError('logical job count')
        self.jobs=jobs;self.lock=threading.RLock();self.serial=0
        self.head=Generation(-1,MappingProxyType({}),MappingProxyType({}),MappingProxyType({}),MappingProxyType({}),jobs)
        _,self.initial_admission=self.apply(files,masks=masks)
    def snapshot(self):return self.head
    def restore(self,generation):
        # Explicit benchmark control, not a user-facing epoch rollback operation.
        if generation.jobs!=self.jobs:raise ValueError('logical generation job domain')
        with self.lock:self.head=generation;self.serial=max(self.serial,generation.number+1)
    def apply(self,edits,deleted=(),masks=None,expected=None):
        begin=time.perf_counter_ns()
        with self.lock:
            old=self.head
            if expected is not None and old.number!=expected:raise GenerationChanged('logical generation changed')
            files=dict(old.files);digests=dict(old.digests);visibility=dict(old.masks)
            for name in deleted:files.pop(name,None);digests.pop(name,None);visibility.pop(name,None)
            hashed=0
            for name,body in edits.items():
                if not isinstance(name,str) or reference.canonical(name)!=name or len(name.encode())>4096:raise ValueError('logical canonical path')
                if not isinstance(body,(bytes,bytearray)) or len(body)>64*1048576:raise ValueError('logical body bound/type')
                body=body if type(body) is bytes else bytes(body)
                if name not in files or (body is not files[name] and body!=files[name]):
                    digests[name]=hashlib.sha256(body).digest();hashed+=len(body);files[name]=body
                visibility.setdefault(name,(1<<self.jobs)-1)
            if masks is not None:visibility=dict(masks)
            if files.keys()!=visibility.keys() or not 0<len(files)<=100000 or sum(map(len,files.values()))>64*1048576:raise ValueError('logical membership/bytes')
            bits=(1<<self.jobs)-1
            if any(type(m) is not int or not 0<=m<=bits for m in visibility.values()):raise ValueError('logical visibility')
            nodes=old.nodes if visibility==old.masks else MappingProxyType({n:tuple(v) for n,v in reference.namespace_nodes(visibility).items()})
            if files==old.files and visibility==old.masks:
                return old,dict(admission_ns=time.perf_counter_ns()-begin,hashed_bytes=hashed,changed=False)
            current=Generation(self.serial,MappingProxyType(files),MappingProxyType(visibility),MappingProxyType(digests),nodes,self.jobs)
            self.serial+=1;self.head=current
            return current,dict(admission_ns=time.perf_counter_ns()-begin,hashed_bytes=hashed,changed=True)


def import_physical(workspace,names,masks):
    """Strict known-namespace adapter. Full reading/discovery cost is explicit."""
    begin=time.perf_counter_ns();captured=workspace.snapshot();paths_=[Path(n) for n in names]
    def stamp(path):
        try:return metadata(path)
        except FileNotFoundError:return None
    before={str(p):stamp(p) for p in paths_};files={}
    for path in paths_:
        if before[str(path)] is not None:files[str(path)]=bounded(path,64*1048576)
    if any(stamp(p)!=before[str(p)] for p in paths_):raise GenerationChanged('physical import changed while reading')
    generation,stats=workspace.apply(files,deleted=set(captured.files).difference(files),masks={n:masks[n] for n in files},expected=captured.number)
    return generation,dict(seconds=(time.perf_counter_ns()-begin)/1e9,stat_calls=len(paths_)*2,physical_reads=len(files),physical_bytes=sum(map(len,files.values())),admission=stats)


def logical_projection(cq):
    """Normalize physical index rows into a separately versioned logical wire."""
    if len(cq)<48 or cq[:8] not in (b'GAIACQ01',MAGIC):raise reference.UnsupportedIndex('logical index header')
    data=bytearray(cq);data[:8]=MAGIC;count=struct.unpack_from('<Q',data,8)[0];at=16
    if count>65536:raise reference.UnsupportedIndex('logical index count')
    for _ in range(count):
        if at>len(data)-32-17:raise reference.UnsupportedIndex('logical index row')
        kind=data[at];length=struct.unpack_from('<Q',data,at+9)[0];patch=at+17+length
        if patch>len(data)-32-64:raise reference.UnsupportedIndex('logical index path')
        data[patch+8:patch+32]=bytes(24)
        at=patch+64
    if at!=len(data)-32:raise reference.UnsupportedIndex('logical index tail')
    data[-32:]=hashlib.sha256(data[:-32]).digest();return data

class LogicalEmitter:
    def verify(self,template):
        template+=bytes(32);out=logical_projection(template)
        return out,dict(physical_reads=0,physical_bytes=0,logical_index=True)


def decode_index(body):
    if not 48<=len(body)<=LIMIT or body[:8]!=MAGIC or hashlib.sha256(body[:-32]).digest()!=body[-32:]:raise ValueError('logical index checksum/version')
    count=struct.unpack_from('<Q',body,8)[0]
    if count>65536:raise ValueError('logical condition count')
    result=[];at=16;previous=None
    for _ in range(count):
        if at>len(body)-32-17:raise ValueError('logical row')
        kind=body[at];jobs,length=struct.unpack_from('<QQ',body,at+1);at+=17
        if kind>3 or not jobs or not 0<length<=4096 or length>len(body)-32-at:raise ValueError('logical path/type')
        name=body[at:at+length].decode();at+=length
        if reference.canonical(name)!=name or at>len(body)-32-64:raise ValueError('logical canonical path')
        size,a,b,c=struct.unpack_from('<QQQQ',body,at);digest=body[at+32:at+64];at+=64
        if a or b or c or (kind!=1 and size) or (kind in (0,2) and digest!=bytes(32)):raise ValueError('logical reserved metadata')
        key=(kind,name,digest)
        if previous is not None and key<=previous:raise ValueError('logical row order')
        previous=key;result.append((kind,name,jobs,size,digest))
    if at!=len(body)-32:raise ValueError('logical tail')
    return result


def validate(rows,generation):
    checked=0
    for kind,name,jobs,size,digest in rows:
        checked+=1
        if jobs&~((1<<generation.jobs)-1):return False,checked
        fm,dm=generation.nodes.get(name,(0,0))
        if kind==0:
            if (fm|dm)&jobs:return False,checked
        elif kind==2:
            if dm&jobs!=jobs:return False,checked
        elif kind==1:
            if fm&jobs!=jobs or name not in generation.files or len(generation.files[name])!=size or generation.digests[name]!=digest:return False,checked
        else:
            if dm&jobs!=jobs:return False,checked
            children=sorted((n,f,d) for n,(f,d) in generation.nodes.items() if n!='/' and str(Path(n).parent)==name)
            pending=jobs
            while pending:
                bit=pending&-pending;pending-=bit
                visible=[(n,1 if f&bit else 2) for n,f,d in children if (f|d)&bit]
                encoded=bytearray(b'GAIA-LIST-1'+struct.pack('<Q',len(visible)))
                for n,k in visible:
                    raw=n.encode();encoded+=struct.pack('<Q',len(raw))+raw+bytes([k])
                if hashlib.sha256(encoded).digest()!=digest:return False,checked
    return True,checked


def bounded(path,limit):
    # Avoid reserving the entire quota for a small receipt/index/output.
    if not stat.S_ISREG(path.lstat().st_mode):raise ValueError('logical regular file')
    with path.open('rb') as stream:
        size=os.fstat(stream.fileno()).st_size
        if not 0<=size<=limit:raise ValueError('logical bounded file')
        data=stream.read(size+1)
        if len(data)!=size:raise ValueError('logical file size changed')
        return data


def paths(path,limit):
    data=bounded(Path(path),4*1048576).decode().splitlines()
    if not data or data[0]!='GAIA-WATCH-1' or not 1<=len(data)-1<=limit:raise ValueError('logical watch framing')
    values=data[1:]
    if len(values)!=len(set(values)) or any(not p.startswith('/') or '\0' in p for p in values):raise ValueError('logical watch paths')
    return [Path(p) for p in values]

def metadata(path):
    s=path.stat();return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode)

class Checker:
    def __init__(self,workspace,tool_pins):
        self.workspace=workspace;self.tool_pins=dict(tool_pins);self.tool_cache={};self.pending=OrderedDict();self.requests=0;self.conditions=0
    def cpu_seconds(self):return 0.0
    def statistics(self):return dict(requests=self.requests,in_process=True,conditions=self.conditions,output_policy='unconditional SHA-256',physical_source_reads=0)
    def close(self):self.pending.clear()
    def begin(self):self.pending.clear()
    def tools(self,watch):
        parts=[];names=paths(watch,100000)
        if {str(p) for p in names}!=set(self.tool_pins):raise ValueError('logical tool membership')
        for path in names:
            name=str(path);before=metadata(path);known=self.tool_cache.get(name)
            if name not in self.tool_pins:raise ValueError('unadmitted logical tool')
            if known!=before:
                if hashlib.sha256(path.read_bytes()).hexdigest()!=self.tool_pins[name] or metadata(path)!=before:raise ValueError('logical tool changed')
                self.tool_cache[name]=before
            parts.append((name,before,self.tool_pins[name]))
        return hashlib.sha256(json.dumps(parts,separators=(',',':')).encode()).digest()
    def capture(self,token):return self.pending[token][0]
    def call(self,argv):
        self.requests+=1
        _,mode,receipt,request,watch,outputs,namespace,index,*stamp=map(str,argv)
        current=self.workspace.snapshot();tools=self.tools(watch)
        token=None
        if mode!='selective-record':
            token=uuid.uuid4().hex+uuid.uuid4().hex
            self.pending[token]=(current,tools)
            while len(self.pending)>4:self.pending.popitem(last=False)
        def conditions(generation):
            wire=bounded(Path(index),LIMIT);rows=decode_index(wire)
            if any(jobs&~((1<<self.workspace.jobs)-1) for _,_,jobs,_,_ in rows):raise ValueError('logical job mask')
            okay,checked=validate(rows,generation);self.conditions+=checked
            return okay,wire
        if mode=='selective-record':
            proof=self.pending.get(stamp[0]) if len(stamp)==1 else None
            if proof is None:return dict(recorded=False,inputs_unchanged=False)
            captured,expected_tools=proof
            with self.workspace.lock:
                try:
                    okay,wire=conditions(captured);rows=decode_index(wire)
                    now_ok,checked=validate(rows,self.workspace.head);self.conditions+=checked
                    if not okay or not now_ok or tools!=expected_tools:return dict(recorded=False,inputs_unchanged=False)
                    hashes=[];output_paths=paths(outputs,64)
                    if Path(index) not in output_paths:raise ValueError('logical index output role')
                    for path in output_paths:
                        before=metadata(path);data=bounded(path,16*1048576)
                        if metadata(path)!=before:raise ValueError('logical output changed')
                        if path==Path(index) and data!=wire:raise ValueError('logical index changed')
                        hashes.append((path,hashlib.sha256(data).digest()))
                    if self.tools(watch)!=expected_tools:return dict(recorded=False,inputs_unchanged=False)
                    identity=hashlib.sha256(b'GAIA-LOGICAL-COMPLETE-1'+request.encode()+tools+hashlib.sha256(wire).digest()).digest()
                    atomic_write(receipt,rebound_receipt(request,identity,hashes))
                    return dict(recorded=True,inputs_unchanged=True,generation=self.workspace.head.number)
                except (OSError,ValueError,KeyError,UnicodeError):return dict(recorded=False,inputs_unchanged=False)
        if mode not in ('selective-check','selective-history-check'):raise ValueError('logical checker operation')
        try:
            okay,wire=conditions(current)
            if not okay:return dict(hit=False,stamp=token,content_hashes=0)
            identity,stored=receipt_proof(receipt,request)
            expected=hashlib.sha256(b'GAIA-LOGICAL-COMPLETE-1'+request.encode()+tools+hashlib.sha256(wire).digest()).digest()
            if identity!=expected or set(stored)!={str(p) for p in paths(outputs,64)}:raise ValueError('logical receipt identity/output roles')
            count=0
            for name,(size,digest) in stored.items():
                path=Path(name);before=metadata(path);data=bounded(path,16*1048576);count+=1
                if len(data)!=size or hashlib.sha256(data).digest()!=digest or metadata(path)!=before:raise ValueError('logical output integrity')
            with self.workspace.lock:
                rows=decode_index(wire);stable,_=validate(rows,self.workspace.head)
                if not stable or self.tools(watch)!=tools:return dict(hit=False,stamp=token,content_hashes=count)
            return dict(hit=True,stamp=token,content_hashes=count,generation=self.workspace.head.number)
        except (OSError,ValueError,KeyError,UnicodeError):return dict(hit=False,stamp=token,content_hashes=0)
