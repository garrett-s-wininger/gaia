"""Real stdlib documentation tests through an existing programmatic API."""
import contextlib,decimal,doctest,hashlib,importlib,io,json,sys,time
from pathlib import Path
MODULES=('difflib','statistics','fractions')
def pin(module):return hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()
def execute(request,cache):
    name=request['module']
    if name=='invalid':
        test=doctest.DocTestParser().get_doctest('>>> 1+1\n3\n',{},'injected','injected',0)
        runner=doctest.DocTestRunner();buffer=io.StringIO()
        with contextlib.redirect_stdout(buffer):result=runner.run(test)
        return dict(ok=False,failed=result.failed,attempted=result.attempted)
    if name not in MODULES:return dict(ok=False,error='unsupported module')
    if name not in cache:
        module=importlib.import_module(name);cache[name]=(module,pin(module))
    module,loaded_pin=cache[name];observed=pin(module)
    if request.get('source_sha256')!=loaded_pin or observed!=loaded_pin:return dict(ok=False,error='source generation mismatch')
    buffer=io.StringIO();start=time.perf_counter_ns()
    with contextlib.redirect_stdout(buffer):result=doctest.testmod(module,extraglobs={'Decimal':decimal.Decimal},report=False)
    return dict(ok=result.failed==0,failed=result.failed,attempted=result.attempted,body_ns=time.perf_counter_ns()-start,token=request['token'])
def main():
    cache={}
    for line in sys.stdin:
        request=json.loads(line)
        if request.get('stop'):break
        try:result=execute(request,cache)
        except Exception as exc:result=dict(ok=False,error=type(exc).__name__+': '+str(exc))
        print(json.dumps(result),flush=True)
if __name__=='__main__':main()
