"""Retained immutable logical-name/offset index, shared by pack and ZIP payloads."""
from collections.abc import Mapping,Set
import hashlib
import json
import mmap
import os
from pathlib import Path
import struct
import sys
import time
import zlib

import cache_store
import locked_python as locked
import transfer as t

MAGIC=b'GAPYIDX1'
HEADER=struct.Struct('!8s7I')  # version, metadata bytes, files, modules, dirs, children, strings
FILE=struct.Struct('!4I2Q32sI')
MODULE=struct.Struct('!4I')
DIRECTORY=struct.Struct('!5I')
CHILD=struct.Struct('!I')
MAX_INDEX=4*1024*1024


def build(root,lock_body,lock_pin,index_path,kind,zip_path=None,zip_index=None,zip_pin=None):
    begin=time.perf_counter();root=Path(root);lock,logical_objects=locked.parse_lock(lock_body,lock_pin)
    sources=[];locators={};owner=None;fd=None
    try:
        if kind=='pack':
            owner=cache_store.Packed(root)
            for key,desc in sorted(owner.packs.items()):sources.append((str((owner.data_dir/(key+'.gap')).resolve()),desc['digest']))
            ids={Path(path).stem:i for i,(path,_) in enumerate(sources)}
            for obj in owner.entries.values():locators[obj['sha256']]=(ids[obj['pack']],obj['offset'],obj['size'])
        elif kind=='zip':
            sys.path.insert(0,str(Path(__file__).parent.parent/'python/dependency_bundles'))
            from precomputed_index import IndexedBundleReader
            owner=IndexedBundleReader(zip_path,zip_index,index_sha256=zip_pin,verify='local')
            import binary_index
            sources=[(str(Path(zip_path).resolve()),binary_index.decode(Path(zip_index).read_bytes())['archive_sha256'])]
        else:raise ValueError('kind')
        raw=[];metadata=[]
        for path,digest in sources:
            stream=open(path,'rb');mapping=mmap.mmap(stream.fileno(),0,access=mmap.ACCESS_READ);raw.append((stream,mapping))
            stat=os.fstat(stream.fileno());metadata.append(dict(path=os.path.relpath(path,root),sha256=digest,size=stat.st_size,identity=[stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns]))
        names=[];modules=[];dirs={'':dict(package=True,children=[])};verified={}
        for row in sorted(lock['files'],key=lambda x:x['name'].encode()):
            name=row['name'];key=row['sha256']
            container,offset,size=locators[key] if kind=='pack' else (0,*owner.ranges[name])
            if size!=row['size']:raise t.TransferError('consumer index logical geometry')
            # Both representations independently validate all logical bytes during index admission.
            if key not in verified:
                body=raw[container][1][offset:offset+size]
                if len(body)!=size or t.digest(body)!=key:raise t.TransferError('consumer index logical digest')
                verified[key]=zlib.crc32(body)
            file_id=len(names);names.append((name,container,offset,size,key,verified[key]))
            parent=Path(name).parent.as_posix()
            for part in Path(name).parents:
                relative=part.as_posix()
                if relative!='.':dirs.setdefault(relative,dict(package=False,children=[]))
            if name.endswith(('.py','.pyc')):
                stem=name[:-4] if name.endswith('.pyc') else name[:-3];package=stem.endswith('/__init__')
                if package:stem=stem[:-9]
                fullname=stem.replace('/','.');modules.append((fullname,file_id,package))
                if package:dirs.setdefault(stem,dict(package=False,children=[]))['package']=True
        modules.sort(key=lambda row:row[0].encode())
        if len({m[0] for m in modules})!=len(modules):raise t.TransferError('consumer index mixed modules')
        for ordinal,(fullname,_,package) in enumerate(modules):
            parent=fullname.rpartition('.')[0].replace('.','/')
            if parent in dirs:dirs[parent]['children'].append(ordinal)
        strings=bytearray()
        def text(value):
            encoded=value.encode();offset=len(strings);strings.extend(encoded);return offset,len(encoded)
        files=bytearray();modtab=bytearray();dirtab=bytearray();children=[]
        for name,container,offset,size,digest,crc in names:files.extend(FILE.pack(*text(name),container,0,offset,size,bytes.fromhex(digest),crc))
        for name,file_id,package in modules:modtab.extend(MODULE.pack(*text(name),file_id,int(package)))
        for path,value in sorted(dirs.items(),key=lambda row:row[0].encode()):
            start=len(children);children+=value['children'];dirtab.extend(DIRECTORY.pack(*text(path),int(value['package']),start,len(value['children'])))
        meta=t.encode(dict(version=1,lock_sha256=lock_pin,kind=kind,containers=metadata))
        body=HEADER.pack(MAGIC,1,len(meta),len(names),len(modules),len(dirs),len(children),len(strings))+meta+files+modtab+dirtab+b''.join(CHILD.pack(i) for i in children)+strings
        if len(body)>MAX_INDEX:raise t.TransferError('consumer index bound')
        # Fully validate tables once before the derived pin can be trusted on later opens.
        t.atomic_write(Path(index_path),body);pin=t.digest(body)
        check=Reader(root,index_path,pin,lock_pin,validate_all=True);check.close()
        return dict(pin=pin,bytes=len(body),seconds=time.perf_counter()-begin,files=len(names),modules=len(modules),logical_validation_bytes=sum(row['size'] for row in logical_objects))
    finally:
        for stream,mapping in locals().get('raw',[]):mapping.close();stream.close()
        if owner:owner.close()


