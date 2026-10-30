#!/usr/bin/env python3
"""Summarize separately collected workload-scoped traces and execution profiles."""
import argparse
import hashlib
from collections import Counter,defaultdict
from datetime import datetime,timezone
import json
from pathlib import Path
import pstats
import re
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
import benchmark

METADATA={'newfstatat','fstat','stat','statx','lstat','access','faccessat','faccessat2','readlink','readlinkat','statfs','fstatfs'}


def category(filename,name):
    if 'marshal.loads' in name:return 'Bytecode decoding'
    if 'builtins.__build_class__' in name:return 'Class construction'
    if 'zipimport' in filename or filename.endswith('/pkgutil.py'):return 'ZIP/module enumeration'
    if 'importlib._bootstrap' in filename:return 'Import machinery'
    if any(filename.endswith('/'+n) for n in ('persistent_zip_loader.py','indexed_path_loader.py','native_loader.py','precomputed_index.py','binary_index.py','bundle_access.py')):
        return 'Bundle provider'
    if '/django_fixture/' in filename:return 'Project fixture'
    if '/django/' in filename:return 'Django code'
    if '/rest_framework/' in filename or '/django_filters/' in filename:return 'REST/filter code'
    if filename=='~' and any(s in name for s in ('posix.','_io.')):return 'C filesystem primitives'
    return 'Other stdlib/runtime'


