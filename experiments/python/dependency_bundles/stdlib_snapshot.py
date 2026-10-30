"""Interpreter-bound, admitted stdlib code/source snapshot (experimental v1).

Runtime module: keep imports limited to the existing loader's bootstrap closure.
Native extensions and modules outside the snapshot retain their host loader.
"""
import importlib.machinery
import importlib.util
from importlib.resources.abc import Traversable, TraversableResources
import hashlib
import json
import marshal
import os
from pathlib import Path
import sys
import types
import zlib

from bundle_access import BundlePath
from indexed_path_loader import IndexedPathProvider
from persistent_zip_loader import ModuleLoader

MANIFEST = '__gaia_bootstrap__/manifest.json'


def runtime_identity():
    return dict(implementation=sys.implementation.name,cache_tag=sys.implementation.cache_tag,
                version=sys.version,magic=importlib.util.MAGIC_NUMBER.hex(),optimize=sys.flags.optimize,
                platform=sys.platform,multiarch=getattr(sys.implementation,'_multiarch',None))


class DirectorySnapshot:
    """Known-path directory control; validates payload length/CRC like readers."""
    def __init__(self, root):
        self.root=Path(root);self.records={};self.closed=False
    def read(self, name):
        if self.closed:raise ValueError('directory snapshot closed')
        body=(self.root/name).read_bytes()
        if name!=MANIFEST:
            length,crc=self.records[name]
            if len(body)!=length or zlib.crc32(body)!=crc:raise ValueError('snapshot payload CRC differs')
        return body
    def close(self):self.closed=True


class OverlayPath(Traversable):
    def __init__(self, snapshot, fallback):self.snapshot,self.fallback=snapshot,fallback
    @property
    def name(self):return self.snapshot.name
    def is_file(self):return self.snapshot.is_file() or self.fallback.is_file()
    def is_dir(self):return self.snapshot.is_dir() or self.fallback.is_dir()
    def iterdir(self):
        names=set()
        if self.snapshot.is_dir():names.update(p.name for p in self.snapshot.iterdir())
        if self.fallback.is_dir():names.update(p.name for p in self.fallback.iterdir())
        return iter(self.joinpath(n) for n in sorted(names))
    def joinpath(self,*parts):return OverlayPath(self.snapshot.joinpath(*parts),self.fallback.joinpath(*parts))
    def open(self,mode='r',*args,**kwargs):
        if self.snapshot.is_file():return self.snapshot.open(mode,*args,**kwargs)
        return self.fallback.open(mode,*args,**kwargs)


class SnapshotResources(TraversableResources):
    def __init__(self,provider,name):self.provider,self.name=provider,name
    def files(self):
        row=self.provider.records[self.name]
        relative=row['relative_source'].rsplit('/',1)[0] if '/' in row['relative_source'] else ''
        return OverlayPath(BundlePath(self.provider.archive,'__gaia_sources__/'+relative+'/'),
                           self.provider.host_root/relative)


class SnapshotLoader(ModuleLoader):
    def get_filename(self,fullname):return self.provider.records[fullname]['origin']
    def get_code(self,fullname):
        provider=self.provider;row=provider.records[fullname]
        archive=provider.open_archive()
        if hasattr(archive,'load_code'):
            code=archive.load_code(row['code'],source_hash=provider.source_hashes[fullname])
        else:
            body=archive.read(row['code'])
            if (len(body)<16 or body[:4]!=importlib.util.MAGIC_NUMBER or
                    int.from_bytes(body[4:8],'little')!=3 or body[8:16]!=provider.source_hashes[fullname]):
                raise ImportError('snapshot bytecode identity differs')
            code=marshal.loads(body[16:])
        provider.module_reads+=1
        if not isinstance(code,types.CodeType) or code.co_filename!=row['origin']:
            raise ImportError('snapshot code/origin differs')
        return code
    def get_source(self,fullname):
        row=self.provider.records[fullname]
        body=self.provider.open_archive().read(row['source']);self.provider.source_reads+=1
        return importlib.util.decode_source(body)
    def get_resource_reader(self,fullname):return SnapshotResources(self.provider,fullname)


class StdlibSnapshotProvider(IndexedPathProvider):
    def __init__(self,archive_path,*,archive_factory,manifest_sha256,host_root):
        super().__init__(archive_path,archive_factory=archive_factory)
        self.manifest_sha256=manifest_sha256;self.host_root=Path(host_root)
        self.records={};self.source_hashes={};self.source_reads=0;self.snapshot=None

    def open_archive(self):
        if self._closed:raise ValueError('stdlib snapshot closed')
        if self.archive is None:
            reader=None;self.opening=True
            try:
                reader=self.archive_factory(self.archive_path)
                body=reader.read(MANIFEST)
                if hashlib.sha256(body).hexdigest()!=self.manifest_sha256:raise ImportError('snapshot manifest digest differs')
                manifest=json.loads(body)
                if manifest['format']!='gaia-python-stdlib' or manifest['version']!=1:
                    raise ImportError('unsupported stdlib snapshot')
                if manifest['runtime']!=runtime_identity():raise ImportError('snapshot interpreter identity differs')
                records=manifest['modules'];payloads={}
                for name,row in records.items():
                    if (not name or type(row['package']) is not bool or
                            row['code']!=row['relative_source'][:-3]+'.pyc' or
                            row['source']!='__gaia_sources__/'+row['relative_source'] or
                            row['origin']!='gaia-stdlib://'+manifest['snapshot']+'/'+row['relative_source']):
                        raise ImportError('invalid snapshot module record')
                    for key in ('code','source'):
                        path=row[key]
                        if path.startswith('/') or '..' in path.split('/') or '\\' in path:
                            raise ImportError('invalid snapshot path')
                        payloads[path]=(row[key+'_size'],row[key+'_crc'])
                if isinstance(reader,DirectorySnapshot):
                    reader.records=payloads
                    reader.entries={name:None for name in payloads}
                    reader.directories={''}
                    for name in payloads:
                        for parent in Path(name).parents:
                            if str(parent)!='.':reader.directories.add(parent.as_posix()+'/')
                elif not set(payloads).issubset(reader.entries):raise ImportError('snapshot member missing')
                self.records=records;self.snapshot=manifest['snapshot']
                self.source_hashes={name:bytes.fromhex(row['source_hash']) for name,row in records.items()}
                self.modules={name:(row['code'],row['package']) for name,row in records.items()}
                self.archive=reader;self.archive_opens+=1
            except BaseException:
                if reader is not None:reader.close()
                self.close();raise
            finally:self.opening=False
        # The archive/module table is already populated: the base only derives
        # package/child tables; source payloads are never mistaken for modules.
        return super().open_archive()

    def find_spec(self,fullname,path=None,target=None):
        if self.opening:return None
        self.open_archive();row=self.records.get(fullname)
        if row is None:return None
        loader=SnapshotLoader(self,fullname)
        spec=importlib.machinery.ModuleSpec(fullname,loader,origin=row['origin'],is_package=row['package'])
        spec.has_location=True;spec.cached=row['origin']+'c'
        if row['package']:
            relative=row['relative_source'].rsplit('/',1)[0]
            spec.submodule_search_locations=[self.archive_path+'/'+relative,str(self.host_root/relative)]
        return spec
