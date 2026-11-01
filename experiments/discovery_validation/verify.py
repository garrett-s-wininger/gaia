"""Independent pytest-cov context oracle and historical regression checks."""
import argparse
import json
from pathlib import Path
import shutil
from coverage import CoverageData
from evidence import observed_symbols,symbols
from run import checkout,run_tests,write


def main():
    p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True)
    p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.work=a.work.resolve();a.work.mkdir(parents=True,exist_ok=False)
    tasks=json.loads((Path(__file__).parent/'tasks.json').read_text())['tasks'];results={}
    for task in tasks:
        root=a.work/task['id']/'project';state=root.parent/'state';state.mkdir(parents=True)
        checkout(a.repo.resolve(),task['commit']+'^1',root)
        native=run_tests(root,state,'shared_evidence','oracle-fixed-environment','native')
        assert native['exit']==0
        config=state/'coverage.ini';coverage_path=state/'coverage.sqlite3'
        config.write_text('[run]\nbranch = False\nsource = jinja2\ndata_file = '+str(coverage_path)+'\n')
        oracle=run_tests(root,state,'full_suite','oracle-fixed-environment','oracle',
                         ['-p','pytest_cov','--cov=jinja2','--cov-context=test','--cov-report=', '--cov-config='+str(config)])
        assert oracle['exit']==0 and native['outcomes']==oracle['outcomes']
        data=CoverageData(basename=str(coverage_path));data.read()
        contexts={}
        for filename in data.measured_files():
            path=Path(filename)
            if not path.is_relative_to(root/'src'):continue
            rel=path.relative_to(root).as_posix();defs=symbols(path.read_text())
            for line,labels in data.contexts_by_lineno(filename).items():
                for label in labels:
                    node,sep,phase=label.rpartition('|')
                    if not sep or phase not in ('setup','run','teardown'):continue
                    for name in observed_symbols(defs,[line]):contexts.setdefault(node,set()).add(rel+'::'+name)
        actual={(node,key) for node,facts in native['observed'].items() for key in facts}
        expected={(node,key) for node,facts in contexts.items() for key in facts}
        missing=sorted(expected-actual);extra=sorted(actual-expected)
        queried={x['file']+'::'+x['symbol'] for x in task['inspect']}
        query_missing=[p for p in missing if p[1] in queried]
        query_extra=[p for p in extra if p[1] in queried]
        results[task['id']]={'tests':len(native['outcomes']),'native_pairs':len(actual),'oracle_pairs':len(expected),
                             'missing':missing,'extra':extra,'exact_match':actual==expected,
                             'queried_function_pairs':sum(key in queried for node,key in actual),
                             'queried_functions_match':not query_missing and not query_extra,
                             'query_missing':query_missing,'query_extra':query_extra}
        print(task['id'],len(actual),len(expected),'missing',len(missing),'extra',len(extra),flush=True)
    a.output.parent.mkdir(parents=True,exist_ok=True);write(a.output,results)
    if not all(r['queried_functions_match'] for r in results.values()):raise SystemExit('Queried function observations differ from the independent oracle.')
    print('Queried function relationships match independent pytest-cov contexts; full-graph differences remain recorded.')


if __name__=='__main__':main()