class Table(Mapping):
    def __init__(self,reader,kind):self.reader,self.kind=reader,kind
    def __len__(self):return self.reader.counts[self.kind]
    def __iter__(self):
        for i in range(len(self)):yield self.reader.name(self.kind,i).decode()
    def __getitem__(self,key):
        i=self.reader.lookup(self.kind,key)
        if i<0:raise KeyError(key)
        row=self.reader.row(self.kind,i)
        if self.kind==0:return i
        if self.kind==1:return self.reader.name(0,row[2]).decode(),bool(row[3])
        return i


class Directories(Set):
    def __init__(self,r):self.r=r
    def __len__(self):return self.r.counts[2]
    def __iter__(self):
        for name in self.r.tables[2]:yield name+'/' if name else ''
    def __contains__(self,path):return isinstance(path,str) and self.r.lookup(2,path.rstrip('/'))>=0


class Packages(Mapping):
    def __init__(self,r):self.r=r
    def __len__(self):return sum(1 for _ in self)
    def __iter__(self):
        for i in range(self.r.counts[2]):
            if self.r.row(2,i)[2]:yield self.r.name(2,i).decode()
    def __getitem__(self,path):
        i=self.r.lookup(2,path)
        if i<0 or not self.r.row(2,i)[2]:raise KeyError(path)
        return path.replace('/','.')


class Children(Mapping):
    def __init__(self,r):self.r=r
    def __len__(self):return len(self.r.precomputed_packages)
    def __iter__(self):return iter(self.r.precomputed_packages)
    def __getitem__(self,path):
        self.r.precomputed_packages[path];i=self.r.lookup(2,path);row=self.r.row(2,i);result=[]
        for j in range(row[3],row[3]+row[4]):
            module_id=CHILD.unpack_from(self.r.mapping,self.r.children_start+j*4)[0]
            member=self.r.row(1,module_id);result.append((self.r.name(1,module_id).decode().rpartition('.')[2],bool(member[3])))
        return tuple(result)


