"""Separate intrusive old-reader setup diagnostic; not randomized latency evidence."""
import argparse
import cProfile
import json
from pathlib import Path
import pstats
import time

import cache_store
import locked_python
import transfer as t


def run(args):
    body=args.lock.read_bytes();pin=t.digest(body);profile=cProfile.Profile()
    begin=time.perf_counter();locked_python.parse_lock(body,pin);parsed=time.perf_counter()
    owner=cache_store.Packed(args.cache);loaded=time.perf_counter();owner.close()
    profile.enable();reader=locked_python.PackedReader(args.cache,body,pin);profile.disable();reader.close()
    stats=pstats.Stats(profile);rows=[]
    for (filename,line,function),(primitive,calls,self_seconds,cumulative,callers) in sorted(stats.stats.items(),key=lambda x:x[1][3],reverse=True)[:25]:
        rows.append(dict(file=Path(filename).name,line=line,function=function,calls=calls,self_seconds=self_seconds,cumulative_seconds=cumulative))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(dict(scope='separate intrusive constructor diagnostic; overlapping cumulative times must not be added',lock_parse_seconds=parsed-begin,local_cache_load_seconds=loaded-parsed,old_reader_profile=rows),indent=2)+'\n')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--cache',type=Path,required=True);parser.add_argument('--lock',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);run(parser.parse_args())
