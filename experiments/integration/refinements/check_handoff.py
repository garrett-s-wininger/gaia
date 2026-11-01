"""Post-review production-TU handoff check with actual event timestamps."""
import argparse,hashlib,importlib.util,json,os,random,shlex,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE));import refined_protocol as current

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main(a):
 for n in ['old_host','new_host','measured_client','project','ninja','work','output','lock']:setattr(a,n,getattr(a,n).resolve())
 a.work.mkdir(parents=True,exist_ok=False);a.output.mkdir(parents=True,exist_ok=True);root=a.project;env=dict(os.environ,LD_LIBRARY_PATH=str(a.ninja.parent.parent/'lib')+':'+os.environ.get('LD_LIBRARY_PATH',''))
 commands=subprocess.check_output([str(a.ninja),'-t','commands','ninja'],cwd=root,env=env,text=True).splitlines();cmd=next(shlex.split(c) for c in commands if ' -c src/version.cc ' in c);cmd=cmd[1:] if Path(cmd[0]).name=='ccache' else cmd;target=cmd[cmd.index('-o')+1]
 source={str(p.relative_to(root)):p.read_text() for p in root.rglob('*') if p.is_file() and p.suffix in ['.h','.hpp','.cc','.c','.inc']};source['build/browse_py.h']=(root/'build/browse_py.h').read_text();original=source['src/version.cc'];pins={str(p):sha(p) for p in [a.old_host,a.new_host,a.measured_client,HERE/'refined_protocol.py',HERE/'refine_host.py',Path(__file__)]}
 spec=importlib.util.spec_from_file_location('measured_client',a.measured_client);old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old);hosts={};generations={};rows=[]
 try:
  for label,module,path in [('measured',old,a.old_host),('hardened',current,a.new_host)]:
   hosts[label]=module.Host(path,a.work/label,True);generations[label]=module.admit(hosts[label],root,source,0)
  rng=random.Random(981)
  for block in range(7):
   body=original+'\nextern "C" int gaia_frame_probe_'+str(block)+'(){return '+str(block)+';}\n';order=['measured','hardened'];rng.shuffle(order);reference=None
   for label in order:
    module=old if label=='measured' else current;host=hosts[label];events=[]
    with a.lock.open('a') as lock:
     import fcntl;fcntl.flock(lock,fcntl.LOCK_EX);start=time.perf_counter_ns();generations[label]=module.admit(host,root,{'src/version.cc':body},generations[label]);row=module.request(host,root,cmd,target,generations[label],on_facts=lambda facts:events.append((time.perf_counter_ns(),facts)));end=time.perf_counter_ns()
    assert len(events)==1 and events[0][1]==row['facts'];assert events[0][0]<end
    actual=sha(root/target)
    if reference is None:reference=actual
    else:assert actual==reference
    rows.append({'block':block,'mode':label,'complete_ns':end-start,'editor_ns':events[0][0]-start,'object_sha256':actual,'facts_sha256':row['facts']['sha256'],'correct':True})
   (root/'src/version.cc').write_text(body);r=subprocess.run(cmd,cwd=root,env=env,capture_output=True,text=True);assert r.returncode==0,r.stderr;assert sha(root/target)==reference
 finally:
  (root/'src/version.cc').write_text(original)
  for h in hosts.values():h.close()
 assert pins=={p:sha(Path(p)) for p in pins}
 d={'status':'complete','implementation_and_tools':pins,'observations':rows,'stock_cli_object_checks':7,'scope':'One actual production version.cc TU, seven changed bodies. Measured implementation/client versus post-review framing/restoration hardening; early publication is actual receipt, not backfilled. No full-graph rerun or timing-equivalence claim.','frozen_inputs_verified_after':True};(a.output/'results.json').write_text(json.dumps(d,indent=2)+'\n')
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for n in ['old-host','new-host','measured-client','project','ninja','work','output','lock']:p.add_argument('--'+n,type=Path,required=True)
 main(p.parse_args())
