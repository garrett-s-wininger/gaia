"""Check current documentation navigation and evidence indexes.

Historical results and ignored work trees are deliberately not rewritten or
interpreted as current instructions. This check does not rerun experiments.
"""
from pathlib import Path
import json
import re
import subprocess
import sys
from urllib.parse import unquote

ROOT=Path(__file__).resolve().parents[1]



def documents():
    yield ROOT/'README.md'
    for name in ('docs','components','research'):
        yield from (ROOT/name).rglob('*.md')
    for base in (ROOT/'experiments/compiler',ROOT/'experiments/python/dependency_bundles',ROOT/'experiments/python/dependency_solving'):
        for name in ('README.md','FINDINGS.md'):
            if (base/name).is_file():yield base/name
    yield ROOT/'experiments/README.md'
    yield ROOT/'experiments/reproducing.md'
    yield ROOT/'experiments/python/README.md'


def indexed_paths(value):
    if isinstance(value,str) and value.startswith(('experiments/','research/','components/','docs/')):yield value
    elif isinstance(value,list):
        for item in value:yield from indexed_paths(item)
    elif isinstance(value,dict):
        for item in value.values():yield from indexed_paths(item)


def main():
    errors=[];links=0;docs=list(documents());indices=0
    manifest=json.loads((ROOT/'research/evidence.json').read_text())
    local_artifacts={item['path'] for item in manifest['artifacts']}
    ignored=subprocess.run(['git','check-ignore','--no-index','--stdin'],cwd=ROOT,
                           input='\n'.join(sorted(local_artifacts))+'\n',capture_output=True,text=True)
    if ignored.returncode not in (0,1):
        errors.append('could not check evidence ignore rules: '+ignored.stderr.strip())
    for target in local_artifacts:
        if Path(target).is_absolute() or '..' in Path(target).parts:
            errors.append('invalid evidence path: '+target)
        elif target not in ignored.stdout.splitlines():
            errors.append('raw evidence must remain ignored: '+target)
    for path in docs:
        for target in re.findall(r'\]\(([^)]+)\)',path.read_text()):
            if target.startswith('#') or re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:',target):continue
            location=unquote(target.split('#',1)[0]).strip('<>')
            if not location:continue
            links+=1
            if not (path.parent/location).exists():errors.append(f'{path.relative_to(ROOT)}: missing link {target}')
    for index in (ROOT/'research').rglob('experiments.json'):
        data=json.loads(index.read_text())
        for target in indexed_paths(data):
            indices+=1
            location=target.split('#',1)[0]
            if location not in local_artifacts and not (ROOT/location).exists():
                errors.append(f'{index.relative_to(ROOT)}: missing indexed path {target}')
    if errors:
        print('\n'.join(errors),file=sys.stderr);return 1
    print(f'Checked {len(docs)} documentation pages, {links} local links, {indices} indexed paths and {len(local_artifacts)} ignored evidence artifacts.')
    return 0

if __name__=='__main__':raise SystemExit(main())
