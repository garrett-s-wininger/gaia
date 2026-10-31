"""Bounded resolved manifests: generic JSON/binary views, no dependency semantics."""
from collections.abc import Mapping,Sequence
import json
from pathlib import Path
import struct
import time

import cache_store as cache
import pipeline_transport as transport
import transfer as t

MAGIC=b'GALOCK01'
HEADER=struct.Struct('!8s10I')
STRING=struct.Struct('!II');PACKAGE=struct.Struct('!III');ARTIFACT=struct.Struct('!HHIIQ');ASSOC=struct.Struct('!IIII');META=struct.Struct('!III')
NONE=0xffffffff
MAX_RECORDS=t.MAX_OBJECTS;MAX_STRINGS=65536;MAX_TEXT=4096;MAX_BYTES=t.MAX_MANIFEST


def text(value):
    return isinstance(value,str) and len(value.encode('utf-8'))<=MAX_TEXT


def validate_document(doc):
    if not isinstance(doc,dict) or set(doc)!={'version','packages','artifacts','associations','metadata'} or type(doc['version']) is not int or doc['version']!=1:raise t.TransferError('resolved lock version/schema')
    if any(not isinstance(doc[k],list) or len(doc[k])>MAX_RECORDS for k in ('packages','artifacts','associations','metadata')):raise t.TransferError('resolved lock table bounds')
    seen=set()
    for row in doc['packages']:
        if not isinstance(row,dict) or set(row)!={'ecosystem','name','version'} or not all(text(row[k]) for k in row) or not row['ecosystem'] or not row['name']:raise t.TransferError('package identity')
        key=(row['ecosystem'],row['name'],row['version'])
        if key in seen:raise t.TransferError('duplicate package identity')
        seen.add(key)
    seen=set()
    for row in doc['artifacts']:
        if not isinstance(row,dict) or set(row)!={'algorithm','digest','size'} or row['algorithm']!='sha256' or not isinstance(row['digest'],str) or not t.HEX.fullmatch(row['digest']) or type(row['size']) is not int or not 0<=row['size']<1<<64:raise t.TransferError('unsupported content descriptor')
        if row['digest'] in seen:raise t.TransferError('duplicate content identity')
        seen.add(row['digest'])
    for row in doc['associations']:
        if not isinstance(row,dict) or set(row)!={'package','artifact','role','label'} or type(row['package']) is not int or row['package']!=NONE and not 0<=row['package']<len(doc['packages']) or type(row['artifact']) is not int or not 0<=row['artifact']<len(doc['artifacts']) or not text(row['role']) or not text(row['label']):raise t.TransferError('artifact association')
    for row in doc['metadata']:
        if not isinstance(row,dict) or set(row)!={'ecosystem','role','artifact'} or not text(row['ecosystem']) or not text(row['role']) or type(row['artifact']) is not int or not 0<=row['artifact']<len(doc['artifacts']):raise t.TransferError('metadata association')


def encode_json(doc):validate_document(doc);body=t.encode(doc);_bound(body);return body


def _bound(body):
    if not 0<len(body)<=MAX_BYTES:raise t.TransferError('resolved lock byte bound')


def encode_binary(doc):
    validate_document(doc);strings=set()
    for row in doc['packages']:strings.update(row.values())
    for row in doc['associations']:strings.update((row['role'],row['label']))
    for row in doc['metadata']:strings.update((row['ecosystem'],row['role']))
    strings=sorted(strings,key=lambda v:v.encode());ids={v:i for i,v in enumerate(strings)}
    if len(strings)>MAX_STRINGS:raise t.TransferError('interned string count')
    pool=bytearray();table=bytearray()
    for value in strings:
        raw=value.encode();table.extend(STRING.pack(len(pool),len(raw)));pool.extend(raw)
    packages=b''.join(PACKAGE.pack(ids[r['ecosystem']],ids[r['name']],ids[r['version']]) for r in doc['packages'])
    digests=bytearray();artifacts=bytearray()
    for row in doc['artifacts']:
        digest=bytes.fromhex(row['digest']);artifacts.extend(ARTIFACT.pack(1,0,len(digests),len(digest),row['size']));digests.extend(digest)
    associations=b''.join(ASSOC.pack(r['package'],r['artifact'],ids[r['role']],ids[r['label']]) for r in doc['associations'])
    metadata=b''.join(META.pack(ids[r['ecosystem']],ids[r['role']],r['artifact']) for r in doc['metadata'])
    body=HEADER.pack(MAGIC,1,0,len(strings),len(doc['packages']),len(doc['artifacts']),len(doc['associations']),len(doc['metadata']),len(pool),len(digests),0)+table+packages+artifacts+associations+metadata+pool+digests
    _bound(body);return body


