import os
import gc
import hashlib
import importlib
import importlib.resources
import marshal
from pathlib import Path
import pkgutil
import shutil
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

import binary_index
from bundle_access import BundleResources
from indexed_path_loader import IndexedPathProvider
from native_benchmark import compile_extension
from native_loader import NativeBundleReader
from precomputed_index import build_index

ODIN=shutil.which(os.environ.get("ODIN", "odin")) or os.environ.get("ODIN", "odin")


@unittest.skipUnless(sys.platform=='linux' and Path(ODIN).is_file() and shutil.which('cc'),'Linux Odin/C toolchain unavailable')
class NativeCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build=tempfile.TemporaryDirectory();cls.library,_=compile_extension(Path(cls.build.name),ODIN)
    @classmethod
    def tearDownClass(cls):cls.build.cleanup()
    def fixture(self,root,bytecode=False,extra=None):
        files={'gaia_live_pkg/__init__.py':b'from .child import VALUE\n',
               'gaia_live_pkg/child.py':b'VALUE=42\n',
               'gaia_live_pkg/unused.py':b'raise AssertionError("leaf executed during enumeration")\n',
               'gaia_live_pkg/sub/__init__.py':b'', 'gaia_live_pkg/sub/deep.py':b'VALUE=17\n',
               'gaia_live_pkg/data.txt':b'resource', 'gaia_live_pkg/π.txt':b'unicode',
               'orphan/leaf.py':b'VALUE=9\n', '__init__.py':b'', 'top.py':b'VALUE=8\n'}
        if extra:files.update(extra)
        if bytecode:
            files={(name+'c' if name.endswith('.py') else name):importlib.util.MAGIC_NUMBER+b'\0'*12+marshal.dumps(compile(body,name,'exec'))
                   if name.endswith('.py') else body for name,body in files.items()}
        archive=root/'data.zip';index=root/'data.index'
        with zipfile.ZipFile(archive,'w') as bundle:
            for name,body in files.items():bundle.writestr(name,body)
        built=build_index(archive,index,encoding='binary')
        return archive,index,built,files
    def reader(self,archive,index,built,**kw):
        return NativeBundleReader(archive,index,index_sha256=built['index_sha256'],library=self.library,
                                  verify=kw.pop('verify','local'),catalog_mode='native',**kw)
    def cleanup_modules(self):
        for name in list(sys.modules):
            if name=='gaia_live_pkg' or name.startswith('gaia_live_pkg.'):del sys.modules[name]
    def test_source_and_bytecode_lookup_resources_enumeration_without_export(self):
        for bytecode in (False,True):
            with self.subTest(bytecode=bytecode),tempfile.TemporaryDirectory() as temp:
                archive,index,built,files=self.fixture(Path(temp),bytecode)
                reader=self.reader(archive,index,built)
                provider=IndexedPathProvider(archive,archive_factory=lambda _:reader,resource_factory=BundleResources)
                try:
                    with mock.patch.object(reader,'infolist',side_effect=AssertionError('bulk entries')):
                        provider.install();provider.open_archive()
                        self.assertLessEqual(reader.live_counts[3],reader.live_counts[4])
                        self.assertEqual(reader.names_returned,0)
                        self.assertEqual(len(provider.modules),8)
                        with mock.patch('importlib._bootstrap_external._path_stat',side_effect=AssertionError('host probe')):
                            self.assertIsNotNone(provider.find_spec('gaia_live_pkg.child'))
                            self.assertIsNone(provider.find_spec('gaia_live_pkg.missing'))
                            package=importlib.import_module('gaia_live_pkg')
                        self.assertEqual(package.VALUE,42)
                        self.assertEqual([(r.name,r.ispkg) for r in pkgutil.iter_modules(package.__path__)],
                                         [('child',False),('sub',True),('unused',False)])
                        self.assertNotIn('gaia_live_pkg.unused',sys.modules)
                        resource=importlib.resources.files(package)
                        self.assertEqual(resource.joinpath('π.txt').read_bytes(),b'unicode')
                        self.assertIn('sub',[p.name for p in resource.iterdir()])
                        self.assertEqual(reader.entries.created,0)
                        for name,body in files.items():self.assertEqual(reader.read(name),body)
                        with self.assertRaises(KeyError):reader.read('missing')
                        with self.assertRaises(ValueError):reader._ffi.catalog(reader._handle)
                finally:provider.close();self.cleanup_modules()
                with self.assertRaises(ValueError):reader.name(0)
    def test_budget_limit_failure_cleanup_and_constant_arena_after_lookups(self):
        with tempfile.TemporaryDirectory() as temp:
            archive,index,built,_=self.fixture(Path(temp));before=len(list(Path('/proc/self/fd').iterdir()))
            for budget in (0,1,64):
                with self.assertRaises(MemoryError):self.reader(archive,index,built,catalog_budget=budget)
                self.assertEqual(len(list(Path('/proc/self/fd').iterdir())),before)
            reader=self.reader(archive,index,built);used=reader.live_counts[3];reader.close()
            reader=self.reader(archive,index,built,catalog_budget=used)
            for _ in range(100):
                reader.precomputed_modules['gaia_live_pkg.child'];reader.read('gaia_live_pkg/data.txt')
            self.assertEqual(reader._ffi.live_stats(reader._handle)[3],used)
            reader.close();del reader;gc.collect()
            self.assertEqual(len(list(Path('/proc/self/fd').iterdir())),before)
    def test_bad_index_ambiguity_crc_and_native_decode_reentrant_close(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);archive,index,built,files=self.fixture(root,True)
            reader=self.reader(archive,index,built,bytecode_handoff='native')
            row=next(r for r in binary_index.decode(index.read_bytes())['entries'] if r[0]=='gaia_live_pkg/data.txt')
            with archive.open('r+b') as stream:stream.seek(row[1]);stream.write(b'X')
            with self.assertRaises(zipfile.BadZipFile):reader.read('gaia_live_pkg/data.txt')
            # Direct decode stays valid if an audit callback closes the arena/maps.
            state={'active':True}
            def audit(event,args):
                if event=='marshal.loads' and state['active']:reader.close()
            sys.addaudithook(audit)
            try:code=reader.load_code('gaia_live_pkg/child.pyc')
            finally:state['active']=False;reader.close()
            namespace={};exec(code,namespace);self.assertEqual(namespace['VALUE'],42)
            encoded=bytearray(index.read_bytes());encoded[-1]=0xff;index.write_bytes(encoded)
            with self.assertRaises(ValueError):self.reader(archive,index,{'index_sha256':hashlib.sha256(encoded).hexdigest()})
        with tempfile.TemporaryDirectory() as temp:
            archive,index,built,_=self.fixture(Path(temp),extra={'gaia_live_pkg/child.pyc':b''})
            with self.assertRaisesRegex(ValueError,'status 11'):self.reader(archive,index,built)


if __name__=='__main__':unittest.main()
