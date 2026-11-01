"""Odin vector unions versus optimized loops and sparse lists on exact same sets."""
import argparse,array,ctypes,fcntl,hashlib,json,random,statistics,struct,subprocess,time
from pathlib import Path
HERE=Path(__file__).resolve().parent

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def fixture(path,rows,roots,degree,changed,queries,seed,relation=None):
 rng=random.Random(seed);words=(roots+63)//64;matrix=array.array('Q',[0])*(rows*words)
 if relation:
  names=list(relation['targets']);mapping={t:i for i,t in enumerate(names)}
  for i,targets in enumerate(relation['relation'].values()):
   for t in targets:
    j=mapping[t];matrix[i*words+j//64]|=1<<(j%64)
 else:
  for i in range(rows):
   for j in rng.sample(range(roots),degree):matrix[i*words+j//64]|=1<<(j%64)
 ids=array.array('I')
 for _ in range(queries):ids.extend(rng.sample(range(rows),changed))
 path.write_bytes(struct.pack('<4I',rows,words,queries,changed)+matrix.tobytes()+ids.tobytes())
 return {'path':str(path),'sha256':sha(path),'bytes':path.stat().st_size,'rows':rows,'roots':roots,'degree':degree,'changed':changed}

def main(a):
 for name in ['library','bench','work','output','lock']:setattr(a,name,getattr(a,name).resolve())
 a.work.mkdir(parents=True,exist_ok=False);a.output.mkdir(parents=True,exist_ok=True)
 pins={str(p):sha(p) for p in [a.library,a.bench,*HERE.glob('*.odin'),*HERE.glob('*.cpp'),*HERE.glob('*.py')]};start=time.perf_counter_ns();cases=[]
 if a.relation:
  relation=json.loads(a.relation.read_text());rows=len(relation['relation']);roots=len(relation['targets'])
  for changed in [1,min(8,rows)]:cases.append(('captured-'+str(changed),fixture(a.work/f'captured-{changed}.bin',rows,roots,None,changed,64,11+changed,relation)))
 for rows,roots,degree,label in [(4096,4096,4,'sparse-4096'),(1024,8192,2048,'dense-8192'),(16384,16384,16,'sparse-16384')]:
  for changed in [1,8,64]:cases.append((label+'-'+str(changed),fixture(a.work/f'{label}-{changed}.bin',rows,roots,degree,changed,64,29+changed)))
 preparation=time.perf_counter_ns()-start;results=[]
 for label,meta in cases:
  # Opaque shared-library calls prevent whole-loop elimination; all output words checked outside clocks.
  reps=4096 if meta['roots']<100 else 1024
  with a.lock.open('a') as lock:
   fcntl.flock(lock,fcntl.LOCK_EX);r=subprocess.run([str(a.bench),str(a.library),meta['path'],str(reps),'7'],capture_output=True,text=True,timeout=120)
  if r.returncode:raise RuntimeError(r.stderr)
  results.append({'label':label,'fixture':meta,'measurement':json.loads(r.stdout)});print(label,flush=True)
 assert pins=={p:sha(Path(p)) for p in pins};assert all(sha(Path(meta['path']))==meta['sha256'] for _,meta in cases)
 raw={'status':'complete','implementation_and_tools':pins,'fixture_preparation_ns':preparation,'cases':results,'frozen_inputs_verified_after':True,'scope':'Warm native query batches, immutable inverted dependency masks. Loop/tiling/SIMD algorithms versus CSR representation; no complete compiler claim, no strict scalar control, portable loop may autovectorize.'}
 (a.output/'results.json').write_text(json.dumps(raw,indent=2)+'\n')

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for n in ['library','bench','work','output','lock']:p.add_argument('--'+n,type=Path,required=True)
 p.add_argument('--relation',type=Path);main(p.parse_args())
