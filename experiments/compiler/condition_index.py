"""Conservative conditions for the explicit regular-file/implicit-directory VFS.

Inputs are the exact journals selected by successful native compilation/reuse,
not compiler depfiles. Missing lookups and directory membership remain explicit.
This is a local experimental representation, not a general POSIX replay format.
"""
import hashlib
import os
from pathlib import Path
import posixpath
import struct


class UnsupportedIndex(ValueError):pass


def canonical(path):
    if not path.startswith('/') or '\x00' in path or '\\' in path or path.startswith('//'):
        raise UnsupportedIndex('unsupported virtual path')
    path=posixpath.normpath(path)
    if len(path.encode())>4096:raise UnsupportedIndex('oversized path')
    return path


def prefixes(path):
    yield '/'
    for i,c in enumerate(path):
        if c=='/' and i>0:yield path[:i]
    if path!='/':yield path


def namespace_nodes(masks):
    nodes={'/':[0,(1<<64)-1]}  # InMemoryFileSystem has a root even for an empty view.
    for path,mask in masks.items():
        if canonical(path)!=path or path=='/' or not 0<=mask<1<<64:
            raise UnsupportedIndex('invalid namespace entry')
        node=nodes.setdefault(path,[0,0]);node[0]|=mask
        for parent in list(prefixes(path))[:-1]:
            if parent in masks:raise UnsupportedIndex('file/directory collision')
            nodes.setdefault(parent,[0,0])[1]|=mask
    if any(file_mask&dir_mask for file_mask,dir_mask in nodes.values()):
        raise UnsupportedIndex('file/directory collision')
    if len(nodes)>200000:raise UnsupportedIndex('namespace node limit')
    return nodes


def encode_namespace(masks):
    if not 0<len(masks)<=100000:raise UnsupportedIndex('namespace limit')
    namespace_nodes(masks)
    out=bytearray(b'GAIANS01'+struct.pack('<Q',len(masks)))
    for path,mask in sorted(masks.items()):
        name=path.encode();out+=struct.pack('<Q',len(name))+name+struct.pack('<Q',mask)
    if len(out)>4*1048576:raise UnsupportedIndex('namespace byte limit')
    return out


def selected_journals(store,result):
    keys=result.get('cache_keys',[]);pins=result.get('journal_sha256',[])
    if len(keys)!=len(pins) or not keys or any(not p for p in pins):
        raise UnsupportedIndex('missing selected journal identity')
    journals=[]
    for i,(key,pin) in enumerate(zip(keys,pins)):
        chosen=None
        for suffix in ('.gdo','.1.gdo','.2.gdo'):
            path=Path(store)/(key+suffix)
            if not path.is_file() or not 100<path.stat().st_size<=80*1048576+88:continue
            raw=path.read_bytes()
            if raw[:8]!=b'GAIADC01' or raw[8:40].hex()!=key:continue
            js,bs=struct.unpack_from('<QQ',raw,72)
            if js+bs!=len(raw)-88 or not 12<=js<=16*1048576:continue
            if hashlib.sha256(raw[8:40]+raw[72:]).digest()!=raw[40:72]:continue
            journal=raw[88:88+js]
            if hashlib.sha256(journal).hexdigest()!=pin:continue
            if hashlib.sha256(raw[88+js:]).hexdigest()!=result['object_sha256'][i]:continue
            chosen=journal;break
        if chosen is None:raise UnsupportedIndex('selected successful journal unavailable')
        journals.append(chosen)
    return journals


