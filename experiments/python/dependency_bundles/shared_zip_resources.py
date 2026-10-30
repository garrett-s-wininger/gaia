"""Experimental Python path hook: stock ZIP imports, one ZIP resource handle.

This is scoped to one archive in an isolated benchmark process. It is not a
replacement package installer, interpreter, or generic environment hook.
"""

from importlib.resources.abc import TraversableResources
import zipfile
import zipimport


class SharedResources(TraversableResources):
    def __init__(self, provider, prefix):
        self.provider = provider
        self.prefix = prefix

    def files(self):
        return zipfile.Path(self.provider.open_archive(), self.prefix)


class SharedImporter(zipimport.zipimporter):
    def __init__(self, path, provider):
        super().__init__(path)
        self.provider = provider

    def get_resource_reader(self, fullname):
        prefix = self.prefix.replace("\\", "/")
        if self.is_package(fullname):
            prefix += fullname.rpartition(".")[2] + "/"
        return SharedResources(self.provider, prefix)


class SharedZipProvider:
    def __init__(self, archive_path):
        self.archive_path = archive_path
        self.archive = None
        self.archive_opens = 0

    def path_hook(self, path):
        if path == self.archive_path or path.startswith(self.archive_path + "/"):
            return SharedImporter(path, self)
        raise ImportError("outside the selected Gaia archive")

    def open_archive(self):
        if self.archive is None:
            self.archive = zipfile.ZipFile(self.archive_path)
            self.archive_opens += 1
        return self.archive

    def close(self):
        if self.archive is not None:
            self.archive.close()
