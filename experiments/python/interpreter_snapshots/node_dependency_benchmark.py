#!/usr/bin/env python3
"""Real pinned TypeScript initialization, matched bundle, and startup snapshots."""
import argparse
import base64
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import statistics
import subprocess
import tarfile
import time

HERE=Path(__file__).resolve().parent
MODES=('require','bundle','snapshot','snapshot-no-codecache')
SOURCES=[dict(name='features.ts',text='''export interface User { name: string; age?: number }
export class Directory<T extends User> {
  private users: T[] = [];
  add(user: T): void { this.users.push(user); }
  describe(): string[] { return this.users.map(u => `${u.name}:${u.age ?? 0}`); }
}
export async function fetchUser(name: string): Promise<User> { return {name}; }
export const directory = new Directory<User>();
'''),dict(name='syntax-error.ts',text='''export const broken: number = ;
export function recover<T>(x: T): T { return x; }
''')]

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):Path(path).write_text(json.dumps(value,indent=2)+'\n')

def extract(corpus,dest):
    provenance=json.loads((corpus/'provenance.json').read_text());archive=corpus/'typescript-5.9.3.tgz';body=archive.read_bytes()
    alg,pin=provenance['dist']['integrity'].split('-',1)
    if alg!='sha512' or base64.b64encode(hashlib.sha512(body).digest()).decode()!=pin or sha(archive)!=provenance['tarball_sha256']:
        raise ValueError('TypeScript integrity mismatch')
    dest.mkdir()
    with tarfile.open(archive) as tf:
        for member in tf.getmembers():
            name=Path(member.name)
            if name.is_absolute() or '..' in name.parts or member.issym() or member.islnk():raise ValueError('unsafe corpus path')
            if member.isfile():
                target=dest/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(tf.extractfile(member).read())
    package=json.loads((dest/'package/package.json').read_text())
    if package['name']!='typescript' or package['version']!='5.9.3':raise ValueError('wrong compiler package')
    return provenance,dest/'package/lib/typescript.js'

def prepare(args):
    args.output=args.output.resolve();args.corpus=args.corpus.resolve()
    args.output.mkdir(parents=True,exist_ok=True);work=args.output/'work';work.mkdir()
    provenance,compiler=extract(args.corpus,work/'corpus');source=compiler.read_text();adapter=(HERE/'typescript_workload.js').read_text()
    # Preserve the upstream CommonJS body byte-for-byte inside its standard
    # wrapper. No dependency code edits, dynamic eval, stubs or dropped exports.
    bundle='''const ts = (() => { const module = {exports:{}};
(function(module,exports,require,__filename,__dirname) {\n'''+source+'''\n})(module,module.exports,require,'''+json.dumps(str(compiler))+','+json.dumps(str(compiler.parent))+''');
return module.exports; })();\n'''+adapter
    entry=work/'bundle.cjs';entry.write_text(bundle)
    ordinary=work/'require.cjs';ordinary.write_text('const ts = require('+json.dumps(str(compiler))+');\n'+adapter)
    setup=[]
    for mode,no_code_cache in [('snapshot',False),('snapshot-no-codecache',True)]:
        blob=work/(mode+'.blob');config=work/(mode+'.json')
        write(config,dict(builder=str(entry),withoutCodeCache=no_code_cache))
        start=time.perf_counter();p=subprocess.run([args.node,'--snapshot-blob',str(blob),'--build-snapshot-config',str(config)],
             env=dict(os.environ,GAIA_INITIALIZATION_MARKER='BUILD-'+mode),cwd=work,capture_output=True,text=True,check=True)
        setup.append(dict(mode=mode,seconds=time.perf_counter()-start,bytes=blob.stat().st_size,sha256=sha(blob),stderr=p.stderr))
    return work,provenance,compiler,entry,ordinary,setup

def semantic(value):return dict(version=value['state']['version'],exports=value['state']['exports'],operations=value['operations'])

