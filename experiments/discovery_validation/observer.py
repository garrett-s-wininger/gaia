"""Read-only export at testmon's existing per-test line/fingerprint boundary."""
import functools
import json
import os
from pathlib import Path
import resource
import pytest

from evidence import generation, symbols

ROOT=None
CONTEXT=None
START=None
REPORTS=[]
OBSERVED={}
CATALOG={}
OWNERS={}
ORIGINAL=None


def pytest_configure(config):
    global ROOT,CONTEXT,START,ORIGINAL
    ROOT=Path(config.rootpath);CONTEXT=os.environ['GAIA_CONTEXT'];START=generation(ROOT,CONTEXT)
    if os.environ.get('GAIA_EXPORT')!='1':return
    from testmon.testmon_core import TestmonData
    ORIGINAL=TestmonData.get_tests_fingerprints
    @functools.wraps(ORIGINAL)
    def exporting(self,nodes_files_lines,reports):
        result=ORIGINAL(self,nodes_files_lines,reports)
        for nodeid,files in nodes_files_lines.items():
            facts=OBSERVED.setdefault(nodeid,{})
            for filename,lines in files.items():
                if not filename.startswith('src/') or not filename.endswith('.py'):continue
                if filename not in CATALOG:
                    CATALOG[filename]=symbols((ROOT/filename).read_text())
                    owners={}
                    for name,info in sorted(CATALOG[filename].items(),key=lambda x:x[1]['end_line']-x[1]['body_line']):
                        for line in range(info['body_line'],info['end_line']+1):owners.setdefault(line,name)
                    OWNERS[filename]=owners
                definitions=CATALOG[filename]
                for name in {OWNERS[filename][line] for line in lines if line in OWNERS[filename]}:
                    facts[filename+'::'+name]=definitions[name]
        return result
    TestmonData.get_tests_fingerprints=exporting


def pytest_runtest_logreport(report):
    REPORTS.append({'nodeid':report.nodeid,'when':report.when,'outcome':report.outcome,
                    'detail':str(report.longrepr) if report.failed else None})


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session,exitstatus):
    global ORIGINAL
    outcomes={}
    for r in REPORTS:
        node=r['nodeid'];old=outcomes.get(node)
        if r['outcome']=='failed':outcomes[node]='failed'
        elif r['when']=='call' and old!='failed':outcomes[node]=r['outcome']
    out={'schema_version':1,'context':CONTEXT,'generation':START,'unchanged_during_run':START==generation(ROOT,CONTEXT),
         'exit':int(exitstatus),'outcomes':outcomes,'reports':REPORTS,
         'observed':{node:sorted(facts) for node,facts in OBSERVED.items()},
         'functions':{filename+'::'+name:info for filename,defs in CATALOG.items() for name,info in defs.items()},
         'collected':session.testscollected,
         'process_peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    Path(os.environ['GAIA_RESULT']).write_text(json.dumps(out,sort_keys=True)+'\n')
    if ORIGINAL is not None:
        from testmon.testmon_core import TestmonData
        TestmonData.get_tests_fingerprints=ORIGINAL
