"""Separate intrusive real-workload lookup diagnostic; not latency evidence."""
import argparse
import json
import os
from pathlib import Path
import pstats
import subprocess
import sys

HERE=Path(__file__).resolve().parent


def run(args):
    data=json.loads(args.run.read_text());work=Path(data['source_snapshots']).parent;root=work/'flat-0';cache=root/'cache';produced=data['producer']['flat'];admission=json.loads((root/'installed.json').read_text());profile=args.output.with_suffix('.prof')
    env=os.environ.copy();env.update(GAIA_READER_KIND='compact-pack',GAIA_COMPACT_INDEX=str(cache/'objects/sha256'/produced['index_descriptor']['digest']),GAIA_COMPACT_PIN=produced['index_descriptor']['digest'],GAIA_PY_LOCK_PIN=admission['logical_pin'],GAIA_BINDING=str(root/'binding.json'),GAIA_BINDING_PIN=admission['binding_pin']);env.pop('GAIA_PY_LOCK',None)
    command=[sys.executable,'-I','-S','-B','-m','cProfile','-o',str(profile),str(HERE/'preindexed_bundle_worker.py'),'--root',str(cache),'--reader','python','--scenario','rest','--expected',str(work/'expected.json'),'--discovery','index']
    child=subprocess.run(command,env=env,capture_output=True,text=True,check=True);result=json.loads(child.stdout)
    if not result['correct']:raise ValueError('profiled workload failed')
    rows=[]
    for (filename,line,function),(primitive,calls,self_seconds,cumulative,callers) in sorted(pstats.Stats(str(profile)).stats.items(),key=lambda x:x[1][3],reverse=True):
        if Path(filename).name in ('compact_python.py','preindexed_bundle.py','indexed_path_loader.py','persistent_zip_loader.py'):
            rows.append(dict(file=Path(filename).name,line=line,function=function,calls=calls,self_seconds=self_seconds,cumulative_seconds=cumulative))
    args.output.write_text(json.dumps(dict(scope='Separate intrusive full-workload profile. Cumulative times overlap and cannot be compared to uninstrumented process medians.',correct=True,functions=rows[:50]),indent=2)+'\n')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);run(parser.parse_args())
