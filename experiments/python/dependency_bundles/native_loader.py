"""In-process CPython/Odin byte provider for the unchanged Python loader."""
import importlib.util
import marshal
from pathlib import Path
from precomputed_catalog import LazyEntries,load_catalog
from native_catalog import LiveEntries,LiveDirectories,LiveModules,LivePackages,LiveChildren,resource_children
import time
import types
import zipfile


class NativeEntry:
    __slots__ = ("filename", "index")

    def __init__(self, name, index):
        self.filename, self.index = name, index

    def is_dir(self):
        return False


class NativeBundleReader:
    def __init__(self, archive, index, *, index_sha256, library, verify="hash", bytecode_handoff="bytes",
                 catalog_path=None,catalog_sha256=None,catalog_mode='rebuilt',catalog_budget=16*1048576):
        if verify not in ("hash", "local"):
            raise ValueError("unknown verification policy")
        if bytecode_handoff not in ('bytes','view','native'):raise ValueError('unknown bytecode handoff')
        self.bytecode_handoff=bytecode_handoff;self.code_loads=0
        self.catalog_mode=catalog_mode;self.row_ids=None
        self.module_queries=self.names_returned=0;self.entry_type=NativeEntry
        self.filename = str(archive)
        self._closed = False
        start = time.perf_counter()
        spec = importlib.util.spec_from_file_location("_gaia_native", str(library))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self._ffi = module
        loaded = time.perf_counter()
        self._handle = (module.unified_open(str(catalog_path),catalog_sha256,index_sha256,str(archive),int(verify=='local'),catalog_budget)
                        if catalog_mode in ('unified','compact') else module.mapped_open(str(index),index_sha256,str(archive),str(catalog_path),catalog_sha256,int(verify=='local'),catalog_budget)
                        if catalog_mode=='mapped' else module.live_open(str(index),index_sha256,str(archive),int(verify=='local'),catalog_budget)
                        if catalog_mode=='native' else module.open(str(index), index_sha256, str(archive), int(verify == "local")))
        opened = time.perf_counter()
        try:
            if catalog_mode in ('native','mapped','unified','compact'):
                self.live_counts=module.live_stats(self._handle)
                self.native_open_phases=dict(zip(('integrity_seconds','validation_seconds','construction_seconds'),module.live_phases(self._handle)))
                self.entries=LiveEntries(self);self.directories=LiveDirectories(self)
                self.precomputed_modules=LiveModules(self);self.precomputed_packages=LivePackages(self)
                self.precomputed_children=LiveChildren(self);self.native_provider=True
            elif catalog_mode=='rebuilt':
                names, directories, count = module.catalog(self._handle)
                names = names.decode("utf-8").split("\0")[:-1]
                self.directories = set(directories.decode("utf-8").split("\0")[:-1])
                self.entries = {name: NativeEntry(name, i) for i, name in enumerate(names)}
                if len(names) != count or len(self.entries) != count:
                    raise ValueError("native catalog count differs")
            else:
                data=load_catalog(catalog_path,catalog_sha256,index_sha256=index_sha256,mode=catalog_mode)
                self.row_ids=data['rows'];self.directories=data['directories']
                self.entries=LazyEntries(self.row_ids,NativeEntry)
                if catalog_mode=='tables':
                    self.precomputed_modules=data['modules'];self.precomputed_packages=data['packages']
                    self.precomputed_children=data['children']
        except BaseException:
            self.close()
            raise
        self.native_timings = {"extension_load_seconds": loaded-start, "native_open_seconds": opened-loaded,
                               "catalog_seconds": time.perf_counter()-opened}

    def infolist(self):
        return list(self.entries.values())

    def read(self, name):
        if self._closed:
            raise ValueError("native reader is closed")
        try:
            return self._ffi.read(self._handle, self.row_id(name))
        except ValueError as error:
            raise zipfile.BadZipFile(str(error)) from error

    def close(self):
        if not self._closed:
            self._ffi.close(self._handle)
            self._closed = True

    def row_id(self,name):
        if self.catalog_mode in ('native','mapped','unified','compact'):
            row=self.entries.lookup(name,0)
            if row<0:raise KeyError(name)
            return row
        return self.row_ids[name] if self.row_ids is not None else self.entries[name].index

    def name(self,row):
        self.names_returned+=1
        return self._ffi.live_name(self._handle,row)

    def iter_resource_children(self,prefix):return resource_children(self,prefix)

    def load_code(self,name,*,source_hash=None):
        if self._closed:raise ValueError('native reader is closed')
        try:
            if self.bytecode_handoff=='native':
                args=(self._handle,self.row_id(name),importlib.util.MAGIC_NUMBER)
                if source_hash is not None:args+=(source_hash,)
                code=self._ffi.read_code(*args)
            else:
                data=self.read(name)
                if len(data)<16 or data[:4]!=importlib.util.MAGIC_NUMBER:
                    raise ImportError('invalid/interpreter-incompatible bytecode')
                flags=int.from_bytes(data[4:8],'little')
                if flags & ~3 or (source_hash is not None and (flags!=3 or data[8:16]!=source_hash)):
                    raise ImportError('bytecode flags/source identity differs')
                payload=memoryview(data)[16:] if self.bytecode_handoff=='view' else data[16:]
                code=marshal.loads(payload)
            if not isinstance(code,types.CodeType):raise ImportError('bytecode payload is not a code object')
        except (EOFError,ValueError,TypeError) as error:
            if 'CRC' in str(error):raise zipfile.BadZipFile(str(error)) from error
            raise ImportError('invalid bytecode body: '+name) from error
        self.code_loads+=1
        return code
