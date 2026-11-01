"""Reuse the exact retained scan workload with original and identity-cached hosts."""
import argparse,hashlib,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
BASE=HERE.parent/'hash_dispatch'

def main(a):
 source=(BASE/'run.py').read_text()
 old="[('llvm',a.llvm_host,None),('crypto_auto',a.crypto_host,None),('crypto_masked',a.crypto_host,'0:0:0:0:0')]"
 assert source.count(old)==1
 source=source.replace(old,"[('original',a.llvm_host,None),('refined',a.crypto_host,None)]")
 source=source.replace("new_facts[0]==new_facts[1]==new_facts[2]", "all(f==new_facts[0] for f in new_facts)")
 source=source.replace("'changed_generation_checks':3", "'changed_generation_checks':2")
 source=source[:source.index("if __name__=='__main__':")]
 namespace={'__file__':str(BASE/'run.py'),'__name__':'refined_scan_replay'};exec(compile(source,'<refined-scan-replay>','exec'),namespace);namespace['HERE']=HERE
 pins={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [BASE/'run.py',Path(__file__),HERE/'refine_host.py',a.llvm_host,a.crypto_host]}
 namespace['main'](a)
 assert pins=={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in pins}
 path=a.output.resolve()/'results.json';d=json.loads(path.read_text());d.pop('cpu_mask',None);d.pop('openssl_version',None);d['scope']='Original LLVM SHA-256 host versus cached immutable SHA-256 identities. Same 33-TU retained scan fixture and exact fields; no CPU backend substitution.';d['replay_sources']=pins;d['generated_replay_sha256']=hashlib.sha256(source.encode()).hexdigest();path.write_text(json.dumps(d,indent=2)+'\n')
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for n in ['llvm-host','crypto-host','project','ninja','work','output','lock']:p.add_argument('--'+n,type=Path,required=True)
 main(p.parse_args())
