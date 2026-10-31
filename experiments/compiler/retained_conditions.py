"""Retain one verified producer state; emit the unchanged condition/cache wires.

Only immutable query structure, namespace classification and hashes of identical
Python bytes objects are reused. Physical backing is read and verified on every
export. State advances only after a complete valid index is constructed.
"""
from dataclasses import dataclass
import hashlib
from pathlib import Path
import struct
import time
from types import MappingProxyType

import condition_index as reference
import incremental_conditions as previous


@dataclass(frozen=True)
class Namespace:
    masks: dict
    nodes: dict


@dataclass(frozen=True)
class Plan:
    signature: tuple
    rows: tuple
    targets: int
    merges: int


@dataclass(frozen=True)
class State:
    fragments: dict
    namespace: Namespace
    plan: Plan
    contents: dict
    paths: dict
    cwd: str


def namespace(masks):
    if len(masks)>100000 or 16+sum(16+len(name.encode()) for name in masks)>4*1048576:
        raise reference.UnsupportedIndex('retained namespace bound')
    return Namespace(MappingProxyType(dict(masks)),MappingProxyType({name:tuple(value) for name,value in reference.namespace_nodes(masks).items()}))


def make_plan(fragments,ns):
    signature=tuple((f.targets,f.listings) for f in fragments)
    targets={};listings={}
    for job,fragment in enumerate(fragments):
        bit=1<<job
        for name in fragment.targets:targets[name]=targets.get(name,0)|bit
        for name in fragment.listings:listings[name]=listings.get(name,0)|bit
    conditions={};merges=0;wire_size=48
    def add(kind,name,jobs,digest=bytes(32)):
        nonlocal merges,wire_size
        if not jobs:return
        merges+=1;key=(kind,name,digest)
        if key not in conditions:
            wire_size+=81+len(name.encode())
            if len(conditions)>=65536 or wire_size>8*1048576:raise reference.UnsupportedIndex('retained condition bound')
        conditions[key]=conditions.get(key,0)|jobs
    for target,jobs in targets.items():
        for name in reference.prefixes(target):
            file_mask,dir_mask=ns.nodes.get(name,(0,0))
            add(1,name,jobs&file_mask)
            add(2,name,jobs&dir_mask)
            add(0,name,jobs&~(file_mask|dir_mask)&previous.MASK)
    children={}
    if listings:
        import posixpath
        for name,(fm,dm) in ns.nodes.items():
            if name!='/':children.setdefault(posixpath.dirname(name),[]).append((name,fm,dm))
        for values in children.values():values.sort()
    for name,jobs in listings.items():
        pending=jobs&ns.nodes.get(name,(0,0))[1]
        while pending:
            bit=pending&-pending;pending-=bit
            visible=[(child,1 if fm&bit else 2) for child,fm,dm in children.get(name,()) if (fm|dm)&bit]
            body=bytearray(b'GAIA-LIST-1'+struct.pack('<Q',len(visible)))
            for child,kind in visible:
                raw=child.encode();body+=struct.pack('<Q',len(raw))+raw+bytes([kind])
            add(3,name,bit,hashlib.sha256(body).digest())
    rows=[]
    for (kind,name,digest),jobs in sorted(conditions.items()):
        raw=name.encode();prefix=bytes([kind])+struct.pack('<QQ',jobs,len(raw))+raw
        # A positive path has one current body for all visible jobs. Its digest
        # changes without changing ordering among the unique kind/path rows.
        rows.append((kind,name,prefix,None if kind==1 else prefix+bytes(32)+digest))
    return Plan(signature,tuple(rows),len(targets),merges)


