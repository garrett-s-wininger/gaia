import os
from contextlib import contextmanager
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

from bundle_access import BundleResources
from indexed_path_loader import IndexedPathProvider
from native_benchmark import compile_extension
from native_loader import NativeBundleReader
from precomputed_catalog import write_catalog,load_catalog
from precomputed_index import build_index

ODIN=shutil.which(os.environ.get("ODIN", "odin")) or os.environ.get("ODIN", "odin")


@unittest.skipUnless(sys.platform=='linux' and Path(ODIN).is_file() and shutil.which('cc'),'Linux Odin/C toolchain unavailable')
class CatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build=tempfile.TemporaryDirectory();cls.library,_=compile_extension(Path(cls.build.name),ODIN)
    @classmethod
    def tearDownClass(cls):cls.build.cleanup()
    def fixture(self,root):
        archive=root/'data.zip';index=root/'data.index'
        bodies={'gaia_catalog_pkg/__init__.py':b'from .child import VALUE\n',
                'gaia_catalog_pkg/child.py':b'VALUE=42\n',
                'gaia_catalog_pkg/unused.py':b'raise AssertionError("enumeration executed leaf")\n',
                'gaia_catalog_pkg/sub/__init__.py':b'', 'gaia_catalog_pkg/sub/deep.py':b'VALUE=8\n',
                'gaia_catalog_pkg/data.txt':b'resource', 'gaia_catalog_pkg/π.txt':b'unicode'}
        with zipfile.ZipFile(archive,'w') as bundle:
            for name,body in bodies.items():bundle.writestr(name,body)
        admitted=build_index(archive,index,encoding='binary');catalogs={}
        for mode in ('rows','tables'):
            catalogs[mode]=write_catalog(archive,index,admitted['index_sha256'],root/(mode+'.catalog'),mode=mode)
        return archive,index,admitted,catalogs,bodies
    def reader(self,archive,index,admitted,catalogs,mode):
        options={} if mode=='rebuilt' else dict(catalog_path=catalogs[mode]['path'],catalog_sha256=catalogs[mode]['sha256'])
        return NativeBundleReader(archive,index,index_sha256=admitted['index_sha256'],library=self.library,
                                  verify='local',catalog_mode=mode,**options)
    @contextmanager
    def mounted(self,provider):
        provider.install()
        try:yield
        finally:
            provider.close()
            for name in list(sys.modules):
                if name=='gaia_catalog_pkg' or name.startswith('gaia_catalog_pkg.'):del sys.modules[name]

    def test_equivalent_tables_lookup_enumeration_resources_and_no_catalog_export(self):
        with tempfile.TemporaryDirectory() as temp:
            archive,index,admitted,catalogs,bodies=self.fixture(Path(temp));expected=None
            for mode in ('rebuilt','rows','tables'):
                reader=self.reader(archive,index,admitted,catalogs,mode)
                provider=IndexedPathProvider(archive,archive_factory=lambda _:reader,resource_factory=BundleResources)
                guard=(mock.patch.object(reader,'infolist',side_effect=AssertionError('table reconstruction'))
                       if mode=='tables' else mock.patch.object(reader,'infolist',wraps=reader.infolist))
                with guard,self.mounted(provider):
                    provider.open_archive()
                    tables=(provider.modules,provider.packages,provider.children)
                    if expected is None:expected=tables
                    else:self.assertEqual(tables,expected)
                    for name,body in bodies.items():self.assertEqual(reader.read(name),body)
                    package=importlib.import_module('gaia_catalog_pkg')
                    self.assertEqual(package.VALUE,42)
                    rows=[(r.name,r.ispkg) for r in pkgutil.iter_modules(package.__path__)]
                    self.assertEqual(rows,[('child',False),('sub',True),('unused',False)])
                    self.assertNotIn('gaia_catalog_pkg.unused',sys.modules)
                    self.assertEqual(importlib.resources.files(package).joinpath('π.txt').read_bytes(),b'unicode')
                    self.assertIsNone(provider.find_spec('gaia_catalog_pkg.missing'))
                    if mode=='tables':self.assertEqual(reader.entries.created,0)

    def test_digest_index_runtime_version_and_mode_binding_and_failure_cleanup(self):
        with tempfile.TemporaryDirectory() as temp:
            archive,index,admitted,catalogs,_=self.fixture(Path(temp));path=Path(catalogs['tables']['path'])
            original=marshal.loads(path.read_bytes());before=len(list(Path('/proc/self/fd').iterdir()))
            for key,value in (('version',99),('runtime',('wrong',)),('index_sha256','0'*64),('mode','rows')):
                data=dict(original);data[key]=value;body=marshal.dumps(data);path.write_bytes(body)
                catalogs['tables']['sha256']=hashlib.sha256(body).hexdigest()
                with self.subTest(key=key),self.assertRaisesRegex(ValueError,'identity/version/mode'):
                    self.reader(archive,index,admitted,catalogs,'tables')
                self.assertEqual(len(list(Path('/proc/self/fd').iterdir())),before)
            with self.assertRaisesRegex(ValueError,'digest'):
                load_catalog(path,'0'*64,index_sha256=admitted['index_sha256'],mode='tables')

    def test_producer_rejects_mixed_modules_and_corrupt_index(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);archive=root/'mixed.zip';index=root/'mixed.index'
            with zipfile.ZipFile(archive,'w') as bundle:
                bundle.writestr('same.py',b'');bundle.writestr('same.pyc',b'')
            admitted=build_index(archive,index,encoding='binary')
            with self.assertRaisesRegex(ValueError,'mixed'):
                write_catalog(archive,index,admitted['index_sha256'],root/'bad.catalog',mode='tables')
            index.write_bytes(b'bad')
            with self.assertRaisesRegex(ValueError,'digest'):
                write_catalog(archive,index,admitted['index_sha256'],root/'bad.catalog',mode='rows')


if __name__=='__main__':unittest.main()
