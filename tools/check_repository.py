"""Check versioned documentation, research indexes and available raw evidence.

A clean checkout may omit ignored raw data. If it is present, its recorded size
and SHA-256 must match. This check does not rerun performance experiments.
"""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys
from urllib.parse import unquote

ROOT=Path(__file__).resolve().parents[1]


def documents():
    result=subprocess.run(['git','ls-files','--cached','--others','--exclude-standard','-z'],
                          cwd=ROOT,check=True,capture_output=True,text=True)
    for name in sorted(set(result.stdout.split('\0'))):
        path=ROOT/name
        if name.endswith('.md') and path.is_file():yield path


def indexed_paths(value):
    if isinstance(value,str) and value.startswith(('experiments/','research/','components/','docs/')):yield value
    elif isinstance(value,list):
        for item in value:yield from indexed_paths(item)
    elif isinstance(value,dict):
        for item in value.values():yield from indexed_paths(item)


def sha256(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1048576),b''):digest.update(block)
    return digest.hexdigest()


def main():
    errors=[];links=0;docs=list(documents());indices=0;verified=0
    manifest=json.loads((ROOT/'research/evidence.json').read_text())
    artifacts={item['path']:item for item in manifest['artifacts']}
    if len(artifacts)!=len(manifest['artifacts']):errors.append('duplicate evidence paths')
    tracked=set(subprocess.check_output(['git','ls-files','--cached','-z'],cwd=ROOT,text=True).split('\0'))
    for target in artifacts.keys()&tracked:errors.append('raw evidence must not be tracked: '+target)
    ignored=subprocess.run(['git','check-ignore','--no-index','--stdin'],cwd=ROOT,
                           input='\n'.join(sorted(artifacts))+'\n',capture_output=True,text=True)
    if ignored.returncode not in (0,1):errors.append('could not check evidence ignore rules: '+ignored.stderr.strip())
    ignored_paths=set(ignored.stdout.splitlines())
    for target,item in artifacts.items():
        if Path(target).is_absolute() or '..' in Path(target).parts:
            errors.append('invalid evidence path: '+target);continue
        if target not in ignored_paths:errors.append('raw evidence must remain ignored: '+target)
        path=ROOT/target
        if path.exists():
            if not path.is_file() or path.stat().st_size!=item['bytes'] or sha256(path)!=item['sha256']:
                errors.append('raw evidence size/hash mismatch: '+target)
            else:verified+=1
    for path in docs:
        for target in re.findall(r'\]\(([^)]+)\)',path.read_text()):
            if target.startswith('#') or re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:',target):continue
            location=unquote(target.split('#',1)[0]).strip('<>')
            if not location:continue
            links+=1;destination=path.parent/location
            try:relative=destination.resolve().relative_to(ROOT).as_posix()
            except ValueError:relative=None
            if not destination.exists() and relative not in artifacts:
                errors.append(f'{path.relative_to(ROOT)}: missing link {target}')
    for index in (ROOT/'research').rglob('experiments.json'):
        data=json.loads(index.read_text())
        for target in indexed_paths(data):
            indices+=1;location=target.split('#',1)[0]
            if location not in artifacts and not (ROOT/location).exists():
                errors.append(f'{index.relative_to(ROOT)}: missing indexed path {target}')
    if errors:
        print('\n'.join(errors),file=sys.stderr);return 1
    print(f'Checked {len(docs)} documentation pages, {links} local links, {indices} indexed paths '
          f'and {len(artifacts)} ignored evidence artifacts ({verified} available hashes verified).')
    return 0


if __name__=='__main__':raise SystemExit(main())
