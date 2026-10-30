"""One process-lifetime ZIP/index for both modules and package resources.

Deliberately supports only this experiment's regular pure-Python packages and
source-only OR interpreter-compatible sourceless bytecode inputs. Native modules,
namespace packages and mixed source/cache policy are outside this prototype.
"""

import importlib.abc
import importlib.util
from importlib.resources.abc import TraversableResources
import marshal
from pathlib import PurePosixPath
import types
import zipfile


class ResourceReader(TraversableResources):
    def __init__(self, provider, prefix):
        self.provider = provider
        self.prefix = prefix

    def files(self):
        return zipfile.Path(self.provider.open_archive(), self.prefix)


class ModuleLoader(importlib.abc.InspectLoader):
    def __init__(self, provider, fullname):
        self.provider = provider
        self.fullname = fullname

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        exec(self.get_code(module.__name__), module.__dict__)

    def get_filename(self, fullname):
        member, _ = self.provider.modules[fullname]
        return self.provider.archive_path + "/" + member

    def is_package(self, fullname):
        return self.provider.modules[fullname][1]

    def get_code(self, fullname):
        member, _ = self.provider.modules[fullname]
        archive=self.provider.open_archive()
        if member.endswith('.pyc') and hasattr(archive,'load_code'):
            code=archive.load_code(member)
            self.provider.module_reads+=1
            return code
        data = archive.read(member)
        self.provider.module_reads += 1
        if member.endswith(".py"):
            return compile(data, self.get_filename(fullname), "exec", dont_inherit=True)
        if len(data) < 16 or data[:4] != importlib.util.MAGIC_NUMBER:
            raise ImportError(f"invalid/interpreter-incompatible bytecode: {fullname}")
        if int.from_bytes(data[4:8], "little") & ~3:
            raise ImportError(f"unsupported bytecode flags: {fullname}")
        try:
            code = marshal.loads(data[16:])
        except (EOFError, ValueError, TypeError) as error:
            raise ImportError(f"invalid bytecode body: {fullname}") from error
        if not isinstance(code, types.CodeType):
            raise ImportError(f"bytecode payload is not a code object: {fullname}")
        return code

    def get_source(self, fullname):
        member, _ = self.provider.modules[fullname]
        if member.endswith(".pyc"):
            return None
        return importlib.util.decode_source(self.provider.open_archive().read(member))

    def get_resource_reader(self, fullname):
        member, _ = self.provider.modules[fullname]
        parent = PurePosixPath(member).parent.as_posix()
        factory = self.provider.resource_factory or ResourceReader
        return factory(self.provider, "" if parent == "." else parent + "/")


class PersistentZipProvider(importlib.abc.MetaPathFinder):
    def __init__(self, archive_path, archive_factory=zipfile.ZipFile, resource_factory=None):
        self.archive_path = archive_path
        self.archive = None
        self.archive_opens = 0
        self.module_reads = 0
        self.modules = {}
        self.opening = False
        self.archive_factory = archive_factory
        self.resource_factory = resource_factory

    def open_archive(self):
        if self.archive is None:
            # ZIP decoding can import a stdlib codec before this index exists.
            # Let normal importers handle that bootstrap instead of recursing.
            self.opening = True
            try:
                self.archive = self.archive_factory(self.archive_path)
            finally:
                self.opening = False
            self.archive_opens += 1
            if hasattr(self.archive,'precomputed_modules'):
                self.modules=self.archive.precomputed_modules
                return self.archive
            for info in self.archive.infolist():
                member = info.filename
                if not member.endswith((".py", ".pyc")) or info.is_dir():
                    continue
                stem = member[:-4] if member.endswith(".pyc") else member[:-3]
                package = stem.endswith("/__init__")
                if package:
                    stem = stem[:-len("/__init__")]
                name = stem.replace("/", ".")
                if name in self.modules:
                    raise ImportError(f"ambiguous/mixed source-bytecode module: {name}")
                self.modules[name] = (member, package)
        return self.archive

    def find_spec(self, fullname, path=None, target=None):
        if self.opening:
            return None
        # First discovery opens/indexes the bundle inside the timed import phase.
        self.open_archive()
        if fullname not in self.modules:
            return None
        member, package = self.modules[fullname]
        loader = ModuleLoader(self, fullname)
        origin = self.archive_path + "/" + member
        locations = [origin.rsplit("/", 1)[0]] if package else None
        return importlib.util.spec_from_file_location(
            fullname, origin, loader=loader, submodule_search_locations=locations)

    def close(self):
        if self.archive is not None:
            self.archive.close()
