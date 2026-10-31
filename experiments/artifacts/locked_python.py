"""Trusted hash-set acquisition and direct packed Python byte access; research only."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import time

import cache_store as cache
import pipeline_transport as transport
import transfer as t


def parse_lock(body,pin):
    if len(body)>t.MAX_MANIFEST or t.digest(body)!=pin:raise t.TransferError('lock integrity/bound')
    value=json.loads(body,object_pairs_hook=t._pairs)
    if not isinstance(value,dict) or set(value)!={'version','algorithm','files','versions','resources'} or value['version']!=1 or value['algorithm']!='sha256':raise t.TransferError('unsupported lock')
    if not isinstance(value['files'],list) or len(value['files'])>t.MAX_OBJECTS:raise t.TransferError('file count')
    names=set();objects={}
    for row in value['files']:
        if not isinstance(row,dict) or set(row)!={'name','sha256','size'}:raise t.TransferError('file descriptor')
        name=row['name']
        if not isinstance(name,str) or not name or '\\' in name or '\x00' in name or name.startswith('/') or any(p in ('','.','..') for p in name.split('/')) or ':' in name or name.casefold() in names:raise t.TransferError('logical name')
        if not isinstance(row['sha256'],str) or not t.HEX.fullmatch(row['sha256']) or type(row['size']) is not int or not 0<=row['size']<=t.MAX_PACK:raise t.TransferError('object descriptor')
        names.add(name.casefold());old=objects.setdefault(row['sha256'],dict(sha256=row['sha256'],size=row['size']))
        if old['size']!=row['size']:raise t.TransferError('conflicting hash sizes')
    if sum(o['size'] for o in objects.values())>t.MAX_PACK:raise t.TransferError('logical quota')
    return value,list(objects.values())


def make_lock(directory,expected):
    files=[];payloads=[]
    for path in sorted(Path(directory).rglob('*')):
        if not path.is_file():continue
        if path.is_symlink():raise ValueError('symlink')
        body=path.read_bytes();files.append(dict(name=path.relative_to(directory).as_posix(),sha256=t.digest(body),size=len(body)));payloads.append(body)
    body=t.encode(dict(version=1,algorithm='sha256',files=files,versions=expected['versions'],resources=expected['resources']))
    parse_lock(body,t.digest(body));return body,payloads


def acquire(url,lock_body,pin,destination,layout='packed'):
    begin=time.perf_counter();value,objects=parse_lock(lock_body,pin);parsed=time.perf_counter();root=Path(destination)
    store=cache.Packed(root) if layout=='packed' else cache.Files(root);client=None;hashed=len(lock_body);hits=set();first=None
    try:
        by_key={obj['sha256']:obj for obj in objects}
        for key,view in store.iter_available(objects):
            hashed+=len(view)
            if t.digest(view)==key:hits.add(key)
            else:store.invalidate(key)
        missing=[obj for obj in objects if obj['sha256'] not in hits];store.prepare(missing);checked=time.perf_counter()
        if missing:
            client=transport.Client(url)
            for obj,payload in client.stream_batch(missing):
                hashed+=len(payload)
                if len(payload)!=obj['size'] or t.digest(payload)!=obj['sha256']:raise t.TransferError('streamed lock object integrity')
                if first is None:first=time.perf_counter()-begin
                store.put_verified(obj,payload)
        store.finish();published=time.perf_counter()
        lock_path=root/('sha256-'+pin+'.pylock');prior=lock_path.read_bytes() if lock_path.exists() else None
        if prior!=lock_body:t.atomic_write(lock_path,lock_body)
        t.atomic_write(root/'ready.json',t.encode(dict(version=1,lock='sha256:'+pin,objects=sorted(by_key))))
        return dict(seconds=time.perf_counter()-begin,lock_parse_seconds=parsed-begin,cache_check_seconds=checked-parsed,
            transfer_admit_seconds=published-checked,first_verified_seconds=first,requests=client.requests if client else 0,
            manifest_requests=0,cache_hits=len(hits),objects=len(objects),hash_bytes=hashed,
            transfer_bytes=sum(obj['size'] for obj in missing),store=dict(store.stats))
    except BaseException:
        (root/'ready.json').unlink(missing_ok=True);store.abort();raise
    finally:
        if client:client.close()
        store.close()


class PackedReader:
    """One retained packed-cache/index lifetime; hash each requested file on read."""
    def __init__(self,root,lock_body,pin):
        value,objects=parse_lock(lock_body,pin);self.filename=str(root);self.entries={row['name']:row for row in value['files']}
        self.store=cache.Packed(Path(root));self.fds={};self.reads=0;self.hash_bytes=len(lock_body);self.directories={''};self.precomputed_modules={}
        try:
            for row in self.entries.values():
                saved=self.store.entries.get(row['sha256'])
                if saved is None or saved['size']!=row['size']:raise t.TransferError('unavailable locked file')
                name=row['name']
                for parent in PurePosixPath(name).parents:
                    if str(parent)!='.':self.directories.add(str(parent)+'/')
                if name.endswith(('.py','.pyc')):
                    stem=name[:-4] if name.endswith('.pyc') else name[:-3];package=stem.endswith('/__init__')
                    if package:stem=stem[:-9]
                    module=stem.replace('/','.')
                    if module in self.precomputed_modules:raise t.TransferError('mixed/duplicate module')
                    self.precomputed_modules[module]=(name,package)
            for key,desc in self.store.packs.items():
                fd=os.open(self.store.data_dir/(key+'.gap'),os.O_RDONLY);self.fds[key]=fd
                if os.fstat(fd).st_size!=desc['size'] or os.pread(fd,len(cache.PACK_MAGIC),0)!=cache.PACK_MAGIC:raise t.TransferError('pack framing/size')
        except BaseException:self.close();raise
    def read(self,name):
        row=self.entries[name];saved=self.store.entries[row['sha256']];body=os.pread(self.fds[saved['pack']],row['size'],saved['offset'])
        if len(body)!=row['size'] or t.digest(body)!=row['sha256']:raise t.TransferError('locked file integrity')
        self.reads+=1;self.hash_bytes+=len(body);return body
    def close(self):
        for fd in self.fds.values():os.close(fd)
        self.fds.clear();self.store.close()


def discover_exact(catalog_body,catalog_pin,name,version):
    """Separate pinned name/version catalog; returns a lock descriptor, not a solve."""
    if len(catalog_body)>t.MAX_MANIFEST or t.digest(catalog_body)!=catalog_pin:raise t.TransferError('catalog integrity/bound')
    catalog=json.loads(catalog_body,object_pairs_hook=t._pairs)
    if not isinstance(catalog,dict) or set(catalog)!={'version','entries'} or type(catalog['version']) is not int or catalog['version']!=1 or not isinstance(catalog['entries'],list) or len(catalog['entries'])>t.MAX_OBJECTS:raise t.TransferError('catalog schema/bound')
    found=None;seen=set()
    for row in catalog['entries']:
        if not isinstance(row,dict) or set(row)!={'name','version','lock'} or not isinstance(row['name'],str) or not isinstance(row['version'],str) or not row['name'] or not row['version'] or len(row['name'])>256 or len(row['version'])>256 or not cache.valid_descriptor(row['lock'],t.MAX_MANIFEST):raise t.TransferError('catalog entry')
        identity=(row['name'],row['version'])
        if identity in seen:raise t.TransferError('ambiguous catalog identity')
        seen.add(identity)
        if identity==(name,version):found=dict(row['lock'])
    if found is None:raise LookupError((name,version))
    return found


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description='Resolve one exact name/version in a previously pinned local catalog')
    parser.add_argument('catalog',type=Path);parser.add_argument('pin');parser.add_argument('name');parser.add_argument('version')
    args=parser.parse_args();print(json.dumps(discover_exact(args.catalog.read_bytes(),args.pin,args.name,args.version),sort_keys=True))