class Content(Mapping):
    def __init__(self,view,index):self.view,self.index=view,index;self._digest=None
    def __iter__(self):return iter(('sha256','size'))
    def __len__(self):return 2
    def __getitem__(self,key):
        if key=='size':return self.view.artifact(self.index)[1]
        if key=='sha256':
            if self._digest is None:self._digest=self.view.artifact(self.index)[0]
            return self._digest
        raise KeyError(key)


class Contents(Sequence):
    def __init__(self,view):self.view=view
    def __len__(self):return self.view.counts[1]
    def __getitem__(self,index):
        if isinstance(index,slice):return [self[i] for i in range(*index.indices(len(self))) ]
        if not 0<=index<len(self):raise IndexError(index)
        return Content(self.view,index)


class JSONView:
    def __init__(self,body,pin):
        _bound(body)
        if t.digest(body)!=pin:raise t.TransferError('resolved lock pin')
        self.document=json.loads(body,object_pairs_hook=t._pairs);validate_document(self.document)
        self.counts=tuple(len(self.document[k]) for k in ('packages','artifacts','associations','metadata'));self.contents=Contents(self)
    def artifact(self,i):row=self.document['artifacts'][i];return row['digest'],row['size']
    def package(self,i):return tuple(self.document['packages'][i][k] for k in ('ecosystem','name','version'))
    def association(self,i):return tuple(self.document['associations'][i][k] for k in ('package','artifact','role','label'))
    def metadata(self,i):return tuple(self.document['metadata'][i][k] for k in ('ecosystem','role','artifact'))


class BinaryView:
    def __init__(self,body,pin):
        _bound(body)
        if not isinstance(body,bytes):
            body=bytes(memoryview(body)[:MAX_BYTES+1]);_bound(body)
        if t.digest(body)!=pin:raise t.TransferError('resolved lock pin')
        if len(body)<HEADER.size:raise t.TransferError('resolved lock truncated')
        magic,version,flags,ns,np,na,ne,nm,sp,dp,reserved=HEADER.unpack_from(body)
        if magic!=MAGIC or version!=1 or flags or reserved or ns>MAX_STRINGS or max(np,na,ne,nm)>MAX_RECORDS:raise t.TransferError('resolved lock header/version/bounds')
        self.body=body;self.counts=(np,na,ne,nm);self.ns=ns
        self.starts=(HEADER.size,HEADER.size+ns*STRING.size,HEADER.size+ns*STRING.size+np*PACKAGE.size,HEADER.size+ns*STRING.size+np*PACKAGE.size+na*ARTIFACT.size,HEADER.size+ns*STRING.size+np*PACKAGE.size+na*ARTIFACT.size+ne*ASSOC.size)
        self.pool=self.starts[4]+nm*META.size;self.digest_pool=self.pool+sp;self.digest_bytes=dp;self.string_bytes=sp
        if self.digest_pool+dp!=len(body):raise t.TransferError('resolved lock table/pool geometry')
        end=0;previous=None
        for i in range(ns):
            offset,size=STRING.unpack_from(body,self.starts[0]+i*8)
            if offset!=end or size>MAX_TEXT or offset+size>sp:raise t.TransferError('resolved lock string bounds')
            raw=body[self.pool+offset:self.pool+offset+size]
            try:raw.decode('utf-8')
            except UnicodeError as error:raise t.TransferError('resolved lock UTF8') from error
            if previous is not None and previous>=raw:raise t.TransferError('resolved lock string interning/order')
            previous=raw;end=offset+size
        if end!=sp:raise t.TransferError('unused string bytes')
        identities=set()
        for i in range(np):
            ids=PACKAGE.unpack_from(body,self.starts[1]+i*12)
            for sid in ids:self._sid(sid)
            if not self.string(ids[0]) or not self.string(ids[1]) or ids in identities:raise t.TransferError('resolved package identity')
            identities.add(ids)
        seen=set();end=0
        for i in range(na):
            alg,flags,offset,size,total=ARTIFACT.unpack_from(body,self.starts[2]+i*ARTIFACT.size)
            if alg!=1 or flags or size!=32 or offset!=end or offset+size>dp:raise t.TransferError('resolved descriptor algorithm/offset')
            digest=body[self.digest_pool+offset:self.digest_pool+offset+size]
            if digest in seen:raise t.TransferError('duplicate content identity')
            seen.add(digest);end=offset+size
        if end!=dp:raise t.TransferError('unused digest bytes')
        for i in range(ne):
            package,artifact,role,label=ASSOC.unpack_from(body,self.starts[3]+i*16)
            if package!=NONE and package>=np or artifact>=na:raise t.TransferError('resolved association bounds')
            self._sid(role);self._sid(label)
        for i in range(nm):
            ecosystem,role,artifact=META.unpack_from(body,self.starts[4]+i*12)
            if artifact>=na:raise t.TransferError('resolved metadata bounds')
            self._sid(ecosystem);self._sid(role)
        self.contents=Contents(self)
    def _sid(self,i):
        if not 0<=i<self.ns:raise t.TransferError('resolved string ID')
    def string(self,i):
        self._sid(i);offset,size=STRING.unpack_from(self.body,self.starts[0]+i*8);return self.body[self.pool+offset:self.pool+offset+size].decode()
    def artifact(self,i):
        if not 0<=i<self.counts[1]:raise IndexError(i)
        alg,flags,offset,size,total=ARTIFACT.unpack_from(self.body,self.starts[2]+i*ARTIFACT.size)
        return self.body[self.digest_pool+offset:self.digest_pool+offset+size].hex(),total
    def package(self,i):
        if not 0<=i<self.counts[0]:raise IndexError(i)
        return tuple(self.string(s) for s in PACKAGE.unpack_from(self.body,self.starts[1]+i*12))
    def association(self,i):
        if not 0<=i<self.counts[2]:raise IndexError(i)
        package,artifact,role,label=ASSOC.unpack_from(self.body,self.starts[3]+i*16);return package,artifact,self.string(role),self.string(label)
    def metadata(self,i):
        if not 0<=i<self.counts[3]:raise IndexError(i)
        ecosystem,role,artifact=META.unpack_from(self.body,self.starts[4]+i*12);return self.string(ecosystem),self.string(role),artifact


