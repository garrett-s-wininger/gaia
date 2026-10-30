from contextlib import contextmanager
import importlib
import importlib.machinery
import pkgutil
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import zipfile
import zipimport

import benchmark
from indexed_path_loader import IndexedPathProvider, IndexPathFinder


class IndexedPathTests(unittest.TestCase):
    def fixture(self, root, mode='source'):
        source=root/'source'
        files={'gaia_index_pkg/__init__.py':'VALUE=1\n',
               'gaia_index_pkg/leaf.py':'raise AssertionError("leaf executed during enumeration")\n',
               'gaia_index_pkg/sub/__init__.py':'VALUE=2\n',
               'gaia_index_pkg/sub/deep.py':'VALUE=3\n',
               'gaia_index_pkg/data.txt':'resource', 'unpackaged/orphan.py':'VALUE=4\n',
               'top.py':'VALUE=5\n', '__init__.py':'# not enumerated\n'}
        for name,body in files.items():
            p=source/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(body)
        directory=source
        if mode=='bytecode':
            directory=root/'bytecode';benchmark.precompile(source,directory)
        archive=root/'bundle.zip';benchmark.pack(directory,archive,zipfile.ZIP_STORED)
        return archive

    @contextmanager
    def mounted(self, provider):
        original=sys.path[:]
        provider.install();sys.path.insert(0,provider.archive_path)
        try:yield
        finally:
            provider.close();sys.path[:]=original
            for name in list(sys.modules):
                if name=='gaia_index_pkg' or name.startswith('gaia_index_pkg.'):
                    del sys.modules[name]

    def test_iteration_matches_stock_without_code_reads_or_zip_fallback(self):
        for mode in ('source','bytecode'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as temp:
                archive=self.fixture(Path(temp),mode)
                paths=[str(archive),str(archive)+'/gaia_index_pkg',str(archive)+'/gaia_index_pkg/sub']
                expected={p:[(r.name,r.ispkg) for r in pkgutil.iter_modules([p],'prefix.')] for p in paths}
                provider=IndexedPathProvider(archive)
                with self.mounted(provider):
                    with mock.patch.object(zipimport,'_read_directory',side_effect=AssertionError('ZIP fallback')), \
                         mock.patch.object(zipfile.ZipFile,'read',side_effect=AssertionError('payload read during discovery')):
                        for path in paths:
                            self.assertIsInstance(pkgutil.get_importer(path),IndexPathFinder)
                            self.assertEqual([(r.name,r.ispkg) for r in pkgutil.iter_modules([path],'prefix.')],expected[path])
                        self.assertEqual(provider.archive_opens,1)
                        self.assertEqual(provider.module_reads,0)

    def test_package_walk_imports_only_packages_and_reads_no_leaf_code(self):
        with tempfile.TemporaryDirectory() as temp:
            archive=self.fixture(Path(temp));provider=IndexedPathProvider(archive)
            with self.mounted(provider):
                package=importlib.import_module('gaia_index_pkg')
                with mock.patch.object(zipimport,'_read_directory',side_effect=AssertionError('ZIP fallback')):
                    names=[r.name for r in pkgutil.walk_packages(package.__path__,package.__name__+'.')]
                self.assertEqual(names,['gaia_index_pkg.leaf','gaia_index_pkg.sub','gaia_index_pkg.sub.deep'])
                self.assertNotIn('gaia_index_pkg.leaf',sys.modules)
                self.assertEqual(provider.module_reads,2)

    def test_owned_misses_stay_in_index_and_outside_paths_keep_normal_loading(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);archive=self.fixture(root);provider=IndexedPathProvider(archive)
            outside=root/'bundle.zip-other';outside.mkdir();(outside/'outside.py').write_text('VALUE=7\n')
            with self.mounted(provider):
                provider.open_archive()
                with mock.patch('os.stat',side_effect=AssertionError('filesystem probe')), \
                     mock.patch('importlib._bootstrap_external._path_stat',side_effect=AssertionError('importlib filesystem probe')):
                    found=importlib.machinery.PathFinder.find_spec('gaia_index_pkg.leaf',[str(archive)+'/gaia_index_pkg'])
                    self.assertEqual(found.origin,str(archive)+'/gaia_index_pkg/leaf.py')
                    self.assertEqual(provider.module_reads,0)
                    self.assertIsNone(importlib.machinery.PathFinder.find_spec('missing',[str(archive)]))
                    self.assertIsNone(importlib.machinery.PathFinder.find_spec('gaia_index_pkg.missing',[str(archive)+'/gaia_index_pkg']))
                    self.assertEqual(list(pkgutil.iter_modules([str(archive)+'/missing'])),[])
                with self.assertRaises(ImportError):provider.path_hook(str(outside))
                spec=importlib.machinery.PathFinder.find_spec('outside',[str(outside)])
                self.assertEqual(spec.origin,str(outside/'outside.py'))
                self.assertIsNone(pkgutil.get_importer(str(archive)+'/gaia_index_pkg').find_spec('top'))

    def test_install_is_lazy_idempotent_and_restores_prior_cache(self):
        with tempfile.TemporaryDirectory() as temp:
            archive=self.fixture(Path(temp));path=str(archive)
            old=pkgutil.get_importer(path);hooks=sys.path_hooks[:];meta=sys.meta_path[:]
            provider=IndexedPathProvider(archive)
            provider.install();provider.install()
            self.assertEqual(provider.archive_opens,0)
            finder=pkgutil.get_importer(path);self.assertIsInstance(finder,IndexPathFinder)
            self.assertIsNone(finder.find_spec('absent'))
            provider.close();provider.close()
            self.assertEqual(sys.path_hooks,hooks);self.assertEqual(sys.meta_path,meta)
            self.assertIs(sys.path_importer_cache[path],old)
            with self.assertRaises(ValueError):list(finder.iter_modules())

    def test_closing_overlapping_mounts_does_not_restore_closed_finder(self):
        with tempfile.TemporaryDirectory() as temp:
            archive=self.fixture(Path(temp));a,b=IndexedPathProvider(archive),IndexedPathProvider(archive)
            a.install();pkgutil.get_importer(str(archive));b.install()
            try:
                finder=pkgutil.get_importer(str(archive));self.assertIs(finder.provider,b)
                a.close();self.assertIs(pkgutil.get_importer(str(archive)),finder)
            finally:a.close();b.close()
            self.assertNotIsInstance(pkgutil.get_importer(str(archive)),IndexPathFinder)

    def test_invalid_mount_removes_hooks_on_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            archive=Path(temp)/'broken.zip';archive.write_bytes(b'invalid')
            hooks=sys.path_hooks[:];meta=sys.meta_path[:];provider=IndexedPathProvider(archive)
            provider.install()
            with self.assertRaises(zipfile.BadZipFile):provider.find_spec('anything')
            self.assertEqual(sys.path_hooks,hooks);self.assertEqual(sys.meta_path,meta)


if __name__=='__main__':unittest.main()
