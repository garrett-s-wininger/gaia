"""Summarize workload-scoped host versus stdlib-snapshot file access."""
import argparse
from collections import Counter,defaultdict
import hashlib
import json
from pathlib import Path
import re

import benchmark
from summarize_django_probe import METADATA


def summarize(args):
    parent=json.loads(args.inputs.read_text())
    for relative,digest in parent['consumer_implementation_sha256'].items():
        if hashlib.sha256((benchmark.HERE.parent.parent/relative).read_bytes()).hexdigest()!=digest:
            raise ValueError('consumer changed since benchmark: '+relative)
    cases=[]
    for case in parent['cases']:
        variant=case['variant'];trace=args.work/(variant+'.trace')
        observed=json.loads((args.work/(variant+'-trace-result.json')).read_text())
        expected=case['samples'][0]
        for key in ('correct','module_origins','executed_files','api_result','source_inspection'):
            if observed[key]!=expected[key]:raise ValueError('diagnostic changed '+key)
        if observed['stdlib_stats']!=expected['stdlib_stats']:
            raise ValueError('diagnostic stdlib import state differs')
        active=False;begins=ends=0;groups=defaultdict(Counter);read_bytes=Counter()
        for line in trace.read_text().splitlines():
            if 'GAIA_WORKLOAD_BEGIN' in line:active=True;begins+=1;continue
            if 'GAIA_WORKLOAD_END' in line:active=False;ends+=1;continue
            if not active:continue
            match=re.match(r'^(?:\d+\s+)?(\w+)\(.*\)\s+=\s+(-?\d+)',line)
            if not match:raise ValueError('unparsed workload syscall: '+line)
            call,value=match.group(1),int(match.group(2))
            if parent['snapshot_descriptor'] in line:group='Snapshot descriptor'
            elif any(parent['snapshot'][key] in line for key in ('directory','archive','index')):group='Snapshot payload/index'
            elif '/usr/lib/python' in line and re.search(r'\.pyc(?:[">/]|$)',line):group='Host stdlib bytecode'
            elif '/usr/lib/python' in line and re.search(r'\.py(?:[">/]|$)',line):group='Host stdlib source'
            elif '/usr/lib/' in line or '/lib/' in line:group='Other host libraries/paths'
            else:group='Other/dependency/fixture'
            groups[group][call]+=1
            if call in ('read','pread64') and value>0:read_bytes[group]+=value
        if begins!=1 or ends!=1:raise ValueError('invalid workload markers')
        rows={group:dict(calls=dict(counts),metadata=sum(n for c,n in counts.items() if c in METADATA),
                        opens=sum(counts[c] for c in ('open','openat','openat2')),
                        reads=sum(counts[c] for c in ('read','pread64')),read_bytes=read_bytes[group])
              for group,counts in groups.items()}
        totals={key:sum(row[key] for row in rows.values()) for key in ('metadata','opens','reads','read_bytes')}
        cases.append(dict(variant=variant,trace=str(trace),result=str(args.work/(variant+'-trace-result.json')),
                          groups=rows,totals=totals,stdlib_stats=observed['stdlib_stats']))
    data=dict(parent_run=parent['run_id'],scope='Workload only; separate instrumented processes, no timing claims.',cases=cases)
    args.output.mkdir(parents=True,exist_ok=True);benchmark.write_json(args.output/'results.json',data)
    lines=['# Stdlib snapshot filesystem diagnostics','',f"Parent run: `{parent['run_id']}`.",'',
           'One separate trace per provider; identical application and source-inspection checks pass. '
           'The wrapper validates all seven worker clock calls and records only the application workload, '
           'including mounts and manifest validation. Common interpreter/harness preparation and '
           'post-workload source inspection are excluded. Import state/code-read counts match the '
           'uninstrumented run. No trace timing is used as a benchmark.', '',
           '| Provider | Total metadata | Total opens | Total reads | Host pyc opens/reads | Host source opens/reads | Snapshot payload/index opens/reads |',
           '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for case in cases:
        g=case['groups'];t=case['totals']
        def pair(name):
            row=g.get(name,{});return f"{row.get('opens',0)} / {row.get('reads',0)}"
        lines.append(f"| {case['variant']} | {t['metadata']} | {t['opens']} | {t['reads']} | "+
                     ' | '.join(pair(n) for n in ('Host stdlib bytecode','Host stdlib source','Snapshot payload/index'))+' |')
    lines+=['','Metadata includes failed path probes. Opens/reads count calls, including EOF reads. '
            'The descriptor is counted separately in JSON and totals. Snapshot payload/index includes '
            'the manifest. Mapped access still incurs page faults/page-cache work; zero read syscalls '
            'does not mean zero storage traffic. Remaining shared libraries, directory enumeration, '
            'project and dependency inputs retain their ordinary paths. Raw per-group syscall counts '
            'and byte totals are in results.json.','']
    (args.output/'REPORT.md').write_text('\n'.join(lines))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,default=benchmark.HERE/'_work/runs/stdlib/results.json')
    parser.add_argument('--work',type=Path,default=benchmark.HERE/'_work/stdlib-diagnostics')
    parser.add_argument('--output',type=Path,default=benchmark.HERE/'_work/runs/stdlib/diagnostics')
    summarize(parser.parse_args())
