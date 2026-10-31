"""Same real Django worker, explicit old/compact reader controls and setup clocks."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python/dependency_bundles'))
import django_worker as worker
import compact_python
import locked_python

if __name__=='__main__':
    import runpy
    import precomputed_index
    import indexed_path_loader
    import os
    import time
    kind=os.environ['GAIA_READER_KIND']
    if kind=='old-pack':
        body=Path(os.environ['GAIA_PY_LOCK']).read_bytes();pin=os.environ['GAIA_PY_LOCK_PIN']
        def factory(root,*a,**kw):
            begin=time.perf_counter();reader=locked_python.PackedReader(root,body,pin);reader.native_timings=dict(setup_seconds=time.perf_counter()-begin,integrity_policy='sha256-every-read');return reader
        precomputed_index.IndexedBundleReader=factory
    elif kind.startswith('compact-'):
        precomputed_index.IndexedBundleReader=lambda root,*a,**kw:compact_python.Reader(root,os.environ['GAIA_COMPACT_INDEX'],os.environ['GAIA_COMPACT_PIN'],os.environ['GAIA_PY_LOCK_PIN'])
        indexed_path_loader.IndexedPathProvider=compact_python.provider_type()
    elif kind=='old-zip':
        original=precomputed_index.IndexedBundleReader
        def factory(*a,**kw):
            begin=time.perf_counter();reader=original(*a,**kw);reader.native_timings=dict(setup_seconds=time.perf_counter()-begin,integrity_policy='crc32-every-read');return reader
        precomputed_index.IndexedBundleReader=factory
    else:raise ValueError('reader kind')
    runpy.run_path(str(Path(worker.__file__)),run_name='__main__')
