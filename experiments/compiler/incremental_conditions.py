"""Batch condition production and reuse parsed, content-identified query fragments.

The cache retains only the current request's actions. It never caches namespace
classification or backing-file verification; those are recomputed on each export.
"""
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import posixpath
import struct
import tempfile

import condition_index as reference

MAX_CACHE=8*1048576
MASK=(1<<64)-1


@dataclass(frozen=True)
class Fragment:
    queries: int
    targets: tuple
    listings: tuple


def parse_fragment(journal,cwd):
    current=reference.canonical(cwd);targets=set();listings=set();queries=0
    for op,outcome,path in reference.decode_journal(journal):
        queries+=1
        target=current if op==8 else reference.canonical(posixpath.join(current,path))
        targets.add(target)
        if op==6:listings.add(target)
        if op==9 and outcome==0:current=target
    return Fragment(queries,tuple(sorted(targets)),tuple(sorted(listings)))


def assemble(fragments,files,masks):
    if not 0<len(fragments)<=64:raise reference.UnsupportedIndex('job limit')
    nodes=reference.namespace_nodes(masks);targets={};listings={};queries=0
    for job,fragment in enumerate(fragments):
        bit=1<<job;queries+=fragment.queries
        for name in fragment.targets:targets[name]=targets.get(name,0)|bit
        for name in fragment.listings:listings[name]=listings.get(name,0)|bit
    conditions={};hashes={};merges=0
    def add(kind,name,jobs,digest=bytes(32)):
        nonlocal merges
        if not jobs:return
        merges+=1;key=(kind,name,digest);conditions[key]=conditions.get(key,0)|jobs
        if len(conditions)>65536:raise reference.UnsupportedIndex('condition count limit')
    for target,jobs in targets.items():
        for name in reference.prefixes(target):
            file_mask,dir_mask=nodes.get(name,(0,0))
            visible=jobs&file_mask
            if visible:
                if name not in files:raise reference.UnsupportedIndex('missing admitted bytes')
                if name not in hashes:hashes[name]=hashlib.sha256(files[name]).digest()
                add(1,name,visible,hashes[name])
            add(2,name,jobs&dir_mask)
            add(0,name,jobs&~(file_mask|dir_mask)&MASK)
    # Construct directory adjacency once, rather than scanning all nodes for
    # every listing/job. Each job still gets its exact visible child sequence.
    children={}
    if listings:
        for name,(file_mask,dir_mask) in nodes.items():
            if name!='/':children.setdefault(posixpath.dirname(name),[]).append((name,file_mask,dir_mask))
        for values in children.values():values.sort()
    for name,jobs in listings.items():
        pending=jobs&nodes.get(name,(0,0))[1]
        while pending:
            bit=pending&-pending;pending-=bit
            visible=[(child,1 if fm&bit else 2) for child,fm,dm in children.get(name,()) if (fm|dm)&bit]
            body=bytearray(b'GAIA-LIST-1'+struct.pack('<Q',len(visible)))
            for child,kind in visible:
                value=child.encode();body+=struct.pack('<Q',len(value))+value+bytes([kind])
            add(3,name,bit,hashlib.sha256(body).digest())
    encoded,stats=reference.encode_conditions(conditions,files,len(hashes),queries)
    stats.update(target_paths=len(targets),condition_merges=merges)
    return encoded,stats


def build_batched(journals,files,masks,cwd):
    if not 0<len(journals)<=64:raise reference.UnsupportedIndex('job limit')
    fragments=[parse_fragment(journal,cwd) for journal in journals]
    encoded,stats=assemble(fragments,files,masks)
    stats.update(fragment_hits=0,fragment_misses=len(fragments),queries_parsed=sum(f.queries for f in fragments))
    return encoded,stats


class Reader:
    def __init__(self,raw):self.raw=raw;self.at=0
    def take(self,size):
        if size<0 or size>len(self.raw)-self.at:raise reference.UnsupportedIndex('fragment cache framing')
        out=self.raw[self.at:self.at+size];self.at+=size;return out
    def number(self):return struct.unpack('<Q',self.take(8))[0]
    def ids(self,paths):
        count=self.number()
        if count>65536:raise reference.UnsupportedIndex('fragment target count')
        ids=struct.unpack('<'+'I'*count,self.take(count*4))
        if any(i>=len(paths) for i in ids):raise reference.UnsupportedIndex('fragment path reference')
        names=tuple(paths[i] for i in ids)
        if names!=tuple(sorted(set(names))):raise reference.UnsupportedIndex('fragment target ordering')
        return names


