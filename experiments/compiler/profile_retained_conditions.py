"""Intrusive exporter call/allocation diagnostic, separate from build timings."""
import argparse
import cProfile
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import pstats
import tempfile
import tracemalloc
from types import MappingProxyType

from check_object_cache import decode_inputs
import incremental_conditions as previous
import retained_conditions as retained


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-run',type=Path,required=True)
    parser.add_argument('--seed-engine',default='gaia-rebound')
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    source=json.loads(args.source_run.read_text());work=Path(source['work']);seed=work/('seed-'+args.seed_engine)
    files=decode_inputs(work/'baseline.gci')
    masks=dict(zip(sorted(files),map(int,(work/'baseline.views').read_text().splitlines()[1:])) )
    result=json.loads((seed/'build/last-result.json').read_text())
    cwd=next(row['sample']['command'][3] for row in source['setup'] if row['engine']==args.seed_engine and row['state']=='unchanged')
    entries,valid=previous.read_cache(seed/'build/condition-fragments.gcf');assert valid
    missing=sorted(entries)[0];entries.pop(missing);cold=previous.encode_cache(entries)
    reports=[];expected=None
    with tempfile.TemporaryDirectory(prefix='gaia-producer-profile-') as tmp:
        for variant in ('incremental','retained'):
            cache=Path(tmp)/variant;cache.write_bytes(cold)
            producer=retained.Producer()
            if variant=='retained':
                producer.build(seed/'gaia-cache',result,files,masks,cwd,cache)
                state=producer.snapshot();fragments=dict(state.fragments);fragments.pop(missing)
                producer.restore(replace(state,fragments=MappingProxyType(fragments)))
            cache.write_bytes(cold)
            # Warm the source backing independently; the diagnostic compares
            # one missing fragment with otherwise unchanged admitted byte refs.
            for name in files:Path(name).read_bytes()
            call=previous.build_incremental if variant=='incremental' else producer.build
            tracemalloc.start();profile=cProfile.Profile();profile.enable()
            encoded,stats=call(seed/'gaia-cache',result,files,masks,cwd,cache)
            profile.disable();current,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
            if expected is None:expected=encoded
            else:assert encoded==expected
            functions=[]
            for (file,line,name),(cc,nc,tt,ct,callers) in pstats.Stats(profile).stats.items():
                if Path(file).name in ('condition_index.py','incremental_conditions.py','retained_conditions.py') or name in ("<built-in method _hashlib.openssl_sha256>","<method 'read' of '_io.FileIO' objects>"):
                    functions.append(dict(file=Path(file).name,function=name,calls=nc))
            reports.append(dict(variant=variant,stats=stats,traced_current_bytes=current,traced_peak_bytes=peak,functions=functions))
    paths=[Path(__file__),Path(previous.__file__),Path(retained.__file__)]
    value=dict(scope='Intrusive call/allocation diagnostic, not latency samples. One selected fragment missing; logical input bytes unchanged; initial retained construction excluded.',
               source_run=source['run_id'],wire_equal=True,sources={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},profiles=reports)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(value,indent=2)+'\n')


if __name__=='__main__':main()
