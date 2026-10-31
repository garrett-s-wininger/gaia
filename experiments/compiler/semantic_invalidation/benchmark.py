"""Measure text invalidation versus normalized-AST candidates with an IR guard."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import random
import shutil
import struct
import subprocess
import time
from semantic_cache import Cache,Compiler,sha
import context
from ccache_control import Ccache

HERE=Path(__file__).resolve().parent


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2)+'\n')


def commands(path):
    body=path.read_bytes()
    if body[:8]!=b'GAIACRQ1':raise ValueError('request version')
    count=struct.unpack_from('<Q',body,8)[0];at=16;result=[]
    if not 0<count<=64:raise ValueError('request count')
    for _ in range(count):
        size=struct.unpack_from('<I',body,at)[0];at+=4;args=[]
        for _ in range(size):
            n=struct.unpack_from('<I',body,at)[0];at+=4
            if n>4096 or at+n>len(body):raise ValueError('request argument bound')
            args.append(body[at:at+n].decode());at+=n
        result.append(args)
    if at!=len(body):raise ValueError('request tail')
    return result


def scenarios(original):
    return {'unchanged':original,'comment':original+b'\n/* semantic-cache comment probe */\n','blank-lines':b'\n\n'+original,'unused-macro':original+b'\n#define GAIA_UNUSED_SEMANTIC_PROBE 19\n','unused-type':original+b'\ntypedef unsigned long GaiaUnusedSemanticProbe;\n','semantic':original+b'\nstatic __attribute__((used)) const unsigned gaia_semantic_probe=19;\n'}


def main(args):
    if args.ccache:
        import os
        prefix=str(args.ccache.resolve().parent.parent/'lib');os.environ['LD_LIBRARY_PATH']=prefix+(os.pathsep+os.environ['LD_LIBRARY_PATH'] if os.environ.get('LD_LIBRARY_PATH') else '')
    origin=json.loads(args.inputs.read_text());origin_work=Path(origin['work']);plan=commands(origin_work/'commands.gcr')
    sources=[Path(v) for command in plan for v in command if v.endswith('.c')]
    import os
    old=Path(os.path.commonpath(sources));runid=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ');work=HERE/'_work'/runid;work.mkdir(parents=True)
    project=work/'project';shutil.copytree(old,project)
    data=dict(run_id=runid,status='running',trials=args.trials,source_archive_sha256=origin['source_archive_sha256'],origin_run=origin['run_id'],modes=args.modes,scenarios=args.scenarios,cases=[],preparation={},ast_helper_sha256=sha(args.ast_helper.read_bytes()) if args.ast_helper else None,direct_ast_helper_sha256=sha(args.direct_ast_helper.read_bytes()) if args.direct_ast_helper else None,source_sha256={p.name:sha(p.read_bytes()) for p in HERE.iterdir() if p.suffix in ('.py','.cpp')})
    frozen=work/'sources';frozen.mkdir()
    for name in data['source_sha256']:shutil.copyfile(HERE/name,frozen/name)
    data['source_snapshots']=str(frozen);args.output.mkdir(parents=True,exist_ok=False);rng=random.Random(19141)
    for suffix in args.sources:
        matches=[c for c in plan if any(v.endswith('/'+suffix) for v in c)]
        if len(matches)!=1:raise ValueError('unique source selection required '+suffix)
        command=[s.replace(str(old),str(project)) for s in matches[0]];source=next(Path(v) for v in command if v.endswith('.c'));original=source.read_bytes();variants={name:body for name,body in scenarios(original).items() if name in args.scenarios}
        compiler=Compiler(command,project,work/suffix.replace('/','-'),args.ast_helper,args.direct_ast_helper);fixed=context.snapshot(command,project,source,compiler.work);before=context.verify(fixed);cache=Cache(compiler,'guarded-ast');setup=cache.seed();entry=cache.entries[0]
        baseline_preprocessed,_=compiler.preprocess();references={};diagnostics={};reference_stats={};preprocessor_sha256={}
        for scenario,body in variants.items():
            source.write_bytes(body);output=compiler.work/('reference-'+scenario+'.o');stats=compiler.full(output);references[scenario]=sha(output.read_bytes());diagnostics[scenario]=stats['stderr'];reference_stats[scenario]=stats;preprocessed,_=compiler.preprocess();preprocessor_sha256[scenario]=sha(preprocessed)
        source.write_bytes(original)
        ccache=Ccache(args.ccache,compiler,entry['object']) if args.ccache else None
        data['preparation'][suffix]=dict(seed=setup,command=command,fixed_context=fixed,context_before=before,reference_stats=reference_stats,baseline_preprocessor_sha256=sha(baseline_preprocessed),preprocessor_sha256=preprocessor_sha256,source_bytes=len(original),baseline_object_sha256=sha(entry['object']),reference_sha256=references,diagnostics=diagnostics)
        if ccache:data['preparation'][suffix]['ccache']=dict(preparation=ccache.preparation,version=ccache.version,binary_sha256=ccache.binary_sha256,config=ccache.config.read_text())
        configurations=[(mode,scenario) for mode in data['modes'] for scenario in variants]
        for block in range(args.trials):
            order=configurations.copy();rng.shuffle(order)
            for mode,scenario in order:
                source.write_bytes(variants[scenario]);current=ccache if mode=='ccache' else Cache(compiler,mode)
                if mode!='ccache':current.entries=[entry]
                output=compiler.work/'current.o';row=current.call(output);actual=sha(output.read_bytes());correct=actual==references[scenario]
                row.update(block=block,mode=mode,scenario=scenario,source=suffix,object_sha256=actual,correct=correct)
                if mode!='ast' and not correct:raise ValueError('guarded/current compiler object differs '+str(row))
                data['cases'].append(row);save(args.output/'results.json',data)
                print(block,suffix,mode,scenario,round(row['seconds']*1000,2),'ms','hit',row['hit'],'correct',correct,flush=True)
        source.write_bytes(original)
        data['preparation'][suffix]['context_after']=context.verify(fixed)
        if ccache and sha(ccache.binary.read_bytes())!=ccache.binary_sha256:raise ValueError('ccache tool changed')
    if args.ast_helper and sha(args.ast_helper.read_bytes())!=data['ast_helper_sha256']:raise ValueError('helper changed')
    if args.direct_ast_helper and sha(args.direct_ast_helper.read_bytes())!=data['direct_ast_helper_sha256']:raise ValueError('direct helper changed')
    data['status']='complete';save(args.output/'results.json',data)
    save(args.output/'validation.json',dict(passed=all(r['correct'] for r in data['cases'] if r['mode']!='ast'),objects_checked=len(data['cases']),ast_only_mismatches=sum(not r['correct'] for r in data['cases'] if r['mode']=='ast'),raw_sha256=sha((args.output/'results.json').read_bytes())))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,required=True)
    parser.add_argument('--ast-helper',type=Path)
    parser.add_argument('--direct-ast-helper',type=Path)
    parser.add_argument('--ccache',type=Path)
    parser.add_argument('--sources',nargs='+',default=['common/zstd_common.c','compress/zstd_lazy.c'])
    parser.add_argument('--trials',type=int,default=3)
    parser.add_argument('--modes',nargs='+',choices=['text','ast','guarded-ast','ir','ccache'],default=['text','ast','guarded-ast','ir'])
    parser.add_argument('--scenarios',nargs='+',choices=['unchanged','comment','blank-lines','unused-macro','unused-type','semantic'],default=['unchanged','comment','blank-lines','unused-macro','semantic'])
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if 'ccache' in args.modes and not args.ccache:parser.error('ccache mode requires --ccache')
    if args.trials<1:parser.error('positive trials required')
    main(args)
