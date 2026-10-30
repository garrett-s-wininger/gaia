#!/usr/bin/env python3
"""Reproduce the pinned Django corpus; never select new package versions."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.parse
import urllib.request


def main(args):
    manifest=json.loads(args.manifest.read_text())
    args.destination.mkdir(parents=True,exist_ok=True)
    wheels=args.destination/'wheels';wheels.mkdir(exist_ok=True)
    for artifact in manifest['artifacts']:
        url=urllib.parse.urlparse(artifact['url'])
        name=artifact['filename']
        if (url.scheme!='https' or url.netloc!='files.pythonhosted.org'
                or Path(name).name!=name or not name.endswith('.whl')):
            raise ValueError('unexpected artifact URL/name')
        path=wheels/name
        if not path.exists():
            with urllib.request.urlopen(artifact['url'],timeout=120) as response:body=response.read()
            if hashlib.sha256(body).hexdigest()!=artifact['sha256']:raise ValueError('download hash mismatch')
            path.write_bytes(body)
        if hashlib.sha256(path.read_bytes()).hexdigest()!=artifact['sha256']:
            raise ValueError('existing wheel hash mismatch: '+name)
        artifact['path']=str(path.resolve())
    output=args.destination/'provenance.json';output.write_text(json.dumps(manifest,indent=2)+'\n')
    print(output)


if __name__=='__main__':
    here=Path(__file__).resolve().parent
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,default=here/'results/django/provenance.json')
    parser.add_argument('--destination',type=Path,default=here/'_work/django-corpus')
    main(parser.parse_args())