def read_cache(path):
    try:
        with Path(path).open('rb') as stream:
            size=os.fstat(stream.fileno()).st_size
            if not 56<=size<=MAX_CACHE:return {},False
            raw=stream.read(size+1)
            if len(raw)!=size:return {},False
        if not 56<=len(raw)<=MAX_CACHE or raw[:8]!=b'GAIACF01' or hashlib.sha256(raw[:-32]).digest()!=raw[-32:]:return {},False
        reader=Reader(raw[8:-32]);count=reader.number()
        if not 0<count<=100000:raise reference.UnsupportedIndex('fragment path count')
        paths=[]
        for _ in range(count):
            length=reader.number()
            if not 0<length<=4096:raise reference.UnsupportedIndex('fragment path length')
            name=reader.take(length).decode('utf-8',errors='strict')
            if reference.canonical(name)!=name:raise reference.UnsupportedIndex('fragment canonical path')
            paths.append(name)
        if paths!=sorted(set(paths)):raise reference.UnsupportedIndex('fragment path ordering')
        count=reader.number()
        if not 0<count<=64:raise reference.UnsupportedIndex('fragment action count')
        entries={}
        for _ in range(count):
            action=reader.take(32).hex();journal=reader.take(32).hex();cwd_id=reader.number();queries=reader.number()
            if cwd_id>=len(paths) or not 0<queries<=65536:raise reference.UnsupportedIndex('fragment action')
            key=(action,journal,paths[cwd_id]);targets=reader.ids(paths);listings=reader.ids(paths)
            if not targets or len(targets)>queries or len(listings)>queries or not set(listings)<=set(targets) or key in entries:
                raise reference.UnsupportedIndex('fragment entries')
            entries[key]=Fragment(queries,targets,listings)
        if reader.at!=len(reader.raw):raise reference.UnsupportedIndex('fragment cache trailing bytes')
        return entries,True
    except (OSError,UnicodeError,reference.UnsupportedIndex,struct.error):return {},False


def encode_cache(entries):
    if not 0<len(entries)<=64:raise reference.UnsupportedIndex('fragment cache action limit')
    paths=sorted({name for key,f in entries.items() for name in (key[2],*f.targets,*f.listings)})
    if len(paths)>100000:raise reference.UnsupportedIndex('fragment path count')
    indices={name:i for i,name in enumerate(paths)}
    raw=bytearray(b'GAIACF01'+struct.pack('<Q',len(paths)))
    for path in paths:
        name=path.encode();raw+=struct.pack('<Q',len(name))+name
        if len(raw)>MAX_CACHE-32:raise reference.UnsupportedIndex('fragment cache byte limit')
    raw+=struct.pack('<Q',len(entries))
    for (action,journal,cwd),fragment in sorted(entries.items()):
        raw+=bytes.fromhex(action)+bytes.fromhex(journal)+struct.pack('<QQ',indices[cwd],fragment.queries)
        for names in (fragment.targets,fragment.listings):
            raw+=struct.pack('<Q',len(names))+struct.pack('<'+'I'*len(names),*(indices[name] for name in names))
        if len(raw)>MAX_CACHE-32:raise reference.UnsupportedIndex('fragment cache byte limit')
    raw+=hashlib.sha256(raw).digest();return raw


def write_cache(path,raw):
    path=Path(path);fd,tmp=tempfile.mkstemp(prefix=path.name+'.tmp.',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as stream:stream.write(raw)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


def build_incremental(store,result,files,masks,cwd,cache_path):
    cwd=reference.canonical(cwd);keys=result.get('cache_keys',[]);pins=result.get('journal_sha256',[])
    objects=result.get('object_sha256',[])
    if not 0<len(keys)<=64 or len(keys)!=len(pins) or len(keys)!=len(objects):
        raise reference.UnsupportedIndex('missing selected identities')
    for value in (*keys,*pins,*objects):
        if not isinstance(value,str) or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):
            raise reference.UnsupportedIndex('invalid selected identity')
    previous,valid=read_cache(cache_path);current={};fragments=[];hits=misses=parsed=0
    for action,pin,obj in zip(keys,pins,objects):
        key=(action,pin,cwd);fragment=previous.get(key)
        if fragment is None:
            selected=dict(cache_keys=[action],journal_sha256=[pin],object_sha256=[obj])
            raw=reference.selected_journals(store,selected)[0]
            fragment=parse_fragment(raw,cwd);misses+=1;parsed+=fragment.queries
        else:hits+=1
        fragments.append(fragment);current[key]=fragment
    encoded,stats=assemble(fragments,files,masks)
    # Retain only the current request: at most 64 entries and 8 MiB. A corrupt
    # or missing cache triggers recomputation, never a relaxed condition check.
    cache=b'';published=False;issue=None
    try:
        cache=encode_cache(current);write_cache(cache_path,cache);published=True
    except (OSError,reference.UnsupportedIndex) as error:
        # Parsed-fragment caching is optional; a valid index can still publish.
        issue=str(error)
    stats.update(fragment_hits=hits,fragment_misses=misses,queries_parsed=parsed,
                 fragment_cache_valid=valid,fragment_cache_bytes=len(cache),fragment_cache_published=published)
    if issue:stats['fragment_cache_issue']=issue
    return encoded,stats
