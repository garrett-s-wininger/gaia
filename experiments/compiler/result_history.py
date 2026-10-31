"""Bounded linked-result retention, proven by actual native query conditions.

Private per-output cache; one serial writer. A completion receipt is published
last. Corrupt/missing entries miss; this never substitutes an object-only proof
for the full command/link/tool/condition contract.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import struct
import uuid

from inline_snapshot import atomic_write

HEX=re.compile(r'^[0-9a-f]{64}$')
ENTRY=re.compile(r'^[0-9a-f]{32}$')


class InputsChanged(RuntimeError):pass


def encoded(value):return json.dumps(value,sort_keys=True,separators=(',',':')).encode()


def envelope(kind,body):
    payload=encoded(body)
    return encoded(dict(format=kind,body=body,sha256=hashlib.sha256(payload).hexdigest()))


def bounded(path,limit):
    if not stat.S_ISREG(path.lstat().st_mode):raise ValueError('regular cache file required')
    with path.open('rb') as stream:
        body=stream.read(limit+1)
    if len(body)>limit:raise ValueError('cache size bound')
    return body


def decode(path,kind,limit=65536):
    try:value=json.loads(bounded(path,limit))
    except RecursionError:raise ValueError('cache nesting bound') from None
    if not isinstance(value,dict) or value.get('format')!=kind or value.get('sha256')!=hashlib.sha256(encoded(value['body'])).hexdigest():
        raise ValueError('cache envelope')
    return value['body']


def receipt_proof(path,request):
    data=bounded(Path(path),1048576)
    if len(data)<144 or data[:8]!=b'GAIASK01' or data[8:72]!=request.encode() or hashlib.sha256(data[:-32]).digest()!=data[-32:]:
        raise ValueError('completed receipt integrity')
    body=data[:-32];offset=104
    def number():
        nonlocal offset
        if offset>len(body)-8:raise ValueError('receipt framing')
        value=struct.unpack_from('<Q',body,offset)[0];offset+=8;return value
    count=number()
    if not 1<=count<=64:raise ValueError('receipt output count')
    outputs={}
    for _ in range(count):
        length=number()
        if not 1<=length<=4096 or length>len(body)-offset:raise ValueError('receipt path length')
        name=body[offset:offset+length].decode();offset+=length
        size=number();number();number()
        if not name.startswith('/') or name in outputs or offset>len(body)-32:raise ValueError('receipt output')
        outputs[name]=(size,body[offset:offset+32]);offset+=32
    if offset!=len(body):raise ValueError('receipt tail')
    return data[72:104],outputs


def rebound_receipt(request,identity,outputs):
    body=bytearray(b'GAIASK01'+request.encode()+identity+struct.pack('<Q',len(outputs)))
    for path,digest in outputs:
        info=path.stat();name=str(path).encode();sec,ns=divmod(info.st_mtime_ns,1000000000)
        body+=struct.pack('<Q',len(name))+name+struct.pack('<QQQ',info.st_size,sec&((1<<64)-1),ns)+digest
    return body+hashlib.sha256(body).digest()


class LinkedResults:
    def __init__(self,root,decision,env=None,max_entries=3,max_bytes=16*1048576,runner=None):
        self.root=Path(root);self.decision=str(decision);self.env=env
        self.runner=runner
        self.max_entries=max_entries;self.max_bytes=max_bytes

    def call(self,mode,receipt,request,watch,outputs,namespace,index,stamp=None):
        argv=[self.decision,mode,str(receipt),request,str(watch),str(outputs),str(namespace),str(index)]
        if stamp is not None:argv.append(stamp)
        if self.runner is not None:return self.runner(argv)
        result=subprocess.run(argv,env=self.env,capture_output=True,text=True)
        if result.returncode or result.stderr:raise ValueError('decision validation failed: '+result.stderr[:256])
        return json.loads(result.stdout)

    def catalog(self):
        try:
            entries=decode(self.root/'catalog','GAIALC01')['entries']
            if not isinstance(entries,list) or len(entries)>self.max_entries:raise ValueError('catalog count')
            seen=set();total=0
            for item in entries:
                if not ENTRY.fullmatch(item['id']) or item['id'] in seen or not HEX.fullmatch(item['request']):raise ValueError('catalog identity')
                if type(item['bytes']) is not int or not 0<=item['bytes']<=self.max_bytes:raise ValueError('catalog bytes')
                seen.add(item['id']);total+=item['bytes']
            if total>self.max_bytes:raise ValueError('catalog quota')
            return entries
        except (OSError,ValueError,KeyError,TypeError):return []

    def descriptor(self,entry,request):
        if entry.is_symlink() or not entry.is_dir():raise ValueError('entry directory')
        value=decode(entry/'descriptor','GAIALR02')
        if value['request']!=request or not isinstance(value['files'],dict) or not 1<=len(value['files'])<=8:raise ValueError('result identity/count')
        total=0
        for name,info in value['files'].items():
            if not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}',name) or name in ('.','..','descriptor','receipt','outputs'):raise ValueError('artifact name')
            if not HEX.fullmatch(info['sha256']) or type(info['size']) is not int or not 0<=info['size']<=self.max_bytes:raise ValueError('artifact descriptor')
            if type(info['mode']) is not int or not 0<=info['mode']<=0o777:raise ValueError('artifact mode')
            total+=info['size']
        if total>self.max_bytes:raise ValueError('entry quota')
        return value

    def cleanup(self,keep):
        # Inspect at most one staging entry beyond the committed bound. Unknown
        # names or excess debris disable publication instead of an unbounded sweep.
        if not self.root.exists():return
        with os.scandir(self.root) as iterator:
            names=[]
            for item in iterator:
                if item.name=='catalog':continue
                names.append(item.name)
                if len(names)>self.max_entries+1:raise ValueError('excess cache debris')
        for name in names:
            path=self.root/name
            if not ENTRY.fullmatch(name) or path.is_symlink() or not path.is_dir():raise ValueError('unknown cache entry')
        for name in names:
            if name not in keep:shutil.rmtree(self.root/name)

    def store(self,request,artifacts,watch,namespace,index,stamp,source_receipt=None):
        stats=dict(stored=False)
        entry=None
        try:
            if not HEX.fullmatch(request) or not 1<=len(artifacts)<=8:raise ValueError('request/count')
            entries=self.catalog();self.root.mkdir(parents=True,exist_ok=True)
            self.cleanup({item['id'] for item in entries})
            identity=None;completed=None
            if source_receipt is not None:
                identity,completed=receipt_proof(source_receipt,request)
                by_path={str(Path(path)):name for name,path in artifacts.items()}
                if not set(completed).issubset(by_path):raise ValueError('incomplete result retention')
                artifacts={by_path[path]:Path(path) for path in completed}
            # Read one bounded collection before publishing any candidate.
            bodies={};digests={};total=0
            for name,path in artifacts.items():
                if not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}',name) or name in ('.','..','descriptor','receipt','outputs'):raise ValueError('artifact name')
                body=bounded(Path(path),self.max_bytes-total);total+=len(body)
                digest=hashlib.sha256(body).digest()
                if completed is not None and (len(body),digest)!=completed[str(path)]:raise ValueError('completed artifact changed')
                bodies[name]=body;digests[name]=digest
            ident=uuid.uuid4().hex;entry=self.root/ident;entry.mkdir()
            files={}
            for name,body in bodies.items():
                mode=stat.S_IMODE(Path(artifacts[name]).stat().st_mode)&0o777
                atomic_write(entry/name,body);os.chmod(entry/name,mode)
                files[name]=dict(size=len(body),sha256=digests[name].hex(),mode=mode)
            atomic_write(entry/'descriptor',envelope('GAIALR02',dict(request=request,files=files)))
            self.descriptor(entry,request)
            outputs=entry/'outputs'
            outputs.write_text('GAIA-WATCH-1\n'+'\n'.join(str(entry/name) for name in [*files,'descriptor'])+'\n')
            if identity is None:
                proof=self.call('selective-record',entry/'receipt',request,watch,outputs,namespace,index,stamp)
                if not proof['recorded']:raise ValueError('retained result proof refused')
            else:
                hashes=[(entry/name,bytes.fromhex(info['sha256'])) for name,info in files.items()]
                hashes.append((entry/'descriptor',hashlib.sha256(bounded(entry/'descriptor',65536)).digest()))
                atomic_write(entry/'receipt',rebound_receipt(request,identity,hashes))
                stats['proof_rebound']=True
            entries=[dict(id=ident,request=request,bytes=total),*entries]
            while len(entries)>self.max_entries or sum(item['bytes'] for item in entries)>self.max_bytes:entries.pop()
            atomic_write(self.root/'catalog',envelope('GAIALC01',dict(entries=entries)))
            entry=None  # Published; cleanup failure cannot invalidate this proof.
            self.cleanup({item['id'] for item in entries})
            stats.update(stored=True,entries=len(entries),bytes=sum(item['bytes'] for item in entries))
        except (OSError,ValueError,KeyError,TypeError) as error:
            stats['error']=str(error)[:256]
        finally:
            if entry is not None:shutil.rmtree(entry,ignore_errors=True)
        return stats

    def restore(self,request,destinations,watch,namespace,index,active_receipt,active_outputs,result_name):
        stats=dict(hit=False,candidates=0,decision_calls=0,restored_bytes=0)
        for item in self.catalog():
            if item['request']!=request:continue
            entry=self.root/item['id'];stats['candidates']+=1
            try:
                value=self.descriptor(entry,request)
                if not set(value['files']).issubset(destinations) or result_name not in value['files']:continue
                candidate_index=entry/Path(index).name
                proof=self.call('selective-history-check',entry/'receipt',request,watch,entry/'outputs',namespace,candidate_index)
                stats['decision_calls']+=1
                if not proof['hit']:continue
                bodies={}
                for name,info in value['files'].items():
                    body=bounded(entry/name,info['size'])
                    if len(body)!=info['size'] or hashlib.sha256(body).hexdigest()!=info['sha256']:raise ValueError('retained payload integrity')
                    bodies[name]=body
                result=json.loads(bodies[result_name])
                # Receipt is the commit marker. A partial restore is never a hit.
                Path(active_receipt).unlink(missing_ok=True)
                for name,body in bodies.items():
                    atomic_write(destinations[name],body);os.chmod(destinations[name],value['files'][name]['mode'])
                final=self.call('selective-record',active_receipt,request,watch,active_outputs,namespace,index,proof['stamp'])
                if not final['inputs_unchanged']:raise InputsChanged('inputs changed during linked-result restoration')
                if not final['recorded']:raise ValueError('restored result receipt refused')
                stats.update(hit=True,entry=item['id'],restored_bytes=sum(map(len,bodies.values())))
                return result,stats
            except InputsChanged:
                Path(active_receipt).unlink(missing_ok=True);raise
            except (OSError,ValueError,KeyError,TypeError):continue
        return None,stats
