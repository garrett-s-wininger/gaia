"""Research cache layouts behind one logical-byte interface; Linux local lease."""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import struct
import threading

import transfer as t

PACK_MAGIC=b'GAPK0001'
INDEX_MAGIC=b'GAIX0001'
MAX_PACKS=8
MAX_DATA=t.MAX_PACK
MAX_INDEX=t.MAX_MANIFEST+16
READ_SPAN=4*1024*1024


class UnsupportedStore(t.TransferError):pass
class QuotaError(t.TransferError):pass
class CorruptIndex(t.TransferError):pass


def descriptor(body):return dict(algorithm='sha256',digest=t.digest(body),size=len(body))


def valid_descriptor(value,limit):
    return (isinstance(value,dict) and set(value)=={'algorithm','digest','size'} and value['algorithm']=='sha256' and
            isinstance(value['digest'],str) and t.HEX.fullmatch(value['digest']) and type(value['size']) is int and 0<=value['size']<=limit)


def read_bounded(path,limit):
    with path.open('rb') as stream:
        size=os.fstat(stream.fileno()).st_size
        if not 0<=size<=limit:raise CorruptIndex('cache metadata size')
        body=stream.read(size+1)
    if len(body)!=size:raise CorruptIndex('cache metadata changed/truncated')
    return body


