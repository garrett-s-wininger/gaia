"""Django template-loader adapter over the standard package-resource interface.

Used equally by directories and bundles; the directory filesystem-loader control
separately measures the adapter's effect. No dependency source is modified.
"""
from importlib.resources import files
from pathlib import PurePosixPath

from django.apps import apps
from django.template import Origin, TemplateDoesNotExist
from django.template.loaders.base import Loader


class PackageLoader(Loader):
    def get_template_sources(self, template_name):
        path = PurePosixPath(template_name)
        if path.is_absolute() or '..' in path.parts:
            return
        for app in apps.get_app_configs():
            yield Origin(name=app.name+':templates/'+str(path), template_name=template_name, loader=self)

    def get_contents(self, origin):
        package, relative = origin.name.split(':', 1)
        try:
            return files(package).joinpath(*relative.split('/')).read_text(encoding='utf-8')
        except (FileNotFoundError, IsADirectoryError):
            raise TemplateDoesNotExist(origin) from None
