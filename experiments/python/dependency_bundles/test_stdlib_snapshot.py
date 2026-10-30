from contextlib import contextmanager
import importlib
import importlib.resources
import inspect
import json
from pathlib import Path
import py_compile
import sys
import tempfile
import unittest
from unittest import mock

from build_stdlib_snapshot import build_snapshot
from precomputed_index import IndexedBundleReader
from stdlib_snapshot import DirectorySnapshot,MANIFEST,SnapshotLoader,StdlibSnapshotProvider


class StdlibSnapshotTests(unittest.TestCase):
    def fixture(self,root):
        source=root/'host';package=source/'gaia_boot_pkg';package.mkdir(parents=True)
        bodies={'__init__.py':'from . import child\n',
                'child.py':'VALUE=17\ndef answer():\n    return VALUE\nclass Marker:\n    value=17\n'}
        pairs=[]
        for name,body in bodies.items():
            path=package/name;path.write_text(body);pyc=root/(name+'c')
            py_compile.compile(str(path),cfile=str(pyc),doraise=True,invalidation_mode=py_compile.PycInvalidationMode.CHECKED_HASH)
            pairs.append((path,pyc))
        descriptor=build_snapshot(pairs,root/'snapshot',source)
        return descriptor,package,bodies

    def provider(self,d,backend):
        if backend=='directory':path=d['directory'];factory=DirectorySnapshot
        else:
            path=d['archive'];factory=lambda p:IndexedBundleReader(p,d['index'],index_sha256=d['index_sha256'],verify='local')
        return StdlibSnapshotProvider(path,archive_factory=factory,manifest_sha256=d['manifest_sha256'],host_root=d['host_root'])

    @contextmanager
    def mounted(self,provider):
        provider.install()
        try:yield
        finally:
            provider.close()
            for name in list(sys.modules):
                if name=='gaia_boot_pkg' or name.startswith('gaia_boot_pkg.'):del sys.modules[name]

    def test_snapshot_imports_and_inspection_survive_changed_host_sources(self):
        for backend in ('directory','bundle'):
            with self.subTest(backend=backend),tempfile.TemporaryDirectory() as temp:
                d,package,bodies=self.fixture(Path(temp));provider=self.provider(d,backend)
                (package/'child.py').write_text('raise AssertionError("mutable host source used")\n')
                with self.mounted(provider):
                    module=importlib.import_module('gaia_boot_pkg.child')
                    self.assertEqual(module.answer(),17)
                    self.assertIsInstance(module.__loader__,SnapshotLoader)
                    self.assertTrue(module.__file__.startswith('gaia-stdlib://'))
                    self.assertEqual(provider.source_reads,0)
                    self.assertIn('VALUE=17',inspect.getsource(module))
                    self.assertIn('return VALUE',inspect.getsource(module.answer))
                    self.assertIn('value=17',inspect.getsource(module.Marker))
                    data=importlib.resources.files('gaia_boot_pkg').joinpath('child.py').read_text()
                    self.assertEqual(data,bodies['child.py'])

    def test_package_fallback_and_native_extensions_keep_host_loaders(self):
        with tempfile.TemporaryDirectory() as temp:
            d,package,_=self.fixture(Path(temp));(package/'outside.py').write_text('VALUE=29\n')
            (package/'data.txt').write_text('host resource')
            with self.mounted(self.provider(d,'bundle')):
                outside=importlib.import_module('gaia_boot_pkg.outside')
                self.assertEqual(outside.VALUE,29)
                self.assertNotIsInstance(outside.__loader__,SnapshotLoader)
                self.assertEqual(importlib.resources.files('gaia_boot_pkg').joinpath('data.txt').read_text(),'host resource')
                native=importlib.import_module('_sqlite3')
                self.assertNotIsInstance(native.__loader__,SnapshotLoader)

    def test_admission_rejects_stale_source_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);d,package,_=self.fixture(root)
            (package/'child.py').write_text('VALUE=999\n')
            with self.assertRaisesRegex(ValueError,'identity mismatch'):
                build_snapshot([(package/'child.py',root/'child.pyc')],root/'bad',Path(d['host_root']))

    def test_runtime_mismatch_rejects_mount_and_cleans_hooks(self):
        with tempfile.TemporaryDirectory() as temp:
            import hashlib
            d,_,_=self.fixture(Path(temp));path=Path(d['directory'])/MANIFEST
            manifest=json.loads(path.read_text());manifest['runtime']['magic']='wrong'
            body=json.dumps(manifest).encode();path.write_bytes(body)
            d['manifest_sha256']=hashlib.sha256(body).hexdigest();provider=self.provider(d,'directory')
            hooks=sys.path_hooks[:];meta=sys.meta_path[:];provider.install()
            with self.assertRaisesRegex(ImportError,'interpreter identity'):provider.find_spec('gaia_boot_pkg')
            self.assertEqual(sys.path_hooks,hooks);self.assertEqual(sys.meta_path,meta)

    def test_no_source_reads_or_filesystem_checks_for_bundled_import(self):
        with tempfile.TemporaryDirectory() as temp:
            d,_,_=self.fixture(Path(temp));provider=self.provider(d,'bundle')
            with self.mounted(provider):
                provider.open_archive()
                with mock.patch('importlib._bootstrap_external._path_stat',side_effect=AssertionError('host probe')):
                    self.assertEqual(importlib.import_module('gaia_boot_pkg.child').answer(),17)
                self.assertEqual(provider.source_reads,0)
                self.assertEqual(provider.module_reads,2)


if __name__=='__main__':unittest.main()
