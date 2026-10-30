"""Path-entry discovery/enumeration over the existing admitted module table.

Regular source/bytecode packages only, as in PersistentZipProvider. Owned paths
never delegate to zipimport. Other sys.path entries retain their normal hooks.
The payload reader and archive format are unchanged.
"""
import importlib.abc
import os
import sys

from persistent_zip_loader import PersistentZipProvider
from native_catalog import RootedMap


class IndexPathFinder(importlib.abc.PathEntryFinder):
    def __init__(self, provider, path):
        self.provider, self.path = provider, path

    def find_spec(self, fullname, target=None):
        provider = self.provider
        if provider.opening:
            return None
        provider.open_archive()
        provider.path_lookups += 1
        parent = provider.packages.get(self.path)
        if parent is None or fullname.rpartition('.')[0] != parent:
            provider.path_misses += 1
            return None
        spec = provider.find_spec(fullname, target=target)
        if spec is None:provider.path_misses += 1
        return spec

    def iter_modules(self, prefix=''):
        provider = self.provider
        if provider.opening:
            return
        provider.open_archive()
        provider.enumerations += 1
        for name, package in provider.children.get(self.path, ()):
            yield prefix+name, package

    def invalidate_caches(self):
        # The mount describes an immutable admitted snapshot.
        pass


class IndexedPathProvider(PersistentZipProvider):
    def __init__(self, archive_path, *args, **kwargs):
        super().__init__(os.path.abspath(archive_path), *args, **kwargs)
        self.packages, self.children = {}, {}
        self.path_lookups = self.path_misses = self.enumerations = 0
        self._indexed = self._installed = self._closed = False
        self._hook = self.path_hook
        self._previous = {}

    def owns_path(self, path):
        return isinstance(path, str) and (path == self.archive_path or path.startswith(self.archive_path+'/'))

    def path_hook(self, path):
        if self._closed or not self.owns_path(path):
            raise ImportError(path)
        suffix = path[len(self.archive_path):]
        if suffix and any(p in ('', '.', '..') for p in suffix[1:].split('/')):
            raise ImportError(path)
        # Do not open here: imports needed by archive bootstrap must be able to
        # traverse this entry without reentering the provider or stock ZIP parser.
        return IndexPathFinder(self, path)

    def open_archive(self):
        if self._closed:raise ValueError('indexed package mount is closed')
        try:
            archive = super().open_archive()
            if not self._indexed:
                if getattr(archive,'native_provider',False):
                    self.packages=RootedMap(self.archive_path,archive.precomputed_packages)
                    self.children=RootedMap(self.archive_path,archive.precomputed_children)
                    self._indexed=True
                    return archive
                if hasattr(archive,'precomputed_packages'):
                    def rooted(relative):return self.archive_path+('/'+relative if relative else '')
                    self.packages={rooted(p):n for p,n in archive.precomputed_packages.items()}
                    self.children={rooted(p):rows for p,rows in archive.precomputed_children.items()}
                    self._indexed=True
                    return archive
                packages = {self.archive_path: ''}
                package_names = {'': self.archive_path}
                for name, (member, package) in self.modules.items():
                    if package:
                        path = self.archive_path+'/'+member.rsplit('/', 1)[0]
                        packages[path] = name
                        package_names[name] = path
                children = {path: [] for path in packages}
                for name, (_, package) in self.modules.items():
                    parent, _, child = name.rpartition('.')
                    path = package_names.get(parent)
                    if path is not None and child != '__init__':
                        children[path].append((child, package))
                self.packages = packages
                self.children = {path: tuple(sorted(rows)) for path, rows in children.items()}
                self._indexed = True
            return archive
        except BaseException:
            self.close()
            raise

    def install(self):
        if self._closed:raise ValueError('indexed package mount is closed')
        if self._installed:return
        for path, finder in tuple(sys.path_importer_cache.items()):
            if self.owns_path(path):
                self._previous[path] = finder
                del sys.path_importer_cache[path]
        sys.path_hooks.insert(0, self._hook)
        sys.meta_path.insert(0, self)
        self._installed = True

    def close(self):
        if self._installed:
            sys.path_hooks[:] = [hook for hook in sys.path_hooks if hook is not self._hook]
            sys.meta_path[:] = [finder for finder in sys.meta_path if finder is not self]
            for path, finder in tuple(sys.path_importer_cache.items()):
                if isinstance(finder, IndexPathFinder) and finder.provider is self:
                    del sys.path_importer_cache[path]
            for path, previous in self._previous.items():
                if isinstance(previous, IndexPathFinder) and previous.provider._closed:
                    continue
                sys.path_importer_cache.setdefault(path, previous)
            self._previous.clear()
            self._installed = False
        self._closed = True
        super().close()
