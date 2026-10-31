"""Fresh normal interpreter workload; all dependency byte reads use explicit providers."""
import io
import json
import os
from pathlib import Path
import runpy
import sys
from contextlib import redirect_stdout

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE.parent/'artifacts'));sys.path.insert(0,str(HERE.parent/'python/dependency_bundles'))
import compact_python
import precomputed_index
import indexed_path_loader
from service import ModelIO,Profile
from reader import Reader

if __name__=='__main__':
    job=json.loads(sys.stdin.read());model=ModelIO(job['scope'],Profile(**job['profile']));precomputed_index.IndexedBundleReader=lambda root,*a,**kw:Reader(job,model);indexed_path_loader.IndexedPathProvider=compact_python.provider_type()
    captured=io.StringIO()
    with redirect_stdout(captured):runpy.run_path(str(HERE.parent/'python/dependency_bundles/django_worker.py'),run_name='__main__')
    result=json.loads(captured.getvalue());result['storage_model']=model.stats();print(json.dumps(result))
