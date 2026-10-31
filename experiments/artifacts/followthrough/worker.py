"""Unmodified Django operation through one preconnected demand provider."""
import io,json,runpy,sys,time
from contextlib import redirect_stdout
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE.parents[1]/'storage'))
from admission import Client
from service import ModelIO,Profile
from reader import Reader
sys.path.insert(0,str(HERE.parent));sys.path.insert(0,str(HERE.parents[1]/'python/dependency_bundles'))
import compact_python,precomputed_index,indexed_path_loader

if __name__=='__main__':
    job=json.loads(sys.stdin.read());client=Client(job['socket']);model=ModelIO(job['scope'],Profile(**job['profile']))
    def pread(stream,path,offset,size):return client.read(offset,size)
    model.pread=pread
    precomputed_index.IndexedBundleReader=lambda root,*a,**kw:Reader(job,model)
    indexed_path_loader.IndexedPathProvider=compact_python.provider_type()
    first=[None]
    def audit(event,args):
        if event=='exec' and first[0] is None and '/django/' in args[0].co_filename:first[0]=time.perf_counter()
    sys.addaudithook(audit)
    captured=io.StringIO()
    try:
        with redirect_stdout(captured):runpy.run_path(str(HERE.parents[1]/'python/dependency_bundles/django_worker.py'),run_name='__main__')
        result=json.loads(captured.getvalue());result['index_storage']=model.stats();result['first_django_execution']=first[0];print(json.dumps(result))
    finally:client.close()