def parse(body,pin,kind):return {'json':JSONView,'binary':BinaryView}[kind](body,pin)


def acquire(url,body,pin,root,kind):
    begin=time.perf_counter();view=parse(body,pin,kind);parsed=time.perf_counter();objects=list(view.contents)
    if sum(o['size'] for o in objects)>t.MAX_PACK:raise t.TransferError('local cache content quota')
    root=Path(root);store=cache.Packed(root);client=None;hashed=len(body);hits=set()
    try:
        for key,value in store.iter_available(objects):
            hashed+=len(value)
            if t.digest(value)==key:hits.add(key)
            else:store.invalidate(key)
        missing=[obj for obj in objects if obj['sha256'] not in hits];store.prepare(missing);checked=time.perf_counter()
        if missing:
            client=transport.Client(url)
            for obj,payload in client.stream_batch(missing):
                hashed+=len(payload)
                if len(payload)!=obj['size'] or t.digest(payload)!=obj['sha256']:raise t.TransferError('generic streamed content integrity')
                store.put_verified(obj,payload)
        store.finish();published=time.perf_counter()
        lock_path=root/('sha256-'+pin+'.resolved')
        if not lock_path.exists():t.atomic_write(lock_path,body)
        t.atomic_write(root/'ready.json',t.encode(dict(version=1,lock='sha256:'+pin,objects=sorted(obj['sha256'] for obj in objects))))
        return view,dict(seconds=time.perf_counter()-begin,lock_parse_seconds=parsed-begin,cache_check_seconds=checked-parsed,transfer_admit_seconds=published-checked,requests=client.requests if client else 0,manifest_requests=0,hash_bytes=hashed,cache_hits=len(hits),objects=len(objects),transfer_bytes=sum(o['size'] for o in missing),store=dict(store.stats))
    except BaseException:(root/'ready.json').unlink(missing_ok=True);store.abort();raise
    finally:
        if client:client.close()
        store.close()


def python_adapter(view,root):
    """Explicit ecosystem adaptation; decoding/derived lock construction is charged."""
    contexts=[view.metadata(i)[2] for i in range(view.counts[3]) if view.metadata(i)[:2]==('python','context')]
    if len(contexts)!=1:raise t.TransferError('Python context descriptor')
    obj=view.contents[contexts[0]];store=cache.Packed(Path(root))
    try:
        available=list(store.iter_available([obj]))
        if len(available)!=1 or t.digest(available[0][1])!=obj['sha256']:raise t.TransferError('Python context integrity')
        context=json.loads(bytes(available[0][1]),object_pairs_hook=t._pairs)
    finally:store.close()
    files=[]
    for i in range(view.counts[2]):
        package,artifact,role,label=view.association(i)
        if role=='python-file':
            content=view.contents[artifact];files.append(dict(name=label,sha256=content['sha256'],size=content['size']))
    import locked_python
    body=t.encode(dict(version=1,algorithm='sha256',files=files,versions=context['versions'],resources=context['resources']))
    locked_python.parse_lock(body,t.digest(body));return body