class Lease:
    def __init__(self,root):
        root.mkdir(parents=True,exist_ok=True);self.stream=(root/'cache.lock').open('a+b')
        try:fcntl.flock(self.stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:self.stream.close();raise t.TransferError('cache busy; one writer/access transaction at a time') from None
    def close(self):self.stream.close()


def stats():
    return dict(atomic_publications=0,data_read_bytes=0,data_write_bytes=0,representation_hash_bytes=0,
                metadata_write_bytes=0,data_opens=0,data_reads=0,compactions=0,compaction_hash_bytes=0,corrupt_index=False,
                packs=0,index_bytes=0,live_payload_bytes=0)


class Files:
    def __init__(self,root):
        self.root=Path(root);self.lease=Lease(self.root);self.stats=stats();self.write_lock=threading.Lock()
        self.objects=self.root/'objects'/'sha256';self.objects.mkdir(parents=True,exist_ok=True)
    def iter_available(self,objects):
        for obj in objects:
            path=self.objects/obj['sha256']
            try:
                with path.open('rb') as stream:
                    self.stats['data_opens']+=1
                    if os.fstat(stream.fileno()).st_size!=obj['size']:continue
                    body=stream.read(obj['size']+1);self.stats['data_reads']+=1;self.stats['data_read_bytes']+=len(body)
                if len(body)==obj['size']:yield obj['sha256'],memoryview(body)
            except FileNotFoundError:continue
    def invalidate(self,key):pass
    def prepare(self,objects):pass  # Retains the original file-control policy; no global disk quota/index.
    def put_verified(self,obj,body):
        t.atomic_write(self.objects/obj['sha256'],body)
        with self.write_lock:self.stats['atomic_publications']+=1;self.stats['data_write_bytes']+=len(body)
    def finish(self):pass
    def abort(self):pass
    def close(self):self.lease.close()


class Packed:
    def __init__(self,root):
        self.root=Path(root);self.lease=Lease(self.root);self.stats=stats();self.entries={};self.packs={};self.index_id=None
        self.write_lock=threading.Lock();self.stage=None;self.stage_entries={};self.stage_size=0;self.hasher=None;self.failed=False;self.compact=False
        self.data_dir=self.root/'packs';self.index_dir=self.root/'indexes';self.staging=self.root/'staging'
        try:
            for directory in (self.data_dir,self.index_dir,self.staging):directory.mkdir(exist_ok=True)
            try:self._load()
            except UnsupportedStore:raise
            except (CorruptIndex,ValueError,UnicodeError,KeyError,TypeError):self.entries={};self.packs={};self.index_id=None;self.stats['corrupt_index']=True
            self._cleanup();self._update_stats()
        except BaseException:self.lease.close();raise
    def _load(self):
        head=self.root/'head.json'
        if not head.exists():return
        try:value=json.loads(read_bounded(head,4096),object_pairs_hook=t._pairs)
        except (ValueError,UnicodeError) as error:raise CorruptIndex('head JSON') from error
        if not isinstance(value,dict) or set(value)!={'version','index'}:raise CorruptIndex('head schema')
        if type(value['version']) is not int or value['version']!=1:raise UnsupportedStore('unsupported local head version')
        desc=value['index']
        if isinstance(desc,dict) and desc.get('algorithm','sha256')!='sha256':raise UnsupportedStore('unsupported index digest algorithm')
        if not valid_descriptor(desc,MAX_INDEX):raise CorruptIndex('head descriptor')
        try:body=read_bounded(self.index_dir/(desc['digest']+'.gai'),MAX_INDEX)
        except FileNotFoundError:raise CorruptIndex('missing index') from None
        self.stats['representation_hash_bytes']+=len(body)
        if len(body)!=desc['size'] or t.digest(body)!=desc['digest'] or len(body)<16:raise CorruptIndex('index integrity')
        if body[:8]!=INDEX_MAGIC:
            if body[:4]==b'GAIX':raise UnsupportedStore('unsupported local index version')
            raise CorruptIndex('index magic')
        if struct.unpack_from('!Q',body,8)[0]!=len(body)-16:raise CorruptIndex('index framing')
        value=json.loads(body[16:],object_pairs_hook=t._pairs)
        if not isinstance(value,dict) or set(value)!={'version','digest_algorithm','packs','objects'}:raise CorruptIndex('index schema')
        if type(value['version']) is not int or value['version']!=1 or value['digest_algorithm']!='sha256':raise UnsupportedStore('unsupported local index schema/algorithm')
        if not isinstance(value['packs'],list) or len(value['packs'])>MAX_PACKS or not isinstance(value['objects'],list) or len(value['objects'])>t.MAX_OBJECTS:raise CorruptIndex('index bounds')
        packs={};entries={};spans={};live=0
        for pack in value['packs']:
            if isinstance(pack,dict) and pack.get('algorithm','sha256')!='sha256':raise UnsupportedStore('unsupported pack digest algorithm')
            if not valid_descriptor(pack,MAX_DATA+len(PACK_MAGIC)) or pack['size']<len(PACK_MAGIC) or pack['digest'] in packs:raise CorruptIndex('pack descriptor')
            packs[pack['digest']]=pack
        if sum(p['size'] for p in packs.values())>MAX_DATA+len(PACK_MAGIC)*MAX_PACKS:raise CorruptIndex('physical cache quota')
        for obj in value['objects']:
            if not isinstance(obj,dict) or set(obj)!={'sha256','size','pack','offset'}:raise CorruptIndex('local object schema')
            key=obj['sha256'];pack=obj['pack'];size=obj['size'];offset=obj['offset']
            if not isinstance(key,str) or not t.HEX.fullmatch(key) or key in entries or not isinstance(pack,str) or pack not in packs:raise CorruptIndex('local object identity')
            if type(size) is not int or type(offset) is not int or size<0 or offset<len(PACK_MAGIC) or size>packs[pack]['size']-offset:raise CorruptIndex('local object geometry')
            live+=size;entries[key]=obj;spans.setdefault(pack,[]).append((offset,offset+size))
        if live>MAX_DATA:raise CorruptIndex('logical cache quota')
        for ranges in spans.values():
            end=len(PACK_MAGIC)
            for start,stop in sorted(ranges):
                if start<end:raise CorruptIndex('overlapping local objects')
                end=stop
        self.entries=entries;self.packs=packs;self.index_id=desc['digest'];self.stats['index_bytes']=len(body)
    def _scan(self,directory,limit):
        result=[]
        with os.scandir(directory) as stream:
            for entry in stream:
                if len(result)>=limit:raise QuotaError('cache recovery entry bound')
                if not entry.is_file(follow_symlinks=False):raise QuotaError('unexpected cache entry')
                result.append(Path(entry.path))
        return result
    def _cleanup(self):
        for path in self._scan(self.staging,3):
            if path.name not in ('data.tmp','index.tmp','head.tmp'):raise QuotaError('unexpected staging file')
            path.unlink()
        for path in self._scan(self.data_dir,MAX_PACKS+1):
            if path.suffix!='.gap' or not t.HEX.fullmatch(path.stem):raise QuotaError('unexpected pack file')
            if path.stem not in self.packs:path.unlink()
        for path in self._scan(self.index_dir,2):
            if path.suffix!='.gai' or not t.HEX.fullmatch(path.stem):raise QuotaError('unexpected index file')
            if path.stem!=self.index_id:path.unlink()
    def _update_stats(self):
        self.stats.update(packs=len(self.packs),live_payload_bytes=sum(obj['size'] for obj in self.entries.values()))
    def iter_available(self,objects):
        by_pack={}
        for obj in objects:
            saved=self.entries.get(obj['sha256'])
            if saved is not None and saved['size']==obj['size']:by_pack.setdefault(saved['pack'],[]).append(saved)
        for pack,items in by_pack.items():
            try:fd=os.open(self.data_dir/(pack+'.gap'),os.O_RDONLY)
            except FileNotFoundError:continue
            self.stats['data_opens']+=1
            try:
                expected=self.packs[pack]['size']
                if os.fstat(fd).st_size!=expected:continue
                magic=os.pread(fd,len(PACK_MAGIC),0);self.stats['data_reads']+=1;self.stats['data_read_bytes']+=len(magic)
                if magic!=PACK_MAGIC:continue
                groups=[]
                for obj in sorted(items,key=lambda value:value['offset']):
                    if obj['size']==0:yield obj['sha256'],memoryview(b'');continue
                    start=obj['offset'];end=start+obj['size']
                    if groups and start==groups[-1][1] and end-groups[-1][0]<=READ_SPAN:
                        groups[-1][1]=end;groups[-1][2].append(obj)
                    else:groups.append([start,end,[obj]])
                for start,end,members in groups:
                    body=os.pread(fd,end-start,start);self.stats['data_reads']+=1;self.stats['data_read_bytes']+=len(body)
                    if len(body)!=end-start:continue
                    view=memoryview(body)
                    for obj in members:yield obj['sha256'],view[obj['offset']-start:obj['offset']-start+obj['size']]
            finally:os.close(fd)
    def invalidate(self,key):self.entries.pop(key,None)
    def prepare(self,objects):
        new={obj['sha256']:obj for obj in objects};all_ids=set(self.entries)|set(new)
        if len(all_ids)>t.MAX_OBJECTS or sum(obj['size'] for key,obj in self.entries.items() if key not in new)+sum(obj['size'] for obj in new.values())>MAX_DATA:
            raise QuotaError('logical cache capacity exceeded')
        if not objects:return
        projected=sum(pack['size'] for pack in self.packs.values())+len(PACK_MAGIC)+sum(obj['size'] for obj in objects)
        self.compact=len(self.packs)>=MAX_PACKS or projected>MAX_DATA+len(PACK_MAGIC)*MAX_PACKS
    def _write(self,obj,body):
        start=self.stage_size
        try:
            if self.stage_size+len(body)>MAX_DATA+len(PACK_MAGIC):raise QuotaError('staging payload capacity exceeded')
            if self.stage.write(body)!=len(body):raise OSError('short staging write')
        except BaseException:self.failed=True;raise
        self.hasher.update(body);self.stage_size+=len(body);self.stats['data_write_bytes']+=len(body)
        self.stage_entries[obj['sha256']]=dict(sha256=obj['sha256'],size=len(body),offset=start)
    def _begin(self):
        self.stage=(self.staging/'data.tmp').open('wb',buffering=65536);self.hasher=hashlib.sha256()
        try:
            if self.stage.write(PACK_MAGIC)!=len(PACK_MAGIC):raise OSError('short pack header write')
        except BaseException:self.failed=True;raise
        self.hasher.update(PACK_MAGIC);self.stage_size=len(PACK_MAGIC);self.stats['data_write_bytes']+=len(PACK_MAGIC)
        if self.compact:
            self.stats['compactions']+=1
            for key,body in self.iter_available(list(self.entries.values())):
                self.stats['compaction_hash_bytes']+=len(body)
                if t.digest(body)==key:self._write(self.entries[key],body)
    def put_verified(self,obj,body):
        with self.write_lock:
            if self.stage is None:self._begin()
            self._write(obj,body)
    def _publish_bytes(self,name,path,body):
        temporary=self.staging/name
        with temporary.open('wb') as stream:
            if stream.write(body)!=len(body):raise OSError('short metadata write')
        os.replace(temporary,path);self.stats['atomic_publications']+=1;self.stats['metadata_write_bytes']+=len(body)
    def finish(self):
        if self.stage is None:return
        old_entries=self.entries.copy();old_packs=self.packs.copy();old_index=self.index_id;committed=False
        try:
            self.stage.flush();self.stage.close();self.stage=None
            desc=dict(algorithm='sha256',digest=self.hasher.hexdigest(),size=self.stage_size)
            self.stats['representation_hash_bytes']+=self.stage_size
            os.replace(self.staging/'data.tmp',self.data_dir/(desc['digest']+'.gap'));self.stats['atomic_publications']+=1
            entries={} if self.compact else self.entries.copy()
            for key,obj in self.stage_entries.items():entries[key]={**obj,'pack':desc['digest']}
            needed={obj['pack'] for obj in entries.values()};packs={key:pack for key,pack in self.packs.items() if key in needed};packs[desc['digest']]=desc
            if len(packs)>MAX_PACKS:raise QuotaError('pack count exceeded')
            body=t.encode(dict(version=1,digest_algorithm='sha256',packs=[packs[k] for k in sorted(packs)],objects=[entries[k] for k in sorted(entries)]))
            encoded=INDEX_MAGIC+struct.pack('!Q',len(body))+body
            if len(encoded)>MAX_INDEX:raise QuotaError('index capacity exceeded')
            index=descriptor(encoded);self.stats['representation_hash_bytes']+=len(encoded)
            self._publish_bytes('index.tmp',self.index_dir/(index['digest']+'.gai'),encoded)
            self._publish_bytes('head.tmp',self.root/'head.json',t.encode(dict(version=1,index=index)))
            self.entries=entries;self.packs=packs;self.index_id=index['digest'];self.stats['index_bytes']=len(encoded);committed=True
            self.stage_entries={};self.compact=False;self._cleanup();self._update_stats()
        except BaseException:
            self.failed=True
            if not committed:self.entries=old_entries;self.packs=old_packs;self.index_id=old_index
            raise
    def abort(self):
        if self.stage is not None and not self.failed:
            try:self.finish()
            except (OSError,t.TransferError):pass
        if self.stage is not None:
            try:self.stage.close()
            except OSError:pass
            self.stage=None
        try:self._cleanup()
        except (OSError,t.TransferError):pass
    def close(self):
        if self.stage is not None:self.abort()
        self.lease.close()


def make(root,layout):
    if layout=='files':return Files(root)
    if layout=='packed':return Packed(root)
    raise t.TransferError('unknown cache layout')


def access(cache,manifest_id,manifest_size,wanted,layout):
    """Return verified read-only logical views backed by owned immutable buffers."""
    cache=Path(cache);store=make(cache,layout)
    try:
        body=read_bounded(cache/('sha256-'+manifest_id+'.manifest'),t.MAX_MANIFEST)
        if len(body)!=manifest_size or t.digest(body)!=manifest_id:raise t.TransferError('access manifest integrity')
        manifest=t.parse_manifest(body);objects={obj['sha256']:obj for obj in manifest['objects']};wanted=list(wanted)
        if len(wanted)!=len(set(wanted)) or any(key not in objects for key in wanted):raise t.TransferError('access selected identities')
        result={};hashed=0
        for key,payload in store.iter_available([objects[key] for key in wanted]):
            hashed+=len(payload)
            if t.digest(payload)!=key:raise t.TransferError('access blob integrity')
            result[key]=payload
        if set(result)!=set(wanted):raise t.TransferError('access unavailable content')
        return result,dict(logical_hash_bytes=hashed,metadata_hash_bytes=len(body),store=store.stats.copy())
    finally:store.close()


def materialize(cache,views,layout,destination):
    """Legacy ordinary-file demand is explicit and separate from logical access."""
    if layout=='files':return {key:Path(cache)/'objects'/'sha256'/key for key in views},dict(publications=0,bytes_written=0)
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    for key,body in views.items():t.atomic_write(destination/key,body)
    return {key:destination/key for key in views},dict(publications=len(views),bytes_written=sum(map(len,views.values())))