class Reader:
    def __init__(self,root,index_path,index_pin,lock_pin,validate_all=False):
        begin=time.perf_counter();self.stream=None;self.mapping=None;self.data=[];self.closed=False
        self.filename=str(root);self.reads=0;self.read_bytes=0;self.read_seconds=0;self.hash_seconds=0
        try:
            body=cache_store.read_bounded(Path(index_path),MAX_INDEX)
            if t.digest(body)!=index_pin:raise t.TransferError('consumer index integrity')
            self.stream=open(index_path,'rb');self.mapping=mmap.mmap(self.stream.fileno(),0,access=mmap.ACCESS_READ)
            if self.mapping[:]!=body:raise t.TransferError('consumer index changed')
            if len(body)<HEADER.size:raise t.TransferError('consumer index truncated')
            magic,version,meta_size,n,m,d,c,s=HEADER.unpack_from(body)
            if magic!=MAGIC or version!=1 or max(n,m,d,c)>t.MAX_OBJECTS*2 or meta_size>t.MAX_MANIFEST:raise t.TransferError('consumer index header/bounds')
            self.counts=(n,m,d);self.offsets=(HEADER.size+meta_size,HEADER.size+meta_size+n*FILE.size,HEADER.size+meta_size+n*FILE.size+m*MODULE.size)
            self.children_start=self.offsets[2]+d*DIRECTORY.size;self.string_start=self.children_start+c*4;self.string_size=s;self.child_count=c
            if self.string_start+s!=len(body):raise t.TransferError('consumer index geometry')
            meta=json.loads(body[HEADER.size:HEADER.size+meta_size],object_pairs_hook=t._pairs)
            if set(meta)!={'version','lock_sha256','kind','containers'} or meta['version']!=1 or meta['lock_sha256']!=lock_pin or meta['kind'] not in ('pack','zip') or not 1<=len(meta['containers'])<=cache_store.MAX_PACKS:raise t.TransferError('consumer index binding')
            self.meta=meta
            for desc in meta['containers']:
                if not isinstance(desc,dict) or set(desc)!={'path','sha256','size','identity'} or not isinstance(desc['path'],str) or not isinstance(desc['sha256'],str) or not t.HEX.fullmatch(desc['sha256']) or type(desc['size']) is not int or not isinstance(desc['identity'],list) or len(desc['identity'])!=5 or any(type(value) is not int or value<0 for value in desc['identity']):raise t.TransferError('consumer container descriptor')
                relative=desc['path']
                if Path(relative).is_absolute() or '..' in Path(relative).parts:raise t.TransferError('consumer container path')
                stream=open(Path(root)/relative,'rb');stat=os.fstat(stream.fileno());identity=[stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns]
                if identity!=desc['identity'] or stat.st_size!=desc['size'] or not 0<stat.st_size<=t.MAX_PACK+8:stream.close();raise t.TransferError('consumer data identity')
                self.data.append((stream,mmap.mmap(stream.fileno(),0,access=mmap.ACCESS_READ)))
            self.tables=[Table(self,i) for i in range(3)];self.entries=self.tables[0];self.precomputed_modules=self.tables[1]
            self.directories=Directories(self);self.precomputed_packages=Packages(self);self.precomputed_children=Children(self)
            if validate_all:
                for kind in range(3):
                    previous=None
                    for i in range(self.counts[kind]):
                        name=self.name(kind,i);name.decode()
                        if previous is not None and previous>=name:raise t.TransferError('consumer unsorted/duplicate table')
                        previous=name;row=self.row(kind,i)
                        if kind==0:
                            if row[2]>=len(self.data) or row[3] or row[4]+row[5]>len(self.data[row[2]][1]):raise t.TransferError('consumer file bounds')
                        elif kind==1:
                            if row[2]>=n or row[3] not in (0,1):raise t.TransferError('consumer module bounds')
                        elif row[2] not in (0,1) or row[3]+row[4]>c:raise t.TransferError('consumer children bounds')
                for j in range(c):
                    if CHILD.unpack_from(self.mapping,self.children_start+j*4)[0]>=m:raise t.TransferError('consumer child id')
            self.native_timings=dict(setup_seconds=time.perf_counter()-begin,read_seconds=0,hash_seconds=0,reads=0,read_bytes=0,index_bytes=len(body),integrity_policy='sha256+crc32-every-read')
        except BaseException:self.close();raise
    def row(self,kind,i):
        if self.closed or not 0<=i<self.counts[kind]:raise t.TransferError('consumer row bounds/lifetime')
        return (FILE,MODULE,DIRECTORY)[kind].unpack_from(self.mapping,self.offsets[kind]+i*(FILE,MODULE,DIRECTORY)[kind].size)
    def name(self,kind,i):
        offset,size=self.row(kind,i)[:2]
        if offset+size>self.string_size:raise t.TransferError('consumer string bounds')
        return self.mapping[self.string_start+offset:self.string_start+offset+size]
    def lookup(self,kind,name):
        if not isinstance(name,str):return -1
        encoded=name.encode();lo,hi=0,self.counts[kind]
        while lo<hi:
            mid=(lo+hi)//2;value=self.name(kind,mid)
            if value<encoded:lo=mid+1
            elif value>encoded:hi=mid
            else:return mid
        return -1
    def read(self,name):
        begin=time.perf_counter();row=self.lookup(0,name)
        if row<0:raise KeyError(name)
        _,_,container,flags,offset,size,digest,crc=self.row(0,row)
        if container>=len(self.data) or flags or offset+size>len(self.data[container][1]):raise t.TransferError('consumer data bounds')
        body=self.data[container][1][offset:offset+size];hashed=time.perf_counter()
        if hashlib.sha256(body).digest()!=digest or zlib.crc32(body)!=crc:raise t.TransferError('consumer SHA256/CRC integrity')
        end=time.perf_counter();self.native_timings['read_seconds']+=hashed-begin;self.native_timings['hash_seconds']+=end-hashed;self.native_timings['reads']+=1;self.native_timings['read_bytes']+=len(body)
        return body
    def close(self):
        if self.closed:return
        self.closed=True
        for stream,mapping in self.data:mapping.close();stream.close()
        self.data.clear()
        if self.mapping is not None:self.mapping.close()
        if self.stream is not None:self.stream.close()


def provider_type():
    from indexed_path_loader import IndexedPathProvider
    from persistent_zip_loader import PersistentZipProvider
    from native_catalog import RootedMap
    class CompactProvider(IndexedPathProvider):
        def open_archive(self):
            if self._closed:raise ValueError('compact mount closed')
            archive=PersistentZipProvider.open_archive(self)
            if not self._indexed:
                self.packages=RootedMap(self.archive_path,archive.precomputed_packages);self.children=RootedMap(self.archive_path,archive.precomputed_children);self._indexed=True
            return archive
    return CompactProvider
