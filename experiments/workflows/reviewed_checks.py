"""Recheck the affected schema/persistence operations after review fixes."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import benchmark


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--work',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--checkpoint-host',type=Path,required=True);parser.add_argument('--lock',type=Path,required=True)
    parser.add_argument('--trials',type=int,default=11);parser.add_argument('--records',type=int,default=250)
    args=parser.parse_args();args.work.mkdir(parents=True,exist_ok=False)
    here=Path(__file__).parent
    paths=[here/name for name in ['schema_pipeline.py','benchmark.py','checkpoint.odin','reviewed_checks.py']]
    def pins():return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    source_pins=pins();result={'source_hashes':source_pins,'host_sha256':hashlib.sha256(args.checkpoint_host.read_bytes()).hexdigest(),
        'scope':'Review fixes reject conflicting schema names and non-not-found HEAD read errors. Repeated schema/propagation checks and one-shot checkpoint structural probe; original repository-query source unchanged and not rerun. Repository directory preparation outside operation clock; new_stored_bytes includes initial HEAD64B and is not device-write accounting.'}
    for name,operation in [('schema',benchmark.schema_experiment),('checkpoint',benchmark.checkpoint)]:
        with args.lock.open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX);result[name]=operation(args)
    assert source_pins==pins()
    result['source_pins_verified_after']=True
    args.output.mkdir(parents=True,exist_ok=True);raw=args.output/'results.json';raw.write_text(json.dumps(result,indent=2)+'\n')
    identity={'bytes':raw.stat().st_size,'sha256':hashlib.sha256(raw.read_bytes()).hexdigest()}
    (args.output/'raw-identity.json').write_text(json.dumps(identity,indent=2)+'\n')
    print(identity)


if __name__=='__main__':main()