class Producer:
    def __init__(self,verifier=None):self.state=None;self.verifier=verifier

    def snapshot(self):
        # State and its dictionaries are never mutated after publication. Bytes
        # and frozen fragments/plans can be shared by deterministic seed states.
        return self.state

    def restore(self,state):self.state=state

    def build(self,store,result,files,masks,cwd,cache_path):
        begin=time.perf_counter_ns();cwd=reference.canonical(cwd)
        keys=result.get('cache_keys',[]);pins=result.get('journal_sha256',[]);objects=result.get('object_sha256',[])
        if not 0<len(keys)<=64 or len(keys)!=len(pins) or len(keys)!=len(objects):raise reference.UnsupportedIndex('selected identities')
        for value in (*keys,*pins,*objects):
            if not isinstance(value,str) or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):raise reference.UnsupportedIndex('selected identity')
        old=self.state
        if old is None:cached,valid=previous.read_cache(cache_path);source='disk'
        else:cached=old.fragments;valid=None;source='memory'
        current={};fragments=[];hits=misses=parsed=0
        paths=dict(old.paths) if old else {}
        paths.setdefault(cwd,cwd)
        def intern(fragment):
            return previous.Fragment(fragment.queries,tuple(paths.setdefault(name,name) for name in fragment.targets),
                                     tuple(paths.setdefault(name,name) for name in fragment.listings))
        for action,pin,obj in zip(keys,pins,objects):
            key=(action,pin,cwd);fragment=cached.get(key)
            if fragment is None:
                raw=reference.selected_journals(store,dict(cache_keys=[action],journal_sha256=[pin],object_sha256=[obj]))[0]
                fragment=intern(previous.parse_fragment(raw,cwd));misses+=1;parsed+=fragment.queries
            else:
                hits+=1
                if old is None:fragment=intern(fragment)
            fragments.append(fragment);current[key]=fragment
        loaded=time.perf_counter_ns()
        ns_hit=old is not None and masks==old.namespace.masks
        ns=old.namespace if ns_hit else namespace(masks)
        signature=tuple((f.targets,f.listings) for f in fragments)
        plan_hit=ns_hit and signature==old.plan.signature
        plan=old.plan if plan_hit else make_plan(fragments,ns)
        if not plan_hit or old is None or cwd!=old.cwd:
            used={cwd}
            for fragment in fragments:used.update(fragment.targets);used.update(fragment.listings)
            if len(used)>100000:raise reference.UnsupportedIndex('retained path bound')
            paths={name:paths[name] for name in used}
        planned=time.perf_counter_ns()
        out=bytearray(b'GAIACQ01'+struct.pack('<Q',len(plan.rows)));contents={};kinds={};hashed=reused=physical_bytes=0
        for kind,name,prefix,fixed in plan.rows:
            if kind==1:
                if name not in files:raise reference.UnsupportedIndex('missing admitted bytes')
                body=files[name];known=old.contents.get(name) if old else None
                if type(body) is bytes and known is not None and body is known[0]:digest=known[1];reused+=1
                else:digest=hashlib.sha256(body).digest();hashed+=1
                if type(body) is bytes:contents[name]=(body,digest)
                size=len(body)
                if self.verifier is not None:
                    out+=prefix+struct.pack('<QQQQ',size,0,0,0)+digest
                else:
                    info=Path(name).stat();size=len(body)
                    if info.st_size!=size:raise reference.UnsupportedIndex('physical file differs from compiler input')
                    backing=Path(name).read_bytes();physical_bytes+=len(backing)
                    if hashlib.sha256(backing).digest()!=digest:raise reference.UnsupportedIndex('physical file differs from compiler input')
                    sec,ns_part=divmod(info.st_mtime_ns,10**9)
                    out+=prefix+struct.pack('<QQQQ',size,sec%((1<<64)),ns_part,info.st_mode)+digest
            else:out+=fixed
            kinds[str(kind)]=kinds.get(str(kind),0)+1
        native_stats={}
        if self.verifier is not None:
            out,native_stats=self.verifier.verify(out);physical_bytes=native_stats['physical_bytes']
        else:out+=hashlib.sha256(out).digest()
        if len(out)>8*1048576:raise reference.UnsupportedIndex('condition byte bound')
        emitted=time.perf_counter_ns();cache=b'';published=False;issue=None
        try:
            cache=previous.encode_cache(current);serialized=time.perf_counter_ns()
            previous.write_cache(cache_path,cache);published=True
        except (OSError,reference.UnsupportedIndex) as error:
            serialized=time.perf_counter_ns();issue=str(error)
        finished=time.perf_counter_ns()
        # Oversize parsed metadata must not become an unbounded retained state.
        retained=bool(cache)
        self.state=State(MappingProxyType(current),ns,plan,MappingProxyType(contents),MappingProxyType(paths),cwd) if retained else None
        stats=dict(queries=sum(f.queries for f in fragments),conditions=len(plan.rows),positive_files=int(kinds.get('1',0)),kinds=kinds,bytes=len(out),
                   target_paths=plan.targets,condition_merges=0 if plan_hit else plan.merges,fragment_hits=hits,fragment_misses=misses,queries_parsed=parsed,
                   fragment_cache_valid=valid,fragment_cache_source=source,fragment_cache_bytes=len(cache),fragment_cache_published=published,
                   namespace_reused=ns_hit,condition_plan_reused=plan_hit,logical_hashes_computed=hashed,logical_hashes_reused=reused,
                   physical_reads=int(kinds.get('1',0)),physical_bytes=physical_bytes,retained=retained,
                   stages_ns=dict(fragment_load=loaded-begin,plan=planned-loaded,verify_emit=emitted-planned,fragment_encode=serialized-emitted,fragment_publish=finished-serialized))
        stats.update(native_stats)
        if issue:stats['fragment_cache_issue']=issue
        return out,stats
