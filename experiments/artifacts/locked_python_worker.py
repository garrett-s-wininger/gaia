"""Run the unchanged real Django workload through an acquired packed reader."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python/dependency_bundles'))
import django_worker as worker
import locked_python

if __name__=='__main__':
    # Reuse the worker's exact existing CLI/workload/validation without editing it.
    import runpy
    import precomputed_index
    import os
    if 'GAIA_PY_LOCK' in os.environ:
        body=Path(os.environ['GAIA_PY_LOCK']).read_bytes();pin=os.environ['GAIA_PY_LOCK_PIN']
        precomputed_index.IndexedBundleReader=lambda root,*a,**kw:locked_python.PackedReader(root,body,pin)
    runpy.run_path(str(Path(worker.__file__)),run_name='__main__')