def run(args):
    started=time.perf_counter();work,provenance,compiler,entry,ordinary,setup=prepare(args)
    data=dict(run_id=datetime.now(timezone.utc).isoformat(),node=subprocess.check_output([args.node,'--version'],text=True).strip(),
              node_sha256=sha(args.node),source_sha256={p.name:sha(p) for p in [HERE/'typescript_workload.js',HERE/'node_dependency_benchmark.py']},
              compiler_sha256=sha(compiler),compiler_bytes=compiler.stat().st_size,bundle_sha256=sha(entry),bundle_bytes=entry.stat().st_size,
              provenance=provenance,prepare_seconds=time.perf_counter()-started,setup=setup,trials=args.trials,
              scope='Fresh process full launch+request+stdout+normal exit; warm page cache. Snapshot retains compiler initialization only, not request results.',
              cases=[],audit=[])
    frozen=work/'sources';frozen.mkdir()
    for name in data['source_sha256']:shutil.copyfile(HERE/name,frozen/name)
    data['source_snapshots']=str(frozen)
    expected={};rng=random.Random(773);samples={m:[] for m in MODES}
    request_dirs=[work/'request-a',work/'request-b']
    for directory in request_dirs:directory.mkdir()
    for block in range(-1,args.trials):
        order=list(MODES);rng.shuffle(order)
        for mode in order:
            token=f'{block}-{mode}';marker=work/(token+'.exit');current_cwd=request_dirs[block%2]
            sources=[dict(row) for row in SOURCES]
            sources[0]['text']+=f'\nexport const requestSequence = {block+2};\n'
            request=dict(token=token,exitMarker=str(marker),sources=sources)
            cmd=[args.node,str(ordinary if mode=='require' else entry),token] if mode in ('require','bundle') else [args.node,'--snapshot-blob',str(work/(mode+'.blob')),'--',token]
            env=dict(os.environ,GAIA_REQUEST_TOKEN=token,GAIA_INITIALIZATION_MARKER='RUNTIME-'+token)
            before=time.perf_counter();p=subprocess.run(cmd,input=json.dumps(request),cwd=current_cwd,env=env,capture_output=True,text=True,check=True);elapsed=time.perf_counter()-before
            if p.stderr:raise RuntimeError(p.stderr)
            value=json.loads(p.stdout)
            if value['token']!=token or value['cwd']!=str(current_cwd) or value['compilerCwd']!=str(current_cwd):raise ValueError('current request/cwd not rebound')
            if marker.read_text()!=token:raise ValueError('normal exit marker absent')
            if value['state']['version']!='5.9.3' or value['state']['exports']<2000:raise ValueError('compiler API not initialized')
            if mode.startswith('snapshot'):
                if value['state']['marker']!='BUILD-'+mode:raise ValueError('snapshot reran initialization')
            elif value['state']['marker']!='RUNTIME-'+token:raise ValueError('ordinary initialization not executed')
            result=semantic(value)
            if block not in expected:expected[block]=result
            elif result!=expected[block]:raise ValueError('real compiler output differs')
            if block>=0:samples[mode].append(dict(block=block,seconds=elapsed,validated=True,**value))
            print(block,mode,f'{elapsed*1000:.2f} ms',flush=True)
    # A source-removal proof cannot accidentally fall back to ordinary require:
    # both snapshot modes must still execute the same compiler outputs.
    hidden=compiler.with_suffix('.hidden');compiler.rename(hidden)
    try:
        for mode in MODES[2:]:
            token='audit-'+mode;marker=work/(token+'.exit');sources=[dict(row) for row in SOURCES];sources[0]['text']+='\nexport const requestSequence = 1;\n'
            request=dict(token=token,exitMarker=str(marker),sources=sources)
            p=subprocess.run([args.node,'--snapshot-blob',str(work/(mode+'.blob')),'--',token],
                input=json.dumps(request),cwd=request_dirs[0],env=dict(os.environ,GAIA_REQUEST_TOKEN=token,GAIA_INITIALIZATION_MARKER='MUST-NOT-INITIALIZE'),capture_output=True,text=True,check=True)
            value=json.loads(p.stdout)
            if semantic(value)!=expected[-1] or marker.read_text()!=token:raise ValueError('source absent audit failed')
            data['audit'].append(dict(mode=mode,source_absent=True,outputs_match=True,initialization_marker=value['state']['marker']))
    finally:hidden.rename(compiler)
    data['cases']=[dict(mode=m,samples=ss) for m,ss in samples.items()];write(args.output/'results.json',data)
    summary={k:v for k,v in data.items() if k!='cases'};summary['raw_sha256']=sha(args.output/'results.json');summary['cases']=[]
    for mode,ss in samples.items():
        summary['cases'].append(dict(mode=mode,median_ms=statistics.median(s['seconds'] for s in ss)*1000,
            min_ms=min(s['seconds'] for s in ss)*1000,max_ms=max(s['seconds'] for s in ss)*1000,
            rss_median_bytes=statistics.median(s['memory']['rss'] for s in ss),
            memory_median_bytes={key:statistics.median(s['memory'][key] for s in ss) for key in ss[0]['memory']},
            paired_wins_vs_bundle=sum(a['seconds']<b['seconds'] for a,b in zip(ss,samples['bundle'])),
            paired_wins_vs_require=sum(a['seconds']<b['seconds'] for a,b in zip(ss,samples['require'])),blocks=len(ss)))
    write(args.output/'summary.json',summary);write(args.output/'validation.json',dict(passed=True,operations=args.trials*4,
        compiler_outputs_diagnostics_ast_and_requests_match=True,normal_exit_markers_match=True,source_absent_audits=len(data['audit']),raw_sha256=summary['raw_sha256']))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--node',default='/usr/bin/node');p.add_argument('--trials',type=int,default=7)
    p.add_argument('--corpus',type=Path,default=HERE/'_work/typescript-corpus');p.add_argument('--output',type=Path,default=HERE/'_work/typescript-results')
    a=p.parse_args()
    if a.trials<1:p.error('trials must be positive')
    run(a)
