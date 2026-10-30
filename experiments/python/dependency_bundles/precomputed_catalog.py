"""Pinned interpreter-specific derived metadata; not a portable storage format."""
from collections.abc import Mapping
import hashlib
import importlib.util
import marshal
from pathlib import Path
import sys


def runtime_identity():
    return (sys.implementation.name,sys.implementation.cache_tag,sys.version,importlib.util.MAGIC_NUMBER,
            sys.platform,getattr(sys.implementation,'_multiarch',None),sys.flags.optimize)


def write_catalog(archive,index,pin,destination,*,mode):
    # Producer uses the full existing decoder/reader checks. Rows retain native
    # binary-index ordinal order; no archive offsets are duplicated here.
    import binary_index
    from precomputed_index import IndexedBundleReader
    validated=IndexedBundleReader(archive,index,index_sha256=pin,verify='local')
    validated.close()
    encoded=Path(index).read_bytes()
    if hashlib.sha256(encoded).hexdigest()!=pin:raise ValueError('index digest mismatch')
    document=binary_index.decode(encoded);rows={name:i for i,(name,*_) in enumerate(document['entries'])}
    if len(rows)!=binary_index.HEADER.unpack_from(encoded)[11]:raise ValueError('duplicate catalog member')
    data=dict(format='gaia-derived-catalog',version=1,runtime=runtime_identity(),index_sha256=pin,
              mode=mode,rows=rows,directories=set(document['directories']))
    if mode=='tables':
        modules={}
        for member in rows:
            if not member.endswith(('.py','.pyc')):continue
            stem=member[:-4] if member.endswith('.pyc') else member[:-3]
            package=stem.endswith('/__init__')
            if package:stem=stem[:-len('/__init__')]
            name=stem.replace('/','.')
            if name in modules:raise ValueError('ambiguous/mixed source-bytecode module: '+name)
            modules[name]=(member,package)
        packages={'':''};package_names={'':''}
        for name,(member,package) in modules.items():
            if package:
                relative=member.rsplit('/',1)[0];packages[relative]=name;package_names[name]=relative
        children={path:[] for path in packages}
        for name,(_,package) in modules.items():
            parent,_,child=name.rpartition('.');path=package_names.get(parent)
            if path is not None and child!='__init__':children[path].append((child,package))
        data.update(modules=modules,packages=packages,children={p:tuple(sorted(v)) for p,v in children.items()})
    elif mode!='rows':raise ValueError('unknown catalog mode')
    body=marshal.dumps(data);Path(destination).write_bytes(body)
    return dict(path=str(Path(destination).resolve()),sha256=hashlib.sha256(body).hexdigest(),bytes=len(body),
                mode=mode,entries=len(rows),modules=len(data.get('modules',{})))


def load_catalog(path,pin,*,index_sha256,mode):
    body=Path(path).read_bytes()
    if hashlib.sha256(body).hexdigest()!=pin:raise ValueError('catalog digest mismatch')
    data=marshal.loads(body)
    if (data['format']!='gaia-derived-catalog' or data['version']!=1 or data['runtime']!=runtime_identity()
            or data['index_sha256']!=index_sha256 or data['mode']!=mode):
        raise ValueError('catalog identity/version/mode differs')
    return data


class LazyEntries(Mapping):
    """Names/ordinal map is eager; allocate entry wrappers only on demand."""
    def __init__(self,rows,entry_type):self.rows,self.entry_type,self.created=rows,entry_type,0
    def __len__(self):return len(self.rows)
    def __iter__(self):return iter(self.rows)
    def __contains__(self,name):return name in self.rows
    def __getitem__(self,name):
        row=self.rows[name];self.created+=1
        return self.entry_type(name,row)
