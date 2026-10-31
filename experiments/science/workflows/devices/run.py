"""Prepare graph fixtures, run real D3D12, preserve full-process and phase costs."""
import argparse,array,fcntl,hashlib,json,pathlib,statistics,struct,subprocess,time
HERE=pathlib.Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--work',type=pathlib.Path,required=True);p.add_argument('--graph',type=pathlib.Path,required=True);p.add_argument('--lock',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args();w=a.work;w.mkdir(parents=True,exist_ok=True);a.output.mkdir(parents=True,exist_ok=True)
 graph=json.loads(a.graph.read_text());edges=[(x,y) for x,y,weight in graph['training_edges']];actual=w/'actual.bin';actual.write_bytes(struct.pack('<II',len(graph['chunks']),len(edges))+b''.join(struct.pack('<II',*e) for e in edges))
 fixtures=[('captured-django-coaccess',actual)]
 for n,m in [(131072,1048576),(1048576,8388608)]:
  path=w/f'generated-{m}.bin';words=array.array('I');state=1
  for i in range(m):
   state=(1664525*state+1013904223)&0xffffffff;x=((state>>16)^state)%n;state=(1664525*state+1013904223)&0xffffffff;y=((state>>16)^state)%n;words.extend((x,y))
  # Deterministic labelled generated scaling, not a measured real dependency graph.
  path.write_bytes(struct.pack('<II',n,m)+words.tobytes());fixtures.append((f'generated-{m}',path))
 del words
 pins={str(p):sha(p) for p in [*HERE.glob('*.cpp'),*HERE.glob('*.hlsl'),HERE/'run.py',w/'dispatch',w/'frontier.dxil',a.graph,*[x[1] for x in fixtures]]}
 rows=[]
 for block in range(5):
  for label,path,stride in [(label+'-'+kind,path,stride) for label,path in fixtures for kind,stride in [('sparse',8),('dense',1)]]:
   with a.lock.open('a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX);start=time.perf_counter_ns();r=subprocess.run([str(w/'dispatch'),str(w/'frontier.dxil'),str(path),'12',str(stride)],capture_output=True,text=True);elapsed=time.perf_counter_ns()-start
   row={'block':block,'label':label,'process_ns':elapsed,'exit_code':r.returncode,'stderr':r.stderr,'stdout':r.stdout};rows.append(row)
   if r.returncode:raise RuntimeError(json.dumps(row))
   row['result']=json.loads(r.stdout);print(label,block,flush=True)
 assert all(sha(pathlib.Path(p))==v for p,v in pins.items()),'frozen source/input changed'
 raw={'status':'complete','backend':'D3D12 explicit hardware DXCore adapter, no CPU fallback','pins':pins,'rows':rows,'controls':'native C++ -O3 edge sweep and prebuilt CSR; exact readback each repetition; 1/8 active and full dense frontier separate; generated mixed-high/low LCG fixtures are synthetic','acquisition':json.loads((w/'acquisition.json').read_text())}
 out=a.output/'results.json';out.write_text(json.dumps(raw,indent=2)+'\n');summary={}
 for label,path in [(label+'-'+kind,path) for label,path in fixtures for kind in ['sparse','dense']]:
  rr=[r for r in rows if r['label']==label];samples=[s for r in rr for s in r['result']['samples'][1:]]
  summary[label]={'sessions':len(rr),'retained_samples':len(samples),'process_ms':statistics.median(r['process_ns']/1e6 for r in rr),'init_ms':statistics.median(r['result']['init_ms'] for r in rr),'pipeline_ms':statistics.median(r['result']['pipeline_ms'] for r in rr),'upload_allocate_ms':statistics.median(r['result']['upload_allocate_ms'] for r in rr),'csr_build_ms':statistics.median(r['result']['csr_build_ms'] for r in rr),'retained':{k:statistics.median(s[k] for s in samples) for k in ['cpu_ms','csr_ms','record_submit_ms','sync_ms','read_validate_ms','gpu_full_ms']},'first_gpu_ms':statistics.median(r['result']['samples'][0]['gpu_full_ms'] for r in rr),'all_equal':all(s['equal'] for r in rr for s in r['result']['samples'])}
 (a.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');(a.output/'raw-identity.json').write_text(json.dumps({'artifact':'experiments/science/workflows/devices/results/results.json','bytes':out.stat().st_size,'sha256':sha(out)},indent=2)+'\n')
if __name__=='__main__':main()