def summarize(args):
    parent=json.loads(args.inputs.read_text());cases=[]
    worker=benchmark.HERE/'django_worker.py'
    relative=str(worker.relative_to(benchmark.HERE.parent.parent))
    if hashlib.sha256(worker.read_bytes()).hexdigest()!=parent['consumer_implementation_sha256'][relative]:
        raise ValueError('worker differs from parent run; revalidate clock boundaries first')
    indexed_comparison=any('discovery' in c for c in parent['cases'])
    if indexed_comparison:
        selected=[(c['reader'] if c['reader']=='directory' else c['reader']+'-'+c['discovery'],c)
                  for c in parent['cases'] if c['mode']=='bytecode']
    else:
        selected=[(r,next(c for c in parent['cases'] if c['scenario']=='rest' and c['mode']=='bytecode' and c['reader']==r))
                  for r in ('directory-stock','directory','python','odin')]
    for reader,original in selected:
        command=original['command'];root=command[command.index('--root')+1]
        index=command[command.index('--index')+1] if '--index' in command else None
        trace=args.work/(reader+'.trace');groups=defaultdict(Counter);read_bytes=Counter();top_paths=Counter();active=False
        total=benchmark.parse_trace(trace)
        for line in trace.read_text().splitlines():
            if 'GAIA_WORKLOAD_BEGIN' in line:active=True;continue
            if 'GAIA_WORKLOAD_END' in line:active=False;continue
            if not active:continue
            m=re.match(r'^(?:\d+\s+)?(\w+)\(.*\)\s+=\s+(-?\d+)',line)
            if not m:raise ValueError('unparsed active trace line')
            call,value=m.group(1),int(m.group(2))
            if root in line or (index and index in line):group='Dependency input'
            elif parent['native']['path'] in line:group='Native extension'
            elif 'django_fixture' in line:group='Project fixture'
            elif any(s in line for s in ('/usr/lib/','/lib/','/usr/bin/')):group='Host runtime/library'
            else:group='Other'
            groups[group][call]+=1
            if call in ('read','pread64') and value>0:
                read_bytes[group]+=value
                fd=re.search(r'(?:read|pread64)\(\d+<([^>]+)>',line)
                if fd:top_paths[fd.group(1)]+=value
        if sum(sum(v.values()) for v in groups.values())!=total['counted_calls']:
            raise ValueError('trace attribution did not partition')
        grouped={g:dict(calls=dict(c),metadata_calls=sum(v for k,v in c.items() if k in METADATA),
                        open_calls=sum(c[k] for k in ('open','openat','openat2')),
                        read_calls=sum(c[k] for k in ('read','pread64')),read_bytes=read_bytes[g]) for g,c in groups.items()}
        stats=pstats.Stats(str(args.work/(reader+'.pstats')));buckets=Counter();functions=[]
        for (filename,line,name),(_,calls,own,inclusive,_) in stats.stats.items():
            buckets[category(filename,name)]+=own
            functions.append(dict(file=filename,line=line,function=name,calls=calls,self_seconds=own,inclusive_seconds=inclusive))
        if abs(sum(buckets.values())-stats.total_tt)>1e-8:raise ValueError('profile buckets do not partition')
        observed={kind:json.loads((args.work/(reader+'-'+kind+'-result.json')).read_text()) for kind in ('trace','profile')}
        for sample in observed.values():
            if not sample['correct'] or sample['api_result']!=original['samples'][0]['api_result']:
                raise ValueError('diagnostic app output differs')
            if sample['module_origins']!=original['samples'][0]['module_origins'] or sample['executed_files']!=original['samples'][0]['executed_files']:
                raise ValueError('diagnostic import/execution set differs')
        cases.append(dict(reader=reader,command=command,trace_path=str(trace),trace=total,groups=grouped,
                          top_read_paths=top_paths.most_common(15),observations=observed,
                          profile=dict(total_self_seconds=stats.total_tt,buckets=dict(buckets),
                                       functions=sorted(functions,key=lambda f:f['self_seconds'],reverse=True))))
    data=dict(run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ'),parent_run=parent['run_id'],
              trace_filter='%file,fstat,fstatfs,read,pread64,close,lseek,getdents64,mmap,munmap,write',
              scope='One separately traced and one separately profiled bytecode REST application per reader. Instrumented timings are not benchmark results.',cases=cases)
    args.output.mkdir(parents=True,exist_ok=True);benchmark.write_json(args.output/'results.json',data)
    lines=['# Django filesystem and execution diagnostics','',f"Parent application run: `{parent['run_id']}`.",'',
           'One trace and one separate profile per bytecode REST reader. The unchanged app worker is '
           'wrapped by django_probe.py, which marks/enables instrumentation at the first workload clock '
           'and stops it at the sixth. All seven main clock calls are checked. Common wrapper/profiler '
           'stdlib imports can change host import state. Traces were collected concurrently; profiles '
           'were collected separately in sequence. Neither instrumented wall time nor strace syscall '
           'durations are used as ordinary timings or cycle estimates. App/import/code validation remains enabled.', '',
           '## Workload filesystem activity','',
           '| Reader | All metadata calls | All opens | All reads | Dependency-input metadata | Dependency-input opens | Dependency-input reads | Host opens | Host reads |',
           '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for c in cases:
        t=c['trace'];g=c['groups']['Dependency input'];h=c['groups']['Host runtime/library']
        lines.append(f"| {c['reader']} | {t['metadata_calls']} | {t['open_calls']} | {t['read_calls']} | {g['metadata_calls']} | {g['open_calls']} | {g['read_calls']} | {h['open_calls']} | {h['read_calls']} |")
    lines += ['', 'Dependency input includes the root/archive and its sidecar; the Odin shared extension '
              'is categorized separately. Host paths include pure-Python stdlib sources/bytecode, native '
              'modules and shared libraries. The project fixture is separate. These calls occur inside '
              'application initialization/checks/DB-fixture/API/admin workload, excluding common worker '
              'preparation and final correctness checks. Read bytes are returned syscall bytes, not '
              'physical storage traffic or mmap payload bytes.', '',
              '## Disjoint profile self time','',
              'Instrumented milliseconds; all buckets are exclusive and sum to the profile total. '
              'Do not use them as partitions of earlier unprofiled medians.', '',
              ]
    by={c['reader']:c for c in cases}
    columns=list(by) if indexed_comparison else ['directory','python','odin']
    lines += ['| Bucket | '+' | '.join(columns)+' |','| --- | '+' | '.join('---:' for _ in columns)+' |']
    for bucket in sorted({b for c in cases for b in c['profile']['buckets']}):
        lines.append('| '+bucket+' | '+' | '.join(f"{by[r]['profile']['buckets'].get(bucket,0)*1000:.3f}" for r in columns)+' |')
    lines += ['', '## Selected Odin profile functions','',
              'Inclusive values overlap other functions/buckets; do not add them. Profiler activation '
              'counts include generator resumptions, not just distinct enumeration requests. These are hypotheses '
              'for the next uninstrumented comparison, not promised time savings.', '',
              '| Function | Calls | Self ms | Inclusive ms |',
              '| --- | ---: | ---: | ---: |']
    native=by['odin-index'] if indexed_comparison else by['odin']
    for f in native['profile']['functions']:
        if f['function'] in ('_read_directory','iter_zipimport_modules','<built-in method marshal.loads>','<built-in method builtins.__build_class__>'):
            lines.append(f"| {f['function']} | {f['calls']} | {f['self_seconds']*1000:.3f} | {f['inclusive_seconds']*1000:.3f} |")
    if not indexed_comparison:
        lines += ['', 'The native payload reader already uses mapped memory. Remaining dependency-related '
              'reads include a second ZIP-directory pass through stock zipimport, and pkgutil enumeration '
              'still scans its file table. An index-backed path-entry finder/iter_modules implementation '
              'is the next candidate. Residual host-runtime imports and bytecode/class reconstruction '
              'are separate costs; warm page cache does not eliminate filesystem operations or Python '
              'object construction. Inspect raw counts/function records before treating native byte access '
              'as the full startup path.', '']
    else:
        lines += ['', 'Indexed discovery must show no _read_directory or iter_zipimport_modules activations '
                  'for the controlled app. Direct-child iteration still yields lazily: its profiler activation '
                  'count includes resumptions; the worker counter records distinct requests. Residual host '
                  'imports and Python runtime initialization are unchanged. Compare the uninstrumented '
                  'parent report for speed, not these diagnostic times.', '']
    (args.output/'REPORT.md').write_text('\n'.join(lines));print(args.output/'REPORT.md')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,default=benchmark.HERE/'_work/runs/django/results.json')
    parser.add_argument('--work',type=Path,default=benchmark.HERE/'_work/django-diagnostics')
    parser.add_argument('--output',type=Path,default=benchmark.HERE/'_work/runs/django-diagnostics')
    summarize(parser.parse_args())