def decode_journal(raw):
    # Fingerprints are opaque to export: native replay validates SHA-256 (01)
    # or BLAKE3-256 (02); exported conditions retain their SHA-256 contract.
    if len(raw)<12 or raw[:8] not in (b'GAIAJR01',b'GAIAJR02'):raise UnsupportedIndex('journal header')
    count=struct.unpack_from('<I',raw,8)[0]
    if not 0<count<=65536:raise UnsupportedIndex('journal count')
    at=12;records=[]
    for _ in range(count):
        if at>len(raw)-38:raise UnsupportedIndex('journal framing')
        op,outcome,length=struct.unpack_from('<BBI',raw,at);at+=6
        if not 1<=op<=9 or outcome>1 or length>4096 or length>len(raw)-at-32:
            raise UnsupportedIndex('journal query')
        path=raw[at:at+length].decode('utf-8',errors='strict');at+=length+32
        if '\x00' in path:raise UnsupportedIndex('journal path')
        records.append((op,outcome,path))
    if at!=len(raw):raise UnsupportedIndex('journal trailing bytes')
    return records


def listing_digest(nodes,path,bit):
    children=[]
    for name,(file_mask,dir_mask) in nodes.items():
        if name!='/' and posixpath.dirname(name)==path:
            kind=1 if file_mask&bit else 2 if dir_mask&bit else 0
            if kind:children.append((name,kind))
    body=bytearray(b'GAIA-LIST-1'+struct.pack('<Q',len(children)))
    for name,kind in sorted(children):
        value=name.encode();body+=struct.pack('<Q',len(value))+value+bytes([kind])
    return hashlib.sha256(body).digest()


def build_index(journals,files,masks,cwd):
    if not 0<len(journals)<=64:raise UnsupportedIndex('job limit')
    cwd=canonical(cwd);nodes=namespace_nodes(masks);conditions={};hashes={};queries=0;routes={}
    def add(kind,path,bit,digest=bytes(32)):
        key=(kind,path,digest);conditions[key]=conditions.get(key,0)|bit
        if len(conditions)>65536:raise UnsupportedIndex('condition count limit')
    for job,journal in enumerate(journals):
        current=cwd;bit=1<<job;seen=set()
        for op,outcome,path in decode_journal(journal):
            queries+=1
            target=current if op==8 else canonical(posixpath.join(current,path))
            if target not in seen:
                seen.add(target)
                if target not in routes:routes[target]=[(name,nodes.get(name,(0,0))) for name in prefixes(target)]
                for name,(file_mask,dir_mask) in routes[target]:
                    kind=1 if file_mask&bit else 2 if dir_mask&bit else 0
                    digest=bytes(32)
                    if kind==1:
                        if name not in files:raise UnsupportedIndex('missing admitted bytes')
                        if name not in hashes:hashes[name]=hashlib.sha256(files[name]).digest()
                        digest=hashes[name]
                    add(kind,name,bit,digest)
            if op==6 and nodes.get(target,(0,0))[1]&bit:
                add(3,target,bit,listing_digest(nodes,target,bit))
            if op==9 and outcome==0:current=target
    return encode_conditions(conditions,files,len(hashes),queries)


def encode_conditions(conditions,files,positive_files,queries):
    out=bytearray(b'GAIACQ01'+struct.pack('<Q',len(conditions)))
    kinds={};file_stats={}
    for (kind,name,digest),jobs in sorted(conditions.items()):
        encoded=name.encode();size=sec=ns=mode=0
        if kind==1:
            st=os.stat(name);size=len(files[name]);sec,ns=divmod(st.st_mtime_ns,10**9);mode=st.st_mode
            if st.st_size!=size or hashlib.sha256(Path(name).read_bytes()).digest()!=digest:
                raise UnsupportedIndex('physical file differs from compiler input')
            file_stats[name]=st.st_mtime_ns
        out+=bytes([kind])+struct.pack('<QQ',jobs,len(encoded))+encoded
        out+=struct.pack('<QQQQ',size,sec%(1<<64),ns,mode)+digest
        kinds[str(kind)]=kinds.get(str(kind),0)+1
    out+=hashlib.sha256(out).digest()
    if len(out)>8*1048576:raise UnsupportedIndex('condition byte limit')
    return out,dict(queries=queries,conditions=len(conditions),positive_files=positive_files,kinds=kinds,bytes=len(out))
